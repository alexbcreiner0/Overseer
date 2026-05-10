import logging
logger = logging.getLogger(__name__)
from PyQt6 import (
    QtWidgets as qw,
    QtGui as qg,
    QtCore as qc
)
import numpy as np
import copy, os
from .tools.creation_tools import flow_seqify, atomic_write
from .tools.qt_tools import recolor_icon
from pathlib import Path
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from .widgets.CustomNavigationToolbar import CustomNavigationToolbar
from matplotlib import pyplot as plt
import sys, importlib, yaml, math, inspect
from .paths import anonymous_submission_mode_active, release_mode_active
from .ControlPanel import ControlPanel
from .GraphPanel import GraphPanel
from .SimWorker import SimController
from .BridgeWorker import BridgeWorker
from .tools.loader import (
    load_presets, to_plain, 
    params_from_mapping, format_plot_config, 
    reload_package_folder, 
    open_with_default_app,
    get_user_data_dir
)
from multiprocessing import Queue, get_context

# from simulation.parameters import params_from_mapping, to_plain
from .widgets.Dialogs import SaveDialog, DescDialog, NewModelDialog
from .widgets.EditConfigDialog import EditConfigDialog

def ensure_models_on_path(models_path: Path):
    """ Add the models directory to the system path if it isn't """
    models_parent = str(models_path.parent)
    if models_parent not in sys.path:
        sys.path.insert(0, models_parent)

def refresh_models_path(old_models_dir: Path, new_models_dir: Path) -> None:
    old_parent = str(old_models_dir.parent)
    new_parent = str(new_models_dir.parent)

    if old_parent and old_parent in sys.path and old_parent != new_parent:
        sys.path.remove(old_parent)

    if new_parent in sys.path:
        sys.path.remove(new_parent)
    sys.path.insert(0, new_parent)

    importlib.invalidate_caches()

    for name in list(sys.modules):
        if name == "models" or name.startswith("models."):
            del sys.modules[name]

class MainWindow(qw.QMainWindow):

    def __init__(self, env):
        super().__init__()
        self.env = env

        with open(env.config_file, "r") as f:
            self.config = yaml.safe_load(f)

        self.status_bar = self.statusBar()
        self.settings = self.config.get("global_settings", {})

        self.setWindowTitle("Overseer")

        data_dir = get_user_data_dir(self.settings, self.env)
        setattr(self.env, "user_data_dir", data_dir)
        setattr(self.env, "models_dir", self.env.user_data_dir / "models")
        setattr(self.env, "log_dir", self.env.user_data_dir / "logs")
        setattr(self.env, "demos_file", self.env.user_data_dir / "demos.yml")

        with open(env.demos_file, "r") as f:
            self.demos = yaml.safe_load(f).get("demos", {})
        
        ensure_models_on_path(self.env.models_dir)

        self._live_animation = True
        self._run_id = 0
        self.bridge_worker = None
        self.bridge_thread = None
        self._sim_state = "IDLE"
        self._rerun_pending = False
        self._pending_restart_update = None

        self._digit_buffer = (1,1)

        self._pending_traj = None
        self._pending_t = None
        self._anim_timer = qc.QTimer(self)
        self._anim_timer.timeout.connect(self._apply_next_frame)

        self.current_demo_name, self.current_demo = self._find_default(self.demos)
        self._sleep_time = self.current_demo.get("details", {}).get("simulation_speed", 0)
        self.sim_model = self.current_demo.get("details", {}).get("simulation_model", {})

        self.ctx = get_context("spawn")
        self.sim_controller = SimController(self.ctx, parent= self)
    
        (
            self.params,
            self.current_sim_func,
            self.presets,
            self.panel_data,
            self.plotting_data,
            self.functions
        ) = self._get_data(self.current_demo)
        self._reset_global_settings()

        self._anim_timer.setInterval(self.settings.get("rendering_framerate", 30))  # ~30fpsmain

        self.model_label = qw.QLabel(f"Model: {self.current_demo.get("name", "")}")
        self.status_bar.addPermanentWidget(self.model_label)

        # This is a hack I did to get commodity names into a particular economic model. 
        #  the only general feature which could replace this would be one which allows you to
        #  label plots based on some external function call
        model_settings = self.config.get("model_specific_settings", {}).get(self.sim_model, None)
        if model_settings is not None:
            if "commodity_names" in model_settings:
                com_names = model_settings["commodity_names"]
                self.plotting_data = format_plot_config(self.plotting_data, com_names)

        # Create top bar menu
        self.presets_submenu, self.results_submenu = self._make_menu(self.presets, self.demos)

        self.figure, self.axis = plt.subplots(layout= self.settings.get("figure_mode", "tight"))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = CustomNavigationToolbar(
            self.canvas,
            parent= self,
            default_dir= self.settings.get("default_save_dir", "."),
            default_save_name= self.settings.get("default_save_name", "figure"),
            params= self.params)
        self.removeToolBar(self.toolbar)
        
        # make top toolbar
        self.nav_toolbar = self._build_nav_toolbar()
        self.addToolBar(qc.Qt.ToolBarArea.TopToolBarArea, self.nav_toolbar)
        
        self.traj, self.t = None, None

        (   
            self.graph_panel,
            self.control_panel,
            self.dropdown_choices
        ) = self._make_panels(
            self.plotting_data,
            self.panel_data,
            self.current_demo
        )

        self.graph_panel._block_axis_callback = True
        self._load_saved_axis_settings()
        self.graph_panel._block_axis_callback = False

        self.graph_panel.toolbar.pan()

        num_slots = len(self.graph_panel.axes)
        for slot_index in range(num_slots):
            cfg = self.control_panel.get_slot_config(slot_index)
            if cfg is None:
                continue
            dropdown_index, options, slot_cfg = cfg
            self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, slot_cfg)

        self.main_splitter = qw.QSplitter(qc.Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.control_panel)
        self.main_splitter.addWidget(self.graph_panel)

        self.main_splitter.setStretchFactor(0,3)
        self.main_splitter.setStretchFactor(1,5)
        
        self.main_splitter.setCollapsible(1, False)
        self.graph_panel.setMinimumWidth(50) # matplotlib crashes at 0

        total = max(1, self.main_splitter.width())
        left = int(total * 3 / 8)   # 3:(3+5)
        right = total - left
        self.main_splitter.setSizes([left, right])

        self.update_figure_background(use_window_background=True)

        qc.QCoreApplication.instance().installEventFilter(self)

        self.setCentralWidget(self.main_splitter)
        self._assign_keybinds(first_boot= True)

        if self.settings.get("run_on_startup", True):
            self.start_sim()

    def _assign_keybinds(self, first_boot = False):
        """ Does what it says """
        try:
            with open(self.env.config_dir / "keybindings.yml", "r") as f:
                keybindings = yaml.safe_load(f)
        except OSError:
            keybindings = {}

        if hasattr(self, "shortcuts"):
            for sc_dict in self.shortcuts.values():
                sc = sc_dict.get("actual_shortcut")
                try:
                    sc.activated.disconnect()
                    sc.setEnabled(False)
                    sc.deleteLater()
                except:
                    pass
            self.shortcuts.clear()

        self.shortcuts = {
            "toggle_control_panel": {
                "shortcut": keybindings.get("toggle_control_panel", "Ctrl+K"),
                "slot": self.toggle_control_panel
            },
            "next_control_tab": {
                "shortcut": keybindings.get("next_control_tab", "Ctrl+Tab"),
                "slot": lambda: self._advance_tab(1)
            },
            "prev_control_tab": {
                "shortcut": keybindings.get("prev_control_tab", "Ctrl+Shift+Tab"),
                "slot": lambda: self._advance_tab(-1)
            },
            "pause_sim": {
                "shortcut": keybindings.get("pause_sim", "Space"),
                "slot": self.toggle_pause
            },
            "kill_sim": {
                "shortcut": keybindings.get("kill_sim", "Ctrl+J"),
                "slot": self._kill_sim
            },
            "toggle_panning": {
                "shortcut": keybindings.get("toggle_panning", "Ctrl+P"),
                "slot": self.graph_panel.toolbar.pan
            },
            "save_screenshot": {
                "shortcut": keybindings.get("save_screenshot", "Ctrl+S,S"),
                "slot": self.toolbar.save_figure,
            },
            "save_preset": {
                "shortcut": keybindings.get("save_preset", "Ctrl+S,P"),
                "slot": self._save_preset
            },
            "save_slot_view": {
                "shortcut": keybindings.get("save_slot_view", "Ctrl+S,V"),
                "slot": self._save_slot_view,
            },
            "save_cat_view": {
                "shortcut": keybindings.get("save_cat_view", "Ctrl+S,C"),
                "slot": lambda: self._on_cat_settings_shortcut("S"),
            },
            "save_stored_limits_view": {
                "shortcut": keybindings.get("save_stored_limits_view", "Ctrl+S,A"),
                "slot": self._save_slot_view,
            },
            "save_demo_view": {
                "shortcut": keybindings.get("save_demo_view", "Ctrl+S,D"),
                "slot": self._save_slot_settings,
            },
            "speed_up": {
                "shortcut": keybindings.get("speed_up", "Ctrl+Plus"),
                "slot": lambda: self._increment_sim_speed(-0.01)
            },
            "speed_down": {
                "shortcut": keybindings.get("speed_down", "Ctrl+Minus"),
                "slot": lambda: self._increment_sim_speed(0.01)
            },
            "start_sim": {
                "shortcut": keybindings.get("start_sim", "F5"),
                "slot": self.start_sim
            },
            "tight_layout": {
                "shortcut": keybindings.get("tight_layout", "F6"),
                "slot": self.tight_layout
            },
            "reload_current_demo": {
                "shortcut": keybindings.get("reload_current_demo", "F7"),
                "slot": self.reload_current_demo
            },
            "refresh_control_panel_and_plots": {
                "shortcut": keybindings.get("refresh_control_panel_and_plots", "F8"),
                "slot": self.refresh_control_panel_and_plots
            },
            "refresh_keybindings": {
                "shortcut": keybindings.get("refresh_keybindings", "F9"),
                "slot": self._assign_keybinds
            },
            "close": {
                "shortcut": keybindings.get("close", "Esc"),
                "slot": self.close
            },
            "expand_grid_right": {
                "shortcut": keybindings.get("expand_grid_right", "Ctrl+Shift+Right"),
                "slot": lambda: self.expand_grid("right")
            },
            "expand_grid_left": {
                "shortcut": keybindings.get("expand_grid_left", "Ctrl+Shift+Left"),
                "slot": lambda: self.expand_grid("left")
            },
            "expand_grid_up": {
                "shortcut": keybindings.get("expand_grid_up", "Ctrl+Shift+Up"),
                "slot": lambda: self.expand_grid("up")
            },
            "expand_grid_down": {
                "shortcut": keybindings.get("expand_grid_down", "Ctrl+Shift+Down"),
                "slot": lambda: self.expand_grid("down")
            },
            "register_buffer_select_11": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,1,1"),
                "slot": lambda: self.register_buffer_select((1,1))
            },
            "register_buffer_select_12": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,1,2"),
                "slot": lambda: self.register_buffer_select((1,2))
            },
            "register_buffer_select_13": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,1,3"),
                "slot": lambda: self.register_buffer_select((1,3))
            },
            "register_buffer_select_21": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,2,1"),
                "slot": lambda: self.register_buffer_select((2,1))
            },
            "register_buffer_select_22": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,2,2"),
                "slot": lambda: self.register_buffer_select((2,2))
            },
            "register_buffer_select_23": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,2,3"),
                "slot": lambda: self.register_buffer_select((2,3))
            },
            "register_buffer_select_31": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,3,1"),
                "slot": lambda: self.register_buffer_select((3,1))
            },
            "register_buffer_select_32": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,3,2"),
                "slot": lambda: self.register_buffer_select((3,2))
            },
            "register_buffer_select_33": {
                "shortcut": keybindings.get("register_buffer_select", "Ctrl+B,3,3"),
                "slot": lambda: self.register_buffer_select((3,3))
            },
            "next_cat_slot": {
                "shortcut": keybindings.get("next_cat_slot", "Ctrl+Down"),
                "slot": lambda: self.change_plot_options("cat", 1)
            },
            "prev_cat_slot": {
                "shortcut": keybindings.get("prev_cat_slot", "Ctrl+Up"),
                "slot": lambda: self.change_plot_options("cat", -1)
            },
            "open_global_settings": {
                "shortcut": keybindings.get("open_global_settings", "F1"),
                "slot": lambda: self.open_settings(tab= 0)
            },
            "open_control_panel_settings": {
                "shortcut": keybindings.get("open_control_panel_settings", "F2"),
                "slot": lambda: self.open_settings(tab= 4)
            },
            "open_plot_settings": {
                "shortcut": keybindings.get("open_plot_settings", "F3"),
                "slot": lambda: self.open_settings(tab= 5)
            },
            "open_demo_settings": {
                "shortcut": keybindings.get("open_demo_settings", "F4"),
                "slot": lambda: self.open_settings(tab= 6)
            },
            "toggle_plot_1": {
                "shortcut": keybindings.get("toggle_plot_1", "Ctrl+1"),
                "slot": lambda: self.change_plot_options("plot", 0)
            },
            "toggle_plot_2": {
                "shortcut": keybindings.get("toggle_plot_2", "Ctrl+2"),
                "slot": lambda: self.change_plot_options("plot", 1)
            },
            "toggle_plot_3": {
                "shortcut": keybindings.get("toggle_plot_3", "Ctrl+3"),
                "slot": lambda: self.change_plot_options("plot", 2)
            },
            "toggle_plot_4": {
                "shortcut": keybindings.get("toggle_plot_4", "Ctrl+4"),
                "slot": lambda: self.change_plot_options("plot", 3)
            },
            "toggle_plot_5": {
                "shortcut": keybindings.get("toggle_plot_5", "Ctrl+5"),
                "slot": lambda: self.change_plot_options("plot", 4)
            },
            "toggle_plot_6": {
                "shortcut": keybindings.get("toggle_plot_6", "Ctrl+6"),
                "slot": lambda: self.change_plot_options("plot", 5)
            },
            "toggle_plot_7": {
                "shortcut": keybindings.get("toggle_plot_7", "Ctrl+7"),
                "slot": lambda: self.change_plot_options("plot", 6)
            },
            "toggle_plot_8": {
                "shortcut": keybindings.get("toggle_plot_8", "Ctrl+8"),
                "slot": lambda: self.change_plot_options("plot", 7)
            },
            "toggle_plot_9": {
                "shortcut": keybindings.get("toggle_plot_9", "Ctrl+9"),
                "slot": lambda: self.change_plot_options("plot", 8)
            },
            "toggle_legend": {
                "shortcut": keybindings.get("toggle_legend", "Ctrl+L,Ctrl+T"),
                "slot": lambda: self.change_plot_options("legend", "T"),
            },
            "legend_size_up": {
                "shortcut": keybindings.get("legend_size_up", "Ctrl+]"),
                "slot": lambda: self.change_plot_options("legend", "+"),
            },
            "legend_size_down": {
                "shortcut": keybindings.get("legend_size_down", "Ctrl+["),
                "slot": lambda: self.change_plot_options("legend", "-"),
            },
            "legend_rotate": {
                "shortcut": keybindings.get("legend_rotate", "Ctrl+L,Ctrl+R"),
                "slot": lambda: self.change_plot_options("legend", "R"),
            },
            "toggle_plot_title": {
                "shortcut": keybindings.get("toggle_plot_title", "Ctrl+T,Ctrl+T"),
                "slot": lambda: self.change_plot_options("title", "T")
            },
            "toggle_x_axis_title": {
                "shortcut": keybindings.get("toggle_x_axis_title", "Ctrl+T,Ctrl+X"),
                "slot": lambda: self.change_plot_options("title", "X")
            },
            "toggle_y_axis_title": {
                "shortcut": keybindings.get("toggle_y_axis_title", "Ctrl+T,Ctrl+Y"),
                "slot": lambda: self.change_plot_options("title", "Y")
            },
        }

        for name, short_dict in self.shortcuts.items():
            key_seq = short_dict["shortcut"]
            shortcut = qg.QShortcut(qg.QKeySequence(key_seq), self)
            shortcut.setContext(qc.Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(short_dict["slot"])
            shortcut.activatedAmbiguously.connect(
                lambda name=name, seq=key_seq: print(f"AMBIGUOUS: {name} -> {seq}")
            )

        if not first_boot:
            self.status_bar.showMessage("Keybindings reloaded", msecs=3000)

    def register_buffer_select(self, coord):
        """ Registers the current slot choice when user changes it """
        self._digit_buffer = coord
        self.status_bar.showMessage(f"Grid choice set to {coord}", msecs=3000)

    def expand_grid(self, direction):
        if direction == "left":
            self.control_panel.cols_spinner.stepDown()
        elif direction == "right":
            self.control_panel.cols_spinner.stepUp()
        elif direction == "up":
            self.control_panel.rows_spinner.stepDown()
        elif direction == "down":
            self.control_panel.rows_spinner.stepUp()

    def _get_slot_index(self):
        if not hasattr(self, "_digit_buffer"):
            return

        coord = tuple(self._digit_buffer)
        x, y = coord
        current_rows = self.control_panel.rows_spinner.value()
        current_cols = self.control_panel.cols_spinner.value()

        if x > current_rows or y > current_cols:
            return

        slot_idx = (y-1) + current_cols*(x-1)
        return slot_idx

    def _save_slot_view(self):
        if not hasattr(self, "_digit_buffer"):
            return

        slot_idx = self._get_slot_index()
        axis_widget = self.control_panel.slot_axes_controls[slot_idx]
        axis_widget._on_save_clicked()

    def change_plot_options(self, target, instruct):
        if not hasattr(self, "_digit_buffer"):
            return

        slot_idx = self._get_slot_index()
        if slot_idx is None:
            return
        dropdown = self.control_panel.slot_dropdowns[slot_idx]

        if target == "cat":
            cat_idx = dropdown.currentIndex()
            dropdown.setCurrentIndex((cat_idx + instruct) % len(self.dropdown_choices))

        if target == "plot":
            name = dropdown.currentText()
            try:
                current_val = dropdown.boxes[name][instruct].isChecked()
                dropdown.boxes[name][instruct].setChecked(True if not current_val else False)
            except IndexError:
                pass

        if target in "legend":
            options_widget = self.control_panel.slot_options[slot_idx]
            if instruct == "T":
                current_val = options_widget.legend_checkbox.isChecked()
                options_widget.legend_checkbox.setChecked(True if not current_val else False)

            if instruct == "+":
                options_widget.legend_size_spin.stepUp()

            if instruct == "-":
                options_widget.legend_size_spin.stepDown()

            if instruct == "R":
                n = options_widget.legend_pos_combo.count()
                cur = options_widget.legend_pos_combo.currentIndex()
                options_widget.legend_pos_combo.setCurrentIndex((cur + 1) % n)

        if target in "title":
            options_widget = self.control_panel.slot_options[slot_idx]
            if instruct == "T":
                current_val = options_widget.title_checkbox.isChecked()
                options_widget.title_checkbox.setChecked(True if not current_val else False)

            if instruct == "X":
                current_val = options_widget.xlabel_checkbox.isChecked()
                options_widget.xlabel_checkbox.setChecked(True if not current_val else False)

            if instruct == "Y":
                current_val = options_widget.ylabel_checkbox.isChecked()
                options_widget.ylabel_checkbox.setChecked(True if not current_val else False)

    def _advance_tab(self, dir):
        current_idx = self.control_panel.content.currentIndex()
        self.control_panel.content.setCurrentIndex((current_idx + dir) % 2)

    def toggle_control_panel(self):
        sizes = self.main_splitter.sizes()

        # If control panel is visible
        if sizes[0] > 20:
            self._saved_splitter_sizes = sizes
            self.main_splitter.setSizes([0, sum(sizes)])
        else:
            # Restore previous sizes
            if hasattr(self, "_saved_splitter_sizes"):
                self.main_splitter.setSizes(self._saved_splitter_sizes)
            else:
                self.main_splitter.setSizes([300, 700])

    def _load_saved_axis_settings(self):
        demo_config = self.current_demo.get("details", {}).get("axis_settings", {})
        rows, cols, limits, saved_limits, dropdown_indices, slot_settings, checked = self._get_slot_settings(demo_config)
        self.control_panel._alter_slot_layout(rows, cols, limits, saved_limits, dropdown_indices, checked, slot_settings)
        self._apply_saved_projections(dropdown_indices)
        self._set_graph_lims(limits)

    def _apply_saved_projections(self, dropdown_indices):
        for slot_index, idx in enumerate(dropdown_indices):
            choice_name = self.graph_panel._choice_name_from_index(idx)
            projection = self.graph_panel.data.get(choice_name, {}).get("projection", "2d")
            want_3d = True if projection == "3d" else False
            self.graph_panel._ensure_slot_projection(slot_index, want_3d)

    def _get_slot_settings(self, demo_config):
        dim = demo_config.get("dimension", (1,1))
        rows, cols = dim
        total_axes = rows*cols
        limits = []
        lims_dict = demo_config.get("limits", {})
        for lim in lims_dict:
            coords = tuple()
            for coord in lims_dict[lim]:
                coords += (tuple(coord),)
            limits.append(coords)
        saved_limits = []
        saved_lims_dict = demo_config.get("saved_limits", {})
        for lim in saved_lims_dict:
            coords = tuple()
            for coord in saved_lims_dict[lim]:
                coords += (tuple(coord),)
            saved_limits.append(coords)
        dropdown_indices = demo_config.get("dropdown_indices", [])
        slot_settings_dict = demo_config.get("settings", {})
        slot_settings = []
        for settings in slot_settings_dict:
            slot_settings.append(slot_settings_dict[settings])
        checked = []
        checked_dict = demo_config.get("checked_plots", {})
        for axis in checked_dict:
            checked.append(checked_dict[axis])

        return rows, cols, limits, saved_limits, dropdown_indices, slot_settings, checked

    def _get_current_axis_settings(self):
        rows, cols, limits, saved_limits, dropdown_indices, checked, slot_settings = self.control_panel.get_slot_settings()
        
        details = self.current_demo.get("details", {})
        axis_settings = copy.deepcopy(details.get("axis_settings", {}))
        axis_settings["dimension"] = [rows, cols]
        axis_settings["limits"] = {}
        for i in range(1,len(limits)+1):
            lims = limits[i-1]
            axis_coords = []
            for coord in lims:
                axis_coords.append(list(coord))
            axis_settings["limits"][f"a{i}"] = axis_coords
        axis_settings["saved_limits"] = {}
        for i in range(1,len(saved_limits)+1):
            lims = saved_limits[i-1]
            if None in lims:
                continue
            axis_coords = []
            for coord in lims:
                axis_coords.append(list(coord))
            axis_settings["saved_limits"][f"a{i}"] = axis_coords
        if not axis_settings["saved_limits"]:
            del axis_settings["saved_limits"]
        axis_settings["dropdown_indices"] = dropdown_indices
        axis_settings["checked_plots"] = {}
        for i in range(1,len(checked)+1):
            axis_settings["checked_plots"][f"a{i}"] = checked[i-1]
        axis_settings["settings"] = {}
        for i in range(1,len(slot_settings)+1):
            axis_settings["settings"][f"a{i}"] = slot_settings[i-1]

        return axis_settings

    def _save_slot_settings(self):
        self.current_demo["details"]["axis_settings"] = self._get_current_axis_settings()
        new_demo_data = {"demos": self.demos}
        flow_seqify(new_demo_data)

        atomic_write(self.env.demos_file, new_demo_data)
        self.status_bar.showMessage("Current overall view saved as demo default.", msecs= 4000)

    def _reset_global_settings(self):
        if hasattr(self, "toolbar"):
            self.toolbar.set_default_dir(self.settings.get("default_save_dir", str(Path.home())))
            self.toolbar.default_save_name = self.settings.get("default_save_name", "figure")
    
        if hasattr(self, "graph_panel"):
            self.graph_panel.settings = self.settings

    def _kill_sim(self):
        if self._sim_state == "RUNNING":
            self._sim_state = "STOPPING"
            if self.sim_controller is not None:
                self._escalate_stop_if_needed()

            self.status_bar.showMessage("Sim was murdered in its sleep.", 2000)
            self._halt_sim_stack(force= True)

    def _halt_sim_stack(self, *, force: bool= False, clear_pending: bool= True, clear_queue: bool = False) -> None:
        """ Safe multipurpose method for halting/killing all of the relevant moving parts of an ongoing sim """

        # ensure no further animation happens
        try:
            self._anim_timer.stop()
        except Exception:
            pass

        if clear_pending:
            self._pending_traj = None
            self._pending_t = None

        bw = getattr(self, "bridge_worker", None)
        # bt = getattr(self, "bridge_thread", None)

        if bw is not None:
            try:
                bw.stop()
            except RuntimeError:
                pass
            try:
                bw.deleteLater()
            except Exception:
                pass

        self.bridge_worker = None

        # if bt is not None:
        #     if bt.isRunning():
        #         bt.quit()
        #         bt.wait(1000)
        #     self.bridge_thread = None

        if clear_queue:
            q = getattr(self, "sim_results_queue", None)
            if q is not None:
                import queue as py_queue
                while True:
                    try:
                        q.get_nowait()
                    except py_queue.Empty:
                        break
                    except Exception:
                        break

        if self.sim_controller is not None:
            try:
                self.sim_controller.request_stop(force=force)
                self.sim_controller.join(timeout= 2.0)
                if force and self.sim_controller.is_alive():
                    self.sim_controller.request_stop(force= True)
                    self.sim_controller.join(timeout= 2.0)
            except Exception:
                pass
            finally:
                self.sim_controller = None

    # def _install_focus_clear_filter(self) -> None:
    #     # Put it on the window and also on the central widget / scroll areas if needed
    #     self.installEventFilter(self)
    #     cw = self.centralWidget()
    #     if cw:
    #         cw.installEventFilter(self)

    def eventFilter(self, a0, a1):
        if a0 is None or a1 is None:
            return super().eventFilter(a0, a1)

        et = a1.type()

        if et == qc.QEvent.Type.KeyPress:
            mods = a1.modifiers()
            key = a1.key()

            if mods & qc.Qt.KeyboardModifier.ControlModifier:
                if mods & qc.Qt.KeyboardModifier.ShiftModifier:
                    if key == qc.Qt.Key.Key_Right:
                        self.expand_grid("right")
                        return True
                    if key == qc.Qt.Key.Key_Left:
                        self.expand_grid("left")
                        return True
                    if key == qc.Qt.Key.Key_Up:
                        self.expand_grid("up")
                        return True
                    if key == qc.Qt.Key.Key_Down:
                        self.expand_grid("down")
                        return True

        if et == qc.QEvent.Type.ShortcutOverride:
            mods = a1.modifiers()
            fw = qw.QApplication.focusWidget()

            in_text_editor = isinstance(
                fw,
                (qw.QLineEdit, qw.QTextEdit, qw.QPlainTextEdit),
            )

            standard_edit_shortcuts = (
                a1.matches(qg.QKeySequence.StandardKey.Copy) or
                a1.matches(qg.QKeySequence.StandardKey.Cut) or
                a1.matches(qg.QKeySequence.StandardKey.Paste) or
                a1.matches(qg.QKeySequence.StandardKey.Undo) or
                a1.matches(qg.QKeySequence.StandardKey.Redo) or
                a1.matches(qg.QKeySequence.StandardKey.SelectAll)
            )

            if mods & qc.Qt.KeyboardModifier.ControlModifier:
                if not (in_text_editor and standard_edit_shortcuts):
                    a1.ignore()
                    return False

        return super().eventFilter(a0, a1)

    def show_partial_results(self, traj, t):
        if traj is None:
            return

        self.traj, self.t = traj, t
        self.graph_panel.traj = traj
        self.graph_panel.t = t

        num_slots = len(self.graph_panel.axes)
        for slot_index in range(num_slots):
            cfg = self.control_panel.get_slot_config(slot_index)
            if cfg is None:
                continue
            dropdown_index, options, slot_cfg = cfg
            self.graph_panel.update_slot_frame(slot_index, dropdown_index, options, slot_cfg)

    def toggle_pause(self):
        # if self.worker:
        #     self.worker.toggle_pause()
        if self.sim_controller is not None:
            self.sim_controller.toggle_pause()


    def update_figure_background(self, use_window_background: bool) -> None:
        """
        If use_transparent is True:
            - Figure and axes are fully transparent.
            - Legend background mimics the window background color (fake transparency).
        If use_transparent is False:
            - Figure, axes, and legend backgrounds are pure white.
        """
        axes = getattr(self.graph_panel, "axes", [self.axis])

        if use_window_background:
            # True transparency for figure & axes
            fig_fc = (0, 0, 0, 0)
            ax_fc = (0, 0, 0, 0)

            plt.rcParams["figure.facecolor"] = fig_fc
            plt.rcParams["axes.facecolor"] = ax_fc

            # Legend default for *new* legends: match Qt window background
            bg = self.palette().color(qg.QPalette.ColorRole.Window)
            legend_rgba = (bg.redF(), bg.greenF(), bg.blueF(), bg.alphaF())
            plt.rcParams["legend.facecolor"] = legend_rgba

            # Canvas: let parent shine through
            self.canvas.setStyleSheet("background: transparent;")

            # Apply to current figure / axes
            self.figure.patch.set_facecolor(fig_fc)
            self.figure.patch.set_alpha(0.0)

            for ax in axes:
                ax.set_facecolor(ax_fc)
                ax.patch.set_alpha(0.0)

                leg = ax.get_legend()
                if leg is not None:
                    frame = leg.get_frame()

                    frame = leg.get_frame()
                    frame.set_facecolor(legend_rgba)  # fake transparency
                    frame.set_alpha(1.0)
                    # Optional: make sure border is visible
                    # frame.set_edgecolor("black")

        else:
            # Solid white everywhere
            fig_fc = "white"
            ax_fc = "white"
            legend_fc = "white"

            plt.rcParams["figure.facecolor"] = fig_fc
            plt.rcParams["axes.facecolor"] = ax_fc
            plt.rcParams["legend.facecolor"] = legend_fc

            self.canvas.setStyleSheet("")  # reset to default

            self.figure.patch.set_facecolor(fig_fc)
            self.figure.patch.set_alpha(1.0)

            for ax in axes:
                ax.set_facecolor(ax_fc)
                ax.patch.set_alpha(1.0)

                leg = ax.get_legend()
                if leg is not None:
                    frame = leg.get_frame()
                    frame.set_facecolor(legend_fc)
                    frame.set_alpha(1.0)
                    # frame.set_edgecolor("black")

        self.canvas.draw_idle()

    def _set_graph_lims(self, limits):
        for i, lims in enumerate(limits):
            self.on_slot_axes_changed(i)

    def _make_panels(self, plotting_data, panel_data, demo):
        if plotting_data is not None:
            dropdown_choices, dropdown_tooltips = self._get_dropdown_choices(plotting_data)
        else:
            plotting_data = {}
            dropdown_choices, dropdown_tooltips = [], {}

        graph_panel = GraphPanel(
            self.traj, self.t, dropdown_choices, plotting_data, self.canvas, 
            self.figure, self.axis, self.toolbar, self.status_bar
        )
        # graph_panel.saved_lims_changed.connect(self.update_saved_lims)
        graph_panel.slot_axes_limits_changed.connect(self.on_slot_axes_limits_changed)
        graph_panel.slot_axes_limits_changed_3d.connect(self.on_slot_axes_limits_changed)
        # xlim, ylim = graph_panel.xlim, graph_panel.ylim
        # self.update_saved_lims(xlim, ylim)

        control_panel = ControlPanel(
            self.env,
            self.status_bar,
            self.params,
            dropdown_choices, 
            dropdown_tooltips,
            panel_data, 
            plotting_data,
            self.sim_model,
            demo
        )
        control_panel.paramChanged.connect(self.start_sim)
        control_panel.layoutChanged.connect(self.on_layout_changed)
        control_panel.slotPlotChoiceChanged.connect(self.on_slot_plot_choice_changed)
        control_panel.slotOptionsChanged.connect(self.on_slot_options_changed)
        control_panel.slotAxesChanged.connect(self.on_slot_axes_changed)
        control_panel.slotAxesCatChanged.connect(self.on_slot_axes_cat_save_request)
        control_panel.paramsReplaced.connect(self._on_params_replaced)

        return graph_panel, control_panel, dropdown_choices

    def _on_params_replaced(self, data):
        new_params, new_sector_names = data
        self.params = new_params
        if new_sector_names is not None:
            self._update_sector_names(new_sector_names)
        self.start_sim()

    def _update_sector_names(self, names):

        with open(self.env.models_dir / self.sim_model / "data" / "plotting_data.yml") as f:
            plotting_data = yaml.safe_load(f)
        formatted = format_plot_config(plotting_data, names)

        self.graph_panel.apply_plotting_data(formatted)

        for slot_index in range(len(self.graph_panel.axes)):
            cfg = self.control_panel.get_slot_config(slot_index)
            if cfg is None:
                continue
            dropdown_index, options, slot_cfg = cfg
            self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, slot_cfg)

        self.control_panel.plotting_data = formatted

    def _apply_next_frame(self):
        if self._pending_traj is None:
            return

        self.show_partial_results(self._pending_traj, self._pending_t)

    def on_slot_axes_limits_changed(self, slot_index: int, xlim: tuple, ylim: tuple, zlim: tuple | None= None):
        """ Method to update the axis entries of a plot control widget when user pans a plot """
        self.control_panel.set_slot_axes_limits(slot_index, xlim, ylim, zlim)

    def _on_cat_settings_shortcut(self, instruct):
        slot_idx = self._get_slot_index()
        
        if instruct == "S":
            self.on_slot_axes_cat_save_request(slot_idx)

    def on_slot_axes_cat_save_request(self, slot_index):
        print("save requested?")
        lims = self.control_panel.get_slot_axes_limits(slot_index)
        cfg = self.control_panel.get_slot_config(slot_index)
        dropdown_index = cfg[0]
        plotting_data = self.control_panel.plotting_data
        dropdown_list = list(plotting_data)
        dropdown_name = dropdown_list[dropdown_index]
        
        plotting_data[dropdown_name]["default_lims"] = lims
        path = self.env.models_dir / self.sim_model / "data" / "plotting_data.yml"

        print(f"Writing data to {path}")
        flow_seqify(plotting_data)
        atomic_write(path, plotting_data)

        self.control_panel.plotting_data = plotting_data

        self.status_bar.showMessage("Default plot category limits saved.", msecs= 4000)

    def on_slot_axes_changed(self, slot_index: int):
        lims = self.control_panel.get_slot_axes_limits(slot_index)
        if lims is None: return

        if len(lims) == 3:
            xlim, ylim, zlim = lims
        else:
            xlim, ylim = lims
            zlim = None
        self.graph_panel.edit_slot_axes(slot_index, xlim, ylim, zlim)

    def on_slot_plot_choice_changed(self, slot_index: int, source: str = "checkbox"):
        # print(f"[DEBUG] Slot {slot_index} dropdown changed to index {_dropdown_index}")
        if not hasattr(self, "traj") or self.traj is None: return

        cfg = self.control_panel.get_slot_config(slot_index)
        if cfg is None: return

        dropdown_index, options, legend_cfg = cfg

        load_idx_defaults = self.settings.get("use_cat_limits", False)
        load_idx_defaults = False if not isinstance(load_idx_defaults, bool) else load_idx_defaults 
        self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, legend_cfg, source= source, load_idx_defaults= load_idx_defaults)
        # self.graph_panel._on_axis_limits_changed(slot_index)

    def on_slot_options_changed(self, slot_index: int):
        """Options changed for a specific slot."""
        if not hasattr(self, "traj") or self.traj is None:
            return

        cfg = self.control_panel.get_slot_config(slot_index)
        if cfg is None:
            return

        dropdown_index, options, slot_cfg = cfg
        self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, slot_cfg)

    def on_layout_changed(self, rows, cols):
        """ Propagate plot dimension change to the graph panel """
        self.graph_panel.set_axes_layout(rows, cols)

        if hasattr(self, "traj") and self.traj is not None:
            self.graph_panel.traj = self.traj
            self.graph_panel.t = self.t

            num_slots = len(self.graph_panel.axes)
            for slot_index in range(num_slots):
                cfg = self.control_panel.get_slot_config(slot_index)
                if cfg is None:
                    continue
                dropdown_index, options, slot_cfg = cfg
                self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, slot_cfg, rescale_legend= True)

        # qc.QTimer.singleShot(0, self.tight_layout)

    def _find_default(self, demos):
        for demo in demos:
            if "default" in demos[demo]:
                if demos[demo]["default"]: return demo, demos[demo]
        return next(iter(demos)), demos[next(iter(demos))]

    def _get_dropdown_choices(self, plotting_data):

        dropdown_choices = [plotting_data[dropdown_choice]["name"] for dropdown_choice in plotting_data]
        dropdown_tooltips = {plotting_data[choice]["name"]: plotting_data[choice].get("tooltip", "No notes") for choice in plotting_data}
        for choice in dropdown_tooltips:
            if not dropdown_tooltips[choice]: dropdown_tooltips[choice] = "No notes"

        return dropdown_choices, dropdown_tooltips

    def on_thread_finished(self):

        self.thread.deleteLater()
        self.thread = None
        self.worker = None

    def _build_nav_toolbar(self):

        nav_toolbar = qw.QToolBar("Navigation")

        for i, action in enumerate(self.toolbar.actions()):
            if i == 10: continue
            nav_toolbar.addAction(action)

        nav_toolbar.addSeparator()
        style = self.style()
        bug_icon = style.standardIcon(qw.QStyle.StandardPixmap.SP_LineEditClearButton)
        pause_icon = style.standardIcon(qw.QStyle.StandardPixmap.SP_MediaPause)

        request_pause = qg.QAction(pause_icon, "Pause simulation", self)
        request_pause.triggered.connect(self.toggle_pause)
        nav_toolbar.addAction(request_pause)

        request_threadkill = qg.QAction(bug_icon, "Force kill sim", self)
        request_threadkill.triggered.connect(self.request_threadkill)
        nav_toolbar.addAction(request_threadkill)

        self.grab_entry = qw.QLineEdit()
        self.grab_entry.setMaximumWidth(80)
    
        grab_as_initial_button = qw.QPushButton("Grab as Initial: ")
        grab_as_initial_button.setToolTip("Attempt to grab the state of the system at the given point in time, and then apply the relevant parameters at that moment as initial conditions. Useful for getting steady states.")
        grab_as_initial_button.clicked.connect(self.grab_as_initial)
        nav_toolbar.addWidget(grab_as_initial_button)
        nav_toolbar.addWidget(self.grab_entry)

        spacer = qw.QWidget()
        spacer.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred,
        )
        nav_toolbar.addWidget(spacer)

        figure_background_checkbox = qw.QCheckBox("Transparent Background")
        figure_background_checkbox.setChecked(True)
        figure_background_checkbox.stateChanged.connect(self._on_figure_background_checkbox_changed)
        nav_toolbar.addWidget(figure_background_checkbox)

        animate_sim_checkbox = qw.QCheckBox("Animate Sim")
        animate_sim_checkbox.setChecked(True)
        animate_sim_checkbox.stateChanged.connect(lambda v: setattr(self, "live_animation", v))
        nav_toolbar.addWidget(animate_sim_checkbox)

        nav_toolbar.addSeparator()

        sim_speed_label = qw.QLabel("Sim Speed: ")
        self.sim_speed_edit = qw.QLineEdit()
        if self._sleep_time != 0:
            self.sim_speed_edit.setText(str(self._sleep_time))
        else:
            self.sim_speed_edit.setPlaceholderText("0.0 (higher = slower)")
        self.sim_speed_edit.setFixedWidth(130)
        self.sim_speed_edit.textChanged.connect(self._adjust_sim_speed)
        nav_toolbar.addWidget(sim_speed_label)
        nav_toolbar.addWidget(self.sim_speed_edit)


        catch_icon = style.standardIcon(qw.QStyle.StandardPixmap.SP_DialogHelpButton)
        tight_layout_action = qg.QAction(catch_icon, "Make the plots adapt to their space better", self)
        tight_layout_action.triggered.connect(self.tight_layout)
        nav_toolbar.addAction(tight_layout_action)

        nav_toolbar.addSeparator()

        return nav_toolbar #, entries, buttons

    def _adjust_sim_speed(self, text):
        try:
            self._sleep_time = float(text)
        except:
            return

        if self.sim_controller is not None and self.sim_controller.is_alive():
            self.sim_controller.set_sleep_time(self._sleep_time)

    def _increment_sim_speed(self, inc):
        self._sleep_time = max(0, self._sleep_time + inc)
        self.sim_speed_edit.setText(f"{self._sleep_time:.3f}")

    def _on_figure_background_checkbox_changed(self, state: int) -> None:
        use_window = True if state == 2 else False
        self.update_figure_background(use_window)

    def tight_layout(self):
        layout_mode = self.settings.get("figure_mode", "tight")
        if layout_mode == "tight":
            self.figure.tight_layout()
        elif layout_mode == "constrained":
            self.figure.set_layout_engine("none")
            self.figure.set_layout_engine("constrained")
            self.canvas.draw()
            # self.figure.get_constrained_layout()
        # self.graph_panel._recompute_base_box_aspect()

        # self.graph_panel.canvas.draw_idle()
        self.figure.canvas.draw_idle()

    def grab_as_initial(self):
        try:
            time = float(self.grab_entry.text())
        except ValueError:
            return

        closest = 0
        for i, t in enumerate(self.t):
            if math.fabs(t - time) < math.fabs(t - self.t[closest]):
                closest = i

        for name in vars(self.params):
            if name in self.traj:
                new_val = self.traj[name][closest]
                setattr(self.params, name, new_val)

        # self.update_plot()
        self.control_panel.load_new_params(self.params)
        self.start_sim()

    def request_threadkill(self):
        if self.sim_controller is not None and self.sim_controller.is_alive():
            self.sim_controller.request_stop()
            self.status_bar.showMessage("Stop requested...", msecs=2000)

    def _make_menu(self, presets, demos):

        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        settings_menu = menu.addMenu("Settings")
        view_menu = menu.addMenu("View")
        sim_menu = menu.addMenu("Simulation")
        demo_menu = menu.addMenu("Demos")
        params_menu = menu.addMenu("Parameters")
        results_menu = menu.addMenu("Results")

        # functions_menu = menu.addMenu("Sim Functions")
        self.sim_choice = qg.QActionGroup(self)
        self.sim_choice.setExclusive(True)

        self._create_presets_submenus(presets, params_menu)
        self._create_results_submenus(results_menu)
    
        rerun_button = qg.QAction("Rerun Simulation", self)
        sim_menu.addAction(rerun_button)
        rerun_button.triggered.connect(self.start_sim)

        reload_button = qg.QAction("Reload simulation", self)
        sim_menu.addAction(reload_button)
        reload_button.triggered.connect(self.reload_current_demo)

        force_kill_action = qg.QAction("Force Stop Simulation", self)
        sim_menu.addAction(force_kill_action)
        force_kill_action.triggered.connect(self._kill_sim)

        global_settings_action = qg.QAction("Application Settings", self)
        settings_menu.addAction(global_settings_action)
        global_settings_action.triggered.connect(lambda _checked= False, tab= 0: self.open_settings(tab))

        edit_models_action = qg.QAction("Model Settings", self)
        settings_menu.addAction(edit_models_action)
        edit_models_action.triggered.connect(lambda _checked= False, tab= 1: self.open_settings(tab))
        
        edit_parameters_action = qg.QAction("Parameter Settings", self)
        settings_menu.addAction(edit_parameters_action)
        edit_parameters_action.triggered.connect(lambda _checked= False, tab= 2: self.open_settings(tab))

        edit_presets_action = qg.QAction("Preset Settings", self)
        settings_menu.addAction(edit_presets_action)
        edit_presets_action.triggered.connect(lambda _checked= False, tab= 3: self.open_settings(tab))

        edit_controls_action = qg.QAction("Control Panel Settings", self)
        settings_menu.addAction(edit_controls_action)
        edit_controls_action.triggered.connect(lambda _checked= False, tab= 4: self.open_settings(tab))

        edit_plots_action = qg.QAction("Plot Settings", self)
        settings_menu.addAction(edit_plots_action)
        edit_plots_action.triggered.connect(lambda _checked= False, tab= 5: self.open_settings(tab))

        edit_demos_action = qg.QAction("Demo Settings", self)
        settings_menu.addAction(edit_demos_action)
        edit_demos_action.triggered.connect(lambda _checked= False, tab= 6: self.open_settings(tab))

        edit_keybindings_action = qg.QAction("Edit keybindings", self)
        settings_menu.addAction(edit_keybindings_action)
        edit_keybindings_action.triggered.connect(lambda: open_with_default_app(self.env.config_dir / "keybindings.yml"))

        quit_button = qg.QAction("Quit", self)
        file_menu.addAction(quit_button)
        quit_button.triggered.connect(self.close)

        load_saved_axes_action = qg.QAction("Load saved axis settings", self)
        view_menu.addAction(load_saved_axes_action)
        load_saved_axes_action.triggered.connect(self._load_saved_axis_settings)

        save_current_axes_action = qg.QAction("Save current axis settings", self)
        view_menu.addAction(save_current_axes_action)
        save_current_axes_action.triggered.connect(self._save_slot_settings)

        for demo in demos:
            name = demos[demo]["name"]
            demo_options_submenu = demo_menu.addMenu(name)
            demo_options_submenu.setProperty("demo_id", demo)
            load_action = qg.QAction("Load demo", self)
            view_desc_action = qg.QAction("View description", self)
            demo_options_submenu.addAction(load_action)
            demo_options_submenu.addAction(view_desc_action)
            load_action.triggered.connect(lambda _checked= False, name= demo: self.load_demo(name))
            view_desc_action.triggered.connect(lambda _checked= False, name= demo: self.view_demo_desc(name))

        save_preset_action = qg.QAction("Save parameter settings", self)
        save_preset_action.setData("save_preset_action")
        params_menu.addAction(save_preset_action)
        save_preset_action.triggered.connect(self._save_preset)

        save_results_action = qg.QAction("Save current results", self)
        save_results_action.setData("save_results_action")
        results_menu.addAction(save_results_action)
        save_results_action.triggered.connect(self._save_results)

        self.sim_submenus = {}
        self.sim_actions = {}

        return params_menu, results_menu

    def _create_results_submenus(self, results_submenu):
        model_name = self.current_demo["details"]["simulation_model"]
        results_path = Path(self.env.models_dir / model_name / "saved_results")
        if not results_path.exists():
            return

        saved_files = [p for p in results_path.iterdir() if p.is_file() and str(p).endswith(".npz")]
        for file in saved_files:
            result_options_submenu = results_submenu.addMenu(file.stem)
            result_options_submenu.setProperty("result_id", file.stem)

            load_action = qg.QAction("Load results", self)
            delete_action = qg.QAction("Delete data", self)
            rename_action = qg.QAction("Rename", self)
            view_desc_action = qg.QAction("View description", self)

            result_options_submenu.addAction(load_action)
            result_options_submenu.addAction(delete_action)
            result_options_submenu.addAction(rename_action)
            result_options_submenu.addAction(view_desc_action)

            load_action.triggered.connect(lambda _checked= False, filepath= file: self._load_prior_results(filepath))
            delete_action.triggered.connect(lambda _checked= False, filepath= file: self._delete_prior_results(filepath))
            rename_action.triggered.connect(lambda _checked= False, filepath= file: self._rename_prior_results(filepath))
            view_desc_action.triggered.connect(lambda _checked= False, filepath= file: self._view_prior_results_desc(filepath))

    def _create_presets_submenus(self, presets, presets_submenu):
        for preset in presets:
            name = presets[preset]["name"]
            preset_options_submenu = presets_submenu.addMenu(name)
            preset_options_submenu.setProperty("preset_id", preset)
            load_action = qg.QAction("Load preset", self)
            delete_action = qg.QAction("Delete preset", self)
            rename_action = qg.QAction("Rename preset", self)
            view_desc_action = qg.QAction("View description", self)
            preset_options_submenu.addAction(load_action)
            preset_options_submenu.addAction(delete_action)
            preset_options_submenu.addAction(rename_action)
            preset_options_submenu.addAction(view_desc_action)
            load_action.triggered.connect(lambda _checked= False, name= preset: self._load_preset_by_name(name))
            delete_action.triggered.connect(lambda _checked= False, name= preset: self._delete_preset(name))
            rename_action.triggered.connect(lambda _checked= False, name= preset: self._rename_preset(name))
            view_desc_action.triggered.connect(lambda _checked= False, name= preset: self._view_preset_desc(name))

    def _clear_results_menu(self):
        for action in list(self.results_submenu.actions()):
            if action.data() == "save_results_action":
                continue
            submenu = action.menu()
            self.results_submenu.removeAction(action)
            if submenu is not None:
                submenu.deleteLater()

    def _clear_presets_menu(self):
        for action in list(self.presets_submenu.actions()):
            if action.data() == "save_preset_action":
                print(f"continuing")
                continue
            submenu = action.menu()
            self.presets_submenu.removeAction(action)
            if submenu is not None:
                submenu.deleteLater()

    def _refresh_results_menu(self):
        self._clear_results_menu()
        self._create_results_submenus(self.results_submenu)

    def _refresh_presets_menu(self):
        self._clear_presets_menu()
        self._create_presets_submenus(self.presets, self.presets_submenu)

    def _save_results(self):
        if self.traj is None:
            self.status_bar.showMessage("You have no data to save! Run a simulation first.", 3000)
            return

        model_name = self.current_demo["details"]["simulation_model"]
        results_path = self.env.models_dir / model_name / "saved_results"
        existing = {p.stem for p in results_path.glob("*.npz")} if results_path.exists() else set()
        dialog = SaveDialog(existing, title= "Save Results", parent= self)
        try:
            shortname, name, desc, save_axis = dialog.bootstrap()
        except TypeError:
            return

        results_path.mkdir(parents= True, exist_ok= True)

        file_path_npz = results_path / f"{shortname}.npz"
        file_path_yml = results_path / f"{shortname}.yml"

        added_t = False
        if "t" not in self.traj:
            self.traj["t"] = self.t
            added_t = True

        try:
            np.savez_compressed(file_path_npz, **self.traj)
        finally:
            if added_t:
                del self.traj["t"]

        other_settings = {
            "name": name,
            "desc": desc,
            "params": to_plain(self.params)
        }
        if save_axis:
            other_settings["axis_settings"] = self._get_current_axis_settings()
        atomic_write(file_path_yml, other_settings)

        self._refresh_results_menu()
        self.status_bar.showMessage(f"Saved results under name {name}", 3000)

    def _load_prior_results(self, filename):
        if self._sim_state == "RUNNING":
            self._halt_sim_stack()
            self._sim_state = "IDLE"

        model_name = self.demos[self.current_demo_name]["details"]["simulation_model"]
        settings_path = self.env.models_dir / model_name / "saved_results" / f"{filename.stem}.yml"

        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings_dict = yaml.safe_load(f) or {}

            params = settings_dict.get("params")
            raw_axis_settings = settings_dict.get("axis_settings")
            if raw_axis_settings is not None:
                axis_settings = self._get_slot_settings(raw_axis_settings)
            else:
                axis_settings = None
            if params is not None:
                self.params = params_from_mapping(
                    params,
                    self.env.models_dir / self.sim_model / "simulation" / "parameters.py"
                )
                self.load_new_params(axis_settings, start_sim_after= False)

        with np.load(filename, allow_pickle= False) as data:
            t = data["t"]
            traj = {k: data[k] for k in data.files if k != "t"}

        self.show_results(traj, t, None)

    def _delete_prior_results(self, filename):
        model_name = self.demos[self.current_demo_name]["details"]["simulation_model"]
        results_path = self.env.models_dir / model_name / "saved_results"
        npz_filepath = results_path / f"{filename}"
        yml_filepath = results_path / f"{filename.stem}.yml"

        reply = qw.QMessageBox.question(
            self,
            "Confirm deletion",
            f"Delete saved results '{filename.stem}'?",
            qw.QMessageBox.StandardButton.Yes | qw.QMessageBox.StandardButton.No,
            qw.QMessageBox.StandardButton.No,
        )

        if reply != qw.QMessageBox.StandardButton.Yes:
            return

        error_encountered = False
        try:
            npz_filepath.unlink()
            yml_filepath.unlink()
        except OSError as e:
            self.status_bar.showMessage(f"Error encountered when deleting: {e}", 4000)
            error_encountered = True

        self._refresh_results_menu()
        if not error_encountered:
            self.status_bar.showMessage(f"Deleted results: {filename.stem}", 3000)

    def _rename_prior_results(self, filename):
        filepath = Path(filename)
        model_name = self.demos[self.current_demo_name]["details"]["simulation_model"]
        results_path = self.env.models_dir / model_name / "saved_results"
        npz_filepath = filename
        yml_filepath = filename.with_suffix(".yml")

        existing = {p.stem for p in results_path.glob("*.npz")}
        existing.discard(filename.stem)

        dialog = SaveDialog(existing, title= "Rename Results", parent= self)
        try:
            new_shortname, new_name, new_desc, _ = dialog.bootstrap()
        except TypeError:
            return

        with open(yml_filepath, "r") as f:
            other_settings = yaml.safe_load(f)
        
        if new_desc != "":
            other_settings["desc"] = new_desc

        if not npz_filepath.exists():
            self.status_bar.showMessage(f"Error: {npz_filepath} not found.", 3000)
            return

        npz_new_path = results_path / f"{new_shortname}.npz"
        yml_new_path = results_path / f"{new_shortname}.yml"

        filename.rename(npz_new_path)
        atomic_write(yml_new_path, other_settings)

        if yml_filepath.exists() and yml_filepath != yml_new_path:
            yml_filepath.unlink()

        self._refresh_results_menu()

    def start_sim(self, name= None, new_val= None):
        requested_update = None
        if name not in (None, False):
            requested_update = (name, new_val)

        if self._sim_state in {"RUNNING", "STOPPING"}:
            self._queue_rerun(requested_update)

            if self._sim_state == "RUNNING":
                self._sim_state = "STOPPING"
                try:
                    if self.sim_controller is not None:
                        self.sim_controller.request_stop(force= False)
                except Exception:
                        pass

                qc.QTimer.singleShot(1500, self._escalate_stop_if_needed)
                self.status_bar.showMessage("Stop requested... will rerun.", 1500)
            else:
                self.status_bar.showMessage("Stopping... rerun queued.", 1500)
            return

        self._start_sim_now(requested_update)

    def _escalate_stop_if_needed(self):
        if self._sim_state != "STOPPING":
            return


        ctrl = self.sim_controller
        if ctrl is None:
            return

        if ctrl.is_alive():
            self.status_bar.showMessage("Force stopping simulation...", 1500)
            self._halt_sim_stack(force= True, clear_pending= False, clear_queue= True)
            self._sim_state = "IDLE"

            if self._rerun_pending:
                self._rerun_pending = False
                self._start_sim_now()

    def _queue_rerun(self, requested_update= None):
        self._rerun_pending = True
        if requested_update is not None:
            self._pending_restart_update = requested_update

    def _consume_pending_restart_update(self):
        update = self._pending_restart_update
        self._pending_restart_update = None
        if update is not None:
            name, new_val = update
            setattr(self.params, name, new_val)

    def _start_sim_now(self, requested_update= None):
        if requested_update is not None:
            name, new_val = requested_update
            setattr(self.params, name, new_val)
        else:
            self._consume_pending_restart_update()

        self._halt_sim_stack(force= False, clear_pending= True, clear_queue= True)

        self._run_id += 1
        self._rerun_pending = False
        self._sim_state = "RUNNING"

        self.sim_results_queue = self.ctx.Queue(maxsize=0)
        self.sim_controller = SimController(self.ctx, parent= self)
        self.sim_controller.configure(
            self.env,
            run_id= self._run_id,
            model_info= self.current_demo, 
            params= self.params,
            mp_queue= self.sim_results_queue,
            sleep_time= self._sleep_time, 
            yield_every=1, 
        )
        self.sim_controller.start()

        # TODO: should never have listened to the chatbot telling me to take this off of it's own thread, return to a separate QThread
        self.bridge_worker = BridgeWorker(self.sim_results_queue, self._run_id, self.plotting_data, parent= self)
        self.bridge_worker.progress.connect(self._on_worker_progress)
        # self.bridge_worker.done.connect(self._on_sim_thread_finished)
        self.bridge_worker.done.connect(self._on_sim_done)
        self.bridge_worker.error.connect(self._on_sim_error)
        self.bridge_worker.start()

        if self._live_animation:
            self._anim_timer.start()

        self.graph_panel.set_sim_run_id(self._run_id)

    def _on_worker_progress(self, new_data: dict, new_t: dict | float):
        self._pending_traj = new_data
        self._pending_t = new_t

    def _on_sim_done(self):
        self._anim_timer.stop()

        if self._pending_traj is not None:
            self.show_partial_results(self._pending_traj, self._pending_t)
            self.traj, self.t = self._pending_traj, self._pending_t

        self._halt_sim_stack(force= False, clear_pending= False, clear_queue= False)
        self._sim_state = "IDLE"

        self.status_bar.showMessage("Sim completed successfully", 4000)

        if self._rerun_pending:
            self._rerun_pending = False
            self._start_sim_now()

    def _on_sim_thread_finished(self):
        self._halt_sim_stack(force= False, clear_pending= False, clear_queue= False)
        self._sim_state = "IDLE"

        if self._rerun_pending:
            self._rerun_pending = False
            self.start_sim()

    def _on_sim_error(self, msg):
        print(msg)
        if isinstance(msg, str):
            ex_repr = msg
            extra = {}
        else:
            run_id, _tag, ex_repr, tb, module_path, func_name = msg
            extra = {
                "run_id": run_id,
                "module_path": module_path,
                "func_name": func_name,
                "_remote_exc_info": tb,
            }
        logger.log(logging.ERROR, f"Simulation failed: {ex_repr}", extra= extra)
        self._rerun_pending = False
        self._halt_sim_stack(force= True, clear_pending= True, clear_queue= False)
        self._sim_state = "IDLE"

    def show_results(self, traj, t, e):
        self._anim_timer.stop()
        self._pending_traj = None
        self._pending_t = None

        self.traj, self.t = traj, t
        if e != None:
            extra, ex = e
            extra["Model"] = self.sim_model
            extra["Parameters"] = self.params
            self.status_bar.showMessage(f"Simulation failed to complete. Exception caught: {str(ex)}", msecs= 5000)
            logger.log(logging.ERROR, "Simulation failed.", extra= extra, exc_info= ex)
        else:
            self.status_bar.clearMessage()

        # new stuff
        self.graph_panel.traj = traj
        self.graph_panel.t = t

        num_slots = len(self.graph_panel.axes)
        for slot_index in range(num_slots):
            cfg = self.control_panel.get_slot_config(slot_index)
            if cfg is None:
                continue
            dropdown_index, options, legend_cfg = cfg
            self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, legend_cfg)

    def _request_stop_for_rerun(self, force= False):
        try:
            self._anim_timer.stop()
        except Exception:
            pass

        if self.sim_controller is not None:
            self.sim_controller.request_stop(force= force)
            # if force:
            #     self._on_sim_done() # no DONE message if force killed the process

    def closeEvent(self, event):
        try:
            self._halt_sim_stack(force= True, clear_pending= True, clear_queue= False)
            if self.settings.get("autosave_axis_settings", False):
                self._save_slot_settings()
        finally:
            event.accept()

    def _load_preset_by_name(self, name):
        if self._sim_state == "RUNNING":
            self._halt_sim_stack()
            self._sim_state = "IDLE"

        try:
            self.params = params_from_mapping(
                self.presets[name]["params"],
                self.env.models_dir / self.sim_model / "simulation" / "parameters.py"
            )
            raw_axis_settings = self.presets[name].get("axis_settings", {})
            if raw_axis_settings != {}:
                axis_settings = self._get_slot_settings(raw_axis_settings)
            else:
                axis_settings = None
            self.load_new_params(axis_settings)
        except Exception as e:
            self.status_bar.showMessage(f"Failed to load preset {name}: {e}")
            extras = {
                "Model": self.sim_model,
                "Preset": name
            }
            logger.log(logging.ERROR, f"Failed to load preset {name}: {e}", extra= extras, exc_info= e)

    def load_new_params(self, axis_settings= None, start_sim_after= True):
        if axis_settings is not None:
            rows, cols, limits, saved_limits, dropdown_indices, slot_settings, checked = axis_settings
            self.graph_panel.blockSignals(True)
            self.control_panel._alter_slot_layout(rows, cols, limits, saved_limits, dropdown_indices, checked, slot_settings)
            self.graph_panel.blockSignals(False)
            self._set_graph_lims(limits)      
        self.control_panel.load_new_params(self.params)
        if start_sim_after:
            self.start_sim()

    def load_preset(self, preset):
        try:
            self.params = params_from_mapping(
                self.presets[preset]["params"],
                self.env.models_dir / self.sim_model / "simulation" / "parameters.py"
            )
            axis_settings = self.presets[preset].get("axis_settings", {})
            if axis_settings:
                rows, cols, limits, saved_limits, dropdown_indices, slot_settings, checked = self._get_slot_settings(axis_settings)
                self.graph_panel.blockSignals(True)
                self.control_panel._alter_slot_layout(rows, cols, limits, saved_limits, dropdown_indices, checked, slot_settings)
                self.graph_panel.blockSignals(False)
                self._set_graph_lims(limits)
            self.control_panel.load_new_params(self.params)
            self.start_sim()
        except Exception as e:
            self.status_bar.showMessage(f"Failed to load preset {preset}: {e}")
            extras = {
                "Model": self.sim_model,
                "Preset": preset
            }
            logger.log(logging.ERROR, f"Failed to load preset {preset}: {e}", extra= extras, exc_info= e)

    def reload_current_demo(self):
        """
        Reload simulation.py / parameters.py for the current demo
        without changing which demo is active.
        """
        # self._halt_sim_stack(force= False, clear_pending= True, clear_queue= True)
        try:
            demo = self.current_demo

            (
                self.params,
                self.current_sim_func,
                self.presets,
                panel_data,
                plotting_data,
                self.functions,
            ) = self._get_data(demo)

            if plotting_data is None:
                plotting_data = {}

            self._reload_config()
            self._reset_global_settings()

            # Re-apply model-specific formatting
            model_settings = self.config.get("model_specific_settings", {}).get(self.sim_model)
            if model_settings and "commodity_names" in model_settings:
                plotting_data = format_plot_config(
                    plotting_data, model_settings["commodity_names"]
                )

            # Push updated data into existing panels
            self.graph_panel.traj = None
            self.graph_panel.t = None
            self.graph_panel.data = plotting_data
            self.control_panel.plotting_data = plotting_data
            self.control_panel.load_new_params(self.params)
        except Exception as e:
            self.status_bar.showMessage(f"Failed to reload current demo: {e}", msecs= 5000)
            extra = {
                "demo": self.current_demo,
                "params": self.params,
                "sim function": self.current_sim_func,
            }
            logger.log(logging.ERROR, f"Failed to reload current demo: {e}", extra= extra, exc_info= e)

        # Re-run simulation
        self.start_sim()

    def _reload_config(self):
        old_models_dir = self.env.models_dir
        old_log_dir = self.env.log_dir
        old_layout_mode = self.settings.get("figure_mode", "tight")

        try:
            with open(self.env.config_file, "r") as f:
                self.config = yaml.safe_load(f)

            self.settings = self.config["global_settings"]

            new_data_dir = get_user_data_dir(self.settings, self.env)
            # new_models_dir = get_user_models_dir(self.settings, self.env)
            # new_log_dir = get_user_logs_dir(self.settings, self.env)

            self.env.user_data_dir = new_data_dir
            
            self.env.models_dir = new_data_dir / "models"
            self.env.log_dir = new_data_dir / "logs" 
            self.env.demos_file = new_data_dir / "demos.yml"

            with open(self.env.demos_file, "r") as f:
                self.demos = yaml.safe_load(f).get("demos", {})

            self.current_demo = self.demos[self.current_demo_name]

            if old_models_dir != self.env.models_dir:
                refresh_models_path(old_models_dir, self.env.models_dir)

            if old_log_dir != self.env.log_dir:
                from .__main__ import reconfigure_logging
                reconfigure_logging(self.env, self.env.log_dir)
                logger = logging.getLogger(__name__)
                logger.info("Log directory changed at runtime", extra={
                    "old_log_dir": str(old_log_dir),
                    "new_log_dir": str(self.env.log_dir),
                })

        except OSError as e:
            logger.log(logging.ERROR, 'failed to load config.yml!', exc_info= e)
            self.status_bar.showMessage(f"Failed to load config.yml. See logs for more info.", msecs= 5000)

        if self.settings.get("figure_mode", "tight") != old_layout_mode:
            self.apply_figure_layout_mode()


    def apply_figure_layout_mode(self):
        mode = self.settings.get("figure_mode", "tight")

        if mode == "constrained":
            self.figure.set_layout_engine("constrained")
        elif mode == "tight":
            self.figure.set_layout_engine("tight")
        else:
            self.figure.set_layout_engine("none")

        self.canvas.draw_idle()

    def _get_data(self, demo):
        sim_details = demo.get("details")
        if not sim_details:
            self.status_bar.showMessage(f"No details found for {demo} in config.yml!", msecs= 5000)

        sim_model = sim_details.get("simulation_model")
        if not sim_model:
            self.status_bar.showMessage(f"No model specified for {demo} in config.yml!", msecs= 5000)

        presets = self._load_presets(demo)
        sim_function, functions = self._load_functions(demo)
        params = self._load_params(presets, sim_model)

        try:
            with open(self.env.models_dir / sim_model / "data" / "plotting_data.yml") as f:
                plotting_data = yaml.safe_load(f)
        except Exception as e:
            logger.log(logging.ERROR, "Failed to load plotting_data.yml", exc_info= e)
            plotting_data = {}

        try:
            with open(self.env.models_dir / sim_model / "data" / "control_panel_data.yml") as f:
                panel_data = yaml.safe_load(f)
        except Exception as e:
            logger.log(logging.ERROR, "Failed to load control_panel_data.yml", exc_info= e)
            panel_data = {}

        return params, sim_function, presets, panel_data, plotting_data, functions

    def _load_presets(self, demo):
        sim_details = demo.get("details")
        if not sim_details:
            return {}

        sim_model = sim_details.get("simulation_model")
        if not sim_model:
            return {}

        try:
            presets = load_presets(self.env, sim_model)
            return presets
        except Exception as e:
            self.status_bar.showMessage(f"Error loading presets, check logs for more info.")
            logger.log(logging.ERROR, f"Failed to load presets", exc_info= e)

        return {}

    def _load_functions(self, demo):
        sim_model = demo.get("details", {}).get("simulation_model")
        sim_function_name = demo.get("details", {}).get("simulation_function")
        if not sim_function_name:
            self.status_bar.showMessage(f"No model specified for {demo} in config.yml!", msecs= 5000)
            return None, {}

        try:
            module_name = f"models.{sim_model}.simulation.simulation"
            trajectories_module = importlib.import_module(module_name)
            reload_package_folder(trajectories_module)

            functions = {}
            for name, obj in inspect.getmembers(trajectories_module, inspect.isfunction):
                if obj.__module__ == trajectories_module.__name__:
                    functions[name] = obj

            sim_function = getattr(trajectories_module, sim_function_name)
        except Exception as e:
            self.status_bar.showMessage(f"Error loading sim function from module: {e}", 4000)
            logger.log(logging.ERROR, f"Failed to load data", exc_info= e)
            sim_function = None
            functions = {}

        return sim_function, functions

    def _load_params(self, presets, sim_model):
        preset_name = self.current_demo.get("details", {}).get("default_preset", "default_preset")
        preset = presets.get(preset_name)
        if preset is not None:
            params_dict = preset.get("params")
        else:
            params_dict = None
        if params_dict is None and presets != {}:
            preset = presets[next(iter(presets))]
            params_dict = presets.get("params", {})
        if params_dict is None:
            params_dict = {}

        params_module_name = f"models.{sim_model}.simulation.parameters"

        try:
            if params_module_name in sys.modules:
                importlib.reload(sys.modules[params_module_name])
            params = params_from_mapping(
                params_dict,
                self.env.models_dir / self.sim_model / "simulation" / "parameters.py"
            )
        except Exception as e:
            self.status_bar.showMessage(f"Error loading parameters for {sim_model}: {e}", msecs= 5000)
            logger.log(logging.ERROR, f"Failed to load params for {sim_model}", exc_info= e)
            return {}

        return params

    def load_demo(self, demo_name, autostart= True):
        self._halt_sim_stack(force= True, clear_pending= True, clear_queue= True)
        self._sim_state = "IDLE"
        try:
            demo = self.demos[demo_name]
            self.sim_model = demo["details"]["simulation_model"]
            self.params, self.current_sim_func, self.presets, panel_data, plotting_data, functions = self._get_data(demo)

            model_settings = self.config.get("model_specific_settings", {}).get(self.sim_model, None)
        except Exception as e:
            self.status_bar.showMessage(f"Failed to load data for demo: {e}. Check diagnostics in the settings for more info.", msecs= 5000)
            extra = {
                "Demo name": demo_name,
            }
            logger.log(logging.ERROR, "Failed to load demo.", extra= extra, exc_info= e)
            return
        
        if model_settings is not None:
            if "commodity_names" in model_settings:
                com_names = model_settings["commodity_names"]
                plotting_data = format_plot_config(plotting_data, com_names)

        self.traj, self.t = None, None

        # self.presets_submenu.clear()
        # self._create_presets_submenus(self.presets, self.presets_submenu)
        self._clear_presets_menu()
        self._clear_results_menu()

        if self.settings.get("autosave_axis_settings", False):
            self._save_slot_settings()
        saved_state = self.main_splitter.saveState()
        if hasattr(self, "main_splitter") and self.main_splitter is not None:
            for w in (self.control_panel, self.graph_panel):
                try:
                    w.setParent(None)
                    w.deleteLater()
                except Exception:
                    pass

        # --- Reset the figure to a clean single-plot layout ---
        self.figure.clear()
        self.axis = self.figure.add_subplot(1, 1, 1)

        self.graph_panel, self.control_panel, self.dropdown_choices = self._make_panels(plotting_data, panel_data, demo)
        self.current_demo_name = demo_name
        self.current_demo = self.demos[self.current_demo_name]
        self._create_results_submenus(self.results_submenu)
        self._create_presets_submenus(self.presets, self.presets_submenu)

        self._load_saved_axis_settings()

        self.main_splitter.addWidget(self.control_panel)
        self.main_splitter.addWidget(self.graph_panel)

        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 5)

        self.main_splitter.restoreState(saved_state)

        self._sleep_time = demo.get("details", {}).get("simulation_speed", 0)
        self.sim_speed_edit.setText(str(self._sleep_time))

        self.model_label.setText(f"Model: {demo["name"]}")

        if autostart:
            self.start_sim()

    def load_sim(self, func, name):
        print(f"Setting sim function = {func}")
        self.current_sim_func = func
        action = self.sim_actions[name]
        action.setChecked(True)
        self.start_sim()

    def new_model(self):
        NewModelDialog(self).bootstrap()

    def open_settings(self, tab= None):
        dlg = EditConfigDialog(env= self.env, model= self.sim_model, tab= 0 if tab is None else tab, parent= self)
        dlg.configApplied.connect(self._on_config_applied)
        dlg.bootstrap()
        print("reloading config")
        self._reload_config()

    def _on_config_applied(self):
        self._reload_config()

        # 2) rebuild the top menus so demo list / global settings changes appear immediately
        self.menuBar().clear()
        self.presets_submenu, self.results_submenu = self._make_menu(self.presets, self.demos)
        self.refresh_control_panel_and_plots()
        # self.sim_actions[self.get_trajectories.__name__].setChecked(True)

    def refresh_plots(self) -> None:
        """Reload plotting_data.yml for the current model and apply it to the live UI."""
        try:
            with open(self.env.models_dir / self.sim_model / "data" / "plotting_data.yml", "r") as f:
                plotting_data = yaml.safe_load(f) or {}
        except Exception as e:
            self.status_bar.showMessage(f"Failed to reload plotting_data.yml: {e}", msecs= 4000)
            logger.log(logging.ERROR, "Failed to reload plotting_data.yml", exc_info= e)
            return


        # If we have sector/commodity names, apply them to plot labels.
        names = None
        try:
            names = self.current_demo.get("details", {}).get("commodity_names")
        except Exception:
            names = None
        if not names:
            names = getattr(self, "sector_names", None)

        try:
            formatted = format_plot_config(plotting_data, names) if names else plotting_data
        except Exception:
            formatted = plotting_data

        # Update live references
        self.graph_panel.data = formatted
        self.control_panel.plotting_data = formatted

        dropdown_choices, dropdown_tooltips = self._get_dropdown_choices(formatted)
        self.dropdown_choices = dropdown_choices

        # Update GraphPanel dropdown mapping, if present
        if hasattr(self.graph_panel, "dropdown_choices"):
            self.graph_panel.dropdown_choices = dropdown_choices

        # Update ControlPanel dropdowns in-place (so user selections don't get wiped)
        if hasattr(self.control_panel, "dropdown_tooltips"):
            self.control_panel.dropdown_tooltips = dropdown_tooltips

        # Redraw using the current slot configs (new plotting_data may change expressions, labels, etc.)
        try:
            num_slots = len(self.graph_panel.axes)
        except Exception:
            num_slots = 1

        for slot_index in range(num_slots):
            cfg = self.control_panel.get_slot_config(slot_index)
            if cfg is None:
                continue
            dropdown_index, options, slot_cfg = cfg
            self.graph_panel.plot_slot_from_scratch(slot_index, dropdown_index, options, slot_cfg)

        try:
            self.graph_panel.canvas.draw_idle()
        except Exception:
            pass

    def refresh_control_panel_and_plots(self):
        # remembering old settings
        rows = self.control_panel.rows_spinner.value()
        cols = self.control_panel.cols_spinner.value()
        old_limits = [w.get_limits() for w in self.control_panel.slot_axes_controls]
        old_saved_limits = [w.get_saved_limits() for w in self.control_panel.slot_axes_controls]
        old_dropdown_indices = [w.dropdown_choices.currentIndex() for w in self.control_panel.slot_dropdowns]
        old_checked = [w.get_current_checked_boxes() for w in self.control_panel.slot_dropdowns]
        old_slot_settings = []
        for w in self.control_panel.slot_options:
            try:
                old_slot_settings.append(w.get_settings())
            except Exception:
                old_slot_settings.append(None)

        self._reset_global_settings()
        self.refresh_control_panel()
        self.refresh_plots()

        self.control_panel._layout_rebuild_in_progress = True
        self.control_panel.layoutChanged.emit(rows, cols)
        self.control_panel._rebuild_slot_dropdowns(
            rows, cols, 
            old_limits= old_limits, 
            old_dropdown_indices= old_dropdown_indices,
            old_checked=old_checked,
            old_slot_settings=old_slot_settings,
            old_saved_limits=old_saved_limits
        )
        self.control_panel._layout_rebuild_in_progress = False
        self.control_panel.layoutChanged.emit(rows, cols)

        self.status_bar.showMessage("Reloaded panel settings.", msecs= 4000)

    def refresh_control_panel(self) -> None:
        """Rebuild the ControlPanel from control_panel_data.yml (and current plotting_data.yml)."""
        # Snapshot UI state we can reasonably preserve.
        old_cp = getattr(self, "control_panel", None)
        old_current_tab = self.control_panel.content.currentIndex()
        old_sizes = None
        try:
            old_sizes = self.main_splitter.sizes()
        except Exception:
            old_sizes = None

        old_rows = old_cols = None
        old_slot_dropdown_texts = []
        old_slot_axes = []

        try:
            old_rows = int(old_cp.rows_spinner.value())
            old_cols = int(old_cp.cols_spinner.value())
        except Exception:
            pass

        if old_cp is not None:
            try:
                for combo in getattr(old_cp, "slot_dropdowns", []):
                    old_slot_dropdown_texts.append(combo.currentText() if combo is not None else "")
            except Exception:
                old_slot_dropdown_texts = []

            try:
                for i in range(len(getattr(self.graph_panel, "axes", []))):
                    old_slot_axes.append(old_cp.get_slot_axes_limits(i))
            except Exception:
                old_slot_axes = []

        # Reload yaml sources
        try:
            with open(self.env.models_dir / self.sim_model / "data" / "plotting_data.yml", "r") as f:
                plotting_data = yaml.safe_load(f) or {}
        except Exception as e:
            self.status_bar.showMessage(f"Failed to reload plotting_data.yml: {e}", msecs= 4000)
            logger.log(logging.ERROR, "Failed to reload plotting_data.yml", exc_info= e)
            plotting_data = {}
            # return

        try:
            with open(self.env.models_dir / self.sim_model / "data" / "control_panel_data.yml", "r") as f:
                panel_data = yaml.safe_load(f) or {}
        except Exception as e:
            self.status_bar.showMessage(f"Failed to reload control_panel_data.yml: {e}", msecs= 4000)
            logger.log(logging.ERROR, "Failed to reload control_panel_data.yml", exc_info= e)
            panel_data = {}
            # return

        # Apply sector/commodity names to plotting labels (if available)
        names = None
        try:
            names = self.current_demo.get("details", {}).get("commodity_names")
        except Exception:
            names = None
        if not names:
            names = getattr(self, "sector_names", None)

        try:
            formatted = format_plot_config(plotting_data, names) if names else plotting_data
        except Exception:
            formatted = plotting_data

        dropdown_choices, dropdown_tooltips = self._get_dropdown_choices(formatted)

        self.params, _, _, _, _, _ = self._get_data(self.current_demo)

        # Build new panel and wire signals exactly like _make_panels()
        new_cp = ControlPanel(
            self.env,
            self.status_bar,
            self.params,
            dropdown_choices,
            dropdown_tooltips,
            panel_data,
            formatted,
            self.sim_model,
            self.current_demo,
            old_current_tab,
        )
        new_cp.paramChanged.connect(self.start_sim)
        new_cp.layoutChanged.connect(self.on_layout_changed)
        new_cp.slotPlotChoiceChanged.connect(self.on_slot_plot_choice_changed)
        new_cp.slotOptionsChanged.connect(self.on_slot_options_changed)
        new_cp.slotAxesChanged.connect(self.on_slot_axes_changed)
        new_cp.paramsReplaced.connect(self._on_params_replaced)

        # Swap it into the splitter
        try:
            self.main_splitter.replaceWidget(0, new_cp)
        except Exception:
            # Fallback: remove/re-add
            try:
                self.main_splitter.widget(0).setParent(None)
            except Exception:
                pass
            self.main_splitter.insertWidget(0, new_cp)

        if old_cp is not None:
            old_cp.setParent(None)
            old_cp.deleteLater()

        self.control_panel = new_cp
        self.dropdown_choices = dropdown_choices

        # Best-effort restore of rows/cols + per-slot dropdown selections/axes limits
        if old_rows is not None and old_cols is not None:
            try:
                self.control_panel.rows_spinner.setValue(old_rows)
                self.control_panel.cols_spinner.setValue(old_cols)
            except Exception:
                pass

        try:
            for i, txt in enumerate(old_slot_dropdown_texts):
                if not txt:
                    continue
                if txt in dropdown_choices:
                    self.control_panel.set_slot_dropdown_index(i, dropdown_choices.index(txt))
        except Exception:
            pass

        try:
            for i, lims in enumerate(old_slot_axes):
                if lims is None:
                    continue
                xlim, ylim = lims
                self.control_panel.set_slot_axes_limits(i, xlim, ylim)
        except Exception:
            pass

        # Keep splitter size as-is
        if old_sizes:
            try:
                self.main_splitter.setSizes(old_sizes)
            except Exception:
                pass

    def _save_preset(self):
        params_dict = to_plain(self.params)
        dialog = SaveDialog(self.presets.keys(), title= "Save Preset", parent= self)
        try:
            shortname, name, desc, save_axis = dialog.bootstrap()
        except TypeError:
            return

        self.presets[shortname] = {"name": name, "desc": desc, "params": params_dict}
        if save_axis:
            self.presets[shortname]["axis_settings"] = self._get_current_axis_settings()

        presets_dict = {"presets": self.presets}

        atomic_write(self.env.models_dir / self.sim_model / "data" / "params.yml", presets_dict)

        self._refresh_presets_menu()
        self.status_bar.showMessage(f"Saved preset under name {name}", 3000)
        
    def _delete_preset(self, preset, confirm= True):
        if confirm:
            reply = qw.QMessageBox.question(
                self,
                "Confirm deletion",
                f"Really delete preset {preset}?",
                qw.QMessageBox.StandardButton.Yes | qw.QMessageBox.StandardButton.No,
                qw.QMessageBox.StandardButton.No,
            )

            if reply != qw.QMessageBox.StandardButton.Yes:
                return

        del self.presets[preset]
        presets_dict = flow_seqify({"presets": self.presets})

        presets_path = self.env.models_dir / self.sim_model / "data" / "params.yml"

        error_encountered = False
        try:
            atomic_write(presets_path, presets_dict)
        except OSError as e:
            self.status_bar.showMessage(f"Error encountered when deleting: {e}", 4000)
            logger.log(logging.ERROR, f"Error encountered when deleting: {e}", exc_info= e)
            error_encountered = True

        self._refresh_presets_menu()
        if not error_encountered:
            self.status_bar.showMessage(f"Deleted preset {preset}.", 3000)

    def _rename_preset(self, old_shortname):
        dialog = SaveDialog(self.presets.keys(), title= "Rename Preset", parent= self, name_text= "New Name: ", desc_text= "(Optional) New Description")
        try:
            shortname, new_name, new_desc, save_axis= dialog.bootstrap()
        except TypeError:
            return

        preset = self.presets[old_shortname]
        old_name = preset["name"]
        preset["name"] = new_name
        preset["desc"] = new_desc
        if save_axis:
            preset["axis_settings"] = self._get_current_axis_settings()
        self.presets[shortname] = preset
        del self.presets[old_shortname]

        presets_dict = {"presets": self.presets}
        presets_path = self.env.models_dir / self.sim_model / "data" / "params.yml"

        error_encountered = False
        try:
            atomic_write(presets_path, presets_dict)
        except OSError as e:
            self.status_bar.showMessage(f"Error encountered when renaming: {e}", 4000)
            logger.log(logging.ERROR, f"Error encountered when renaming: {e}", exc_info= e)
            error_encountered = True

        self._refresh_presets_menu()
        if not error_encountered:
            self.status_bar.showMessage(f"Renamed preset from {old_name} to {new_name}.", 3000)

    def _view_preset_desc(self, name):
        desc = self.presets[name]["desc"]
        dialog = DescDialog(self, desc)
        dialog.bootstrap()

    def view_demo_desc(self, demo):
        desc = self.demos[demo]["desc"]
        dialog = DescDialog(self, desc)
        dialog.bootstrap()

    def _view_prior_results_desc(self, filename):
        model_name = self.demos[self.current_demo_name]["details"]["simulation_model"]
        settings_path = self.env.models_dir / model_name / "saved_results" / f"{filename.stem}.yml"
        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings_dict = yaml.safe_load(f)
            desc = settings_dict.get("desc", "No description given.")
        else:
            desc = "No description given."
        dialog = DescDialog(self, desc)
        dialog.bootstrap()

