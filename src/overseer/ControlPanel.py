import logging
logger = logging.getLogger(__name__)

from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
import copy
import numpy as np
from matplotlib import pyplot as plt
from .widgets.SectionDivider import SectionDivider
from .widgets.VScrollArea import VScrollArea
from .widgets.EntryBlock import EntryBlock
from .widgets.HelpButton import HelpButton
from .widgets.LatexLabel import LatexLabel
from .widgets.DropdownChoices import DropdownChoices
from .widgets.MatrixEntry import MatrixEntry
from .widgets.AxesControlWidget import AxesControlWidget
from .widgets.SlotControlsWidget import SlotControlsWidget
from .widgets.FilePicker import FilePicker
from dataclasses import asdict
import importlib, inspect

### --- LAYOUT --- ###
# ControlPanel <- QWidget with QVBoxLayout (outer_layout) [
#   QTabWidget (content) [
#       VScrollArea (sim_controls_scroll_area) [ 
#           QWidget with VBoxLayout (sim_controls + sim_control_layout) [
#               Plot control rows as defined in the model
#           ]
#       ]
#       VScrollArea (plot_controls_scroll_area) [ 
#           QWidget with QVBoxLayout (plot_controls + plot_control_layout) [
#               QWidget with QVBoxLayout (preamble_controls + preamble_controls_lay) [
#                   SectionDivider<"Overall Settings">
#                   QHBoxLayout (spinner_row_lay) [
#                       row and column spinners
#                   ]
#               ]
#               QWidget with QVBoxLayout (plot_slot_controls + plot_slot_controls_lay) [
#                 All of the other plot control stuff
#               ]
#           ]
#       ] 
# ]

class ControlPanel(qw.QWidget):
    paramChanged = qc.pyqtSignal(str, object, str, bool)
    layoutChanged = qc.pyqtSignal(int, int)
    slotPlotChoiceChanged = qc.pyqtSignal(int, str)
    slotOptionsChanged = qc.pyqtSignal(int)
    slotAxesChanged = qc.pyqtSignal(int)
    slotAxesCatChanged = qc.pyqtSignal(int)
    paramsReplaced = qc.pyqtSignal(object)
    preProcess = qc.pyqtSignal(object)
    simEvent = qc.pyqtSignal(object)

    def __init__(
            self, env, status_bar, params, 
            dropdown_choices, dropdown_tooltips, 
            panel_data, plotting_data, sim_model, 
            demo, mainwindow, current_tab= 0
    ):
        super().__init__()
        self.block_signals = True
        self.params = params
        self.sim_model = sim_model
        self.plotting_data = copy.deepcopy(plotting_data)
        self._base_plotting_data = copy.deepcopy(plotting_data)
        self.dropdown_tooltips = dropdown_tooltips
        self.panel_data = panel_data if panel_data is not None else {}
        self.dropdown_choices = dropdown_choices
        self.demo = demo
        self.status_bar = status_bar
        self.env = env
        self.main_window = mainwindow

        self.slot_dropdowns = []
        self.slot_options = []
        self.slot_axes_controls = []
        self.slot_titles = {}
        self.entry_blocks = {}
        self.dropdowns = {}
        self.checkboxes = {}
        self.file_pickers = {}
        self.buttons = {}
        self.row_wrappers = []


        self.content = qw.QTabWidget()
        outer_layout = qw.QVBoxLayout(self)
        outer_layout.addWidget(self.content)
        
        sim_controls_scroll_area, plot_controls_scroll_area = self._build_scroll_areas()
        self.content.addTab(sim_controls_scroll_area, "Simulation Controls")
        self.content.addTab(plot_controls_scroll_area, "Plot Controls")

        try:
            extra_functions = importlib.import_module(f"{self.sim_model}.simulation.extra_functions")
            self.extra_functions_dict = dict(inspect.getmembers(extra_functions, inspect.isfunction))
        except Exception:
            self.extra_functions_dict = {}

        plot_controls = self._build_plot_controls_widget()
        try:
            sim_controls = self._build_sim_controls_widget()
        except Exception as e:
            sim_controls = qw.QWidget()
            self.status_bar.showMessage(f"Error building sim controls panel: {e}")
            logger.log(logging.ERROR, f"Error building sim controls panel: {e}", exc_info= e)

        sim_controls_scroll_area.setWidget(sim_controls)
        plot_controls_scroll_area.setWidget(plot_controls)

        for i in range(len(self.slot_dropdowns)):
            self._get_tooltip(i)


        self.content.setCurrentIndex(current_tab)
        self._meta_dependents = self._get_metadeps()

        self.block_signals = False

    def _build_sim_controls_widget(self):
        sim_controls = qw.QWidget()
        sim_controls.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred   # or Expanding
        )
        sim_control_layout = qw.QVBoxLayout(sim_controls)
        sim_control_layout.setContentsMargins(0, 0, 0, 0)
        sim_control_layout.setSpacing(0)

        self._build_sim_controls_from_data(self.panel_data)
        for wrapper in self.row_wrappers:
            sim_control_layout.addWidget(wrapper, alignment= qc.Qt.AlignmentFlag.AlignTop, stretch= 0)
        sim_control_layout.addStretch(1)

        return sim_controls

    def _build_sim_controls_from_data(self, panel_data):
        for row in panel_data:
            preamble_controls = qw.QWidget()
            preamble_controls_lay = qw.QHBoxLayout(preamble_controls)
            preamble_controls_lay.setContentsMargins(0,0,0,0)
            preamble_controls_lay.setSpacing(0)
            preamble_controls.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)

            self.row_wrappers.append(preamble_controls)

            if row[0:7] == "divider":
                if "side" in panel_data[row]:
                    preamble_controls_lay.addWidget(SectionDivider(panel_data[row]["title"], panel_data[row]["side"]))
                else:
                    preamble_controls_lay.addWidget(SectionDivider(panel_data[row]["title"]))
                continue

            for entry_name in panel_data[row]:
                info = panel_data[row][entry_name]
                widget = self.make_widget(entry_name, info, self.params)
                pos = preamble_controls_lay.count()
                preamble_controls_lay.addWidget(widget, stretch= 1, alignment= qc.Qt.AlignmentFlag.AlignTop)

                if info.get("control_type") in "entry_block":
                    self.entry_blocks[entry_name]["row_layout"] = preamble_controls_lay
                    self.entry_blocks[entry_name]["row_index"] = pos
                    self.entry_blocks[entry_name]["panel_info"] = info
                    self.entry_blocks[entry_name]["param_name"] = info["param_name"]

                if info.get("control_type") == "dropdown":
                    self.dropdowns[entry_name]["row_layout"] = preamble_controls_lay
                    self.dropdowns[entry_name]["row_index"] = pos
                    self.dropdowns[entry_name]["panel_info"] = info
                    self.dropdowns[entry_name]["param_name"] = info["param_name"]

                if info.get("control_type") == "checkbox":
                    self.checkboxes[entry_name]["row_layout"] = preamble_controls_lay
                    self.checkboxes[entry_name]["row_index"] = pos
                    self.checkboxes[entry_name]["panel_info"] = info
                    self.checkboxes[entry_name]["param_name"] = info["param_name"]

                if info.get("control_type") == "button":
                    self.buttons[entry_name]["row_layout"] = preamble_controls_lay
                    self.buttons[entry_name]["row_index"] = pos
                    self.buttons[entry_name]["panel_info"] = info

    def _build_plot_controls_widget(self):
        plot_controls = qw.QWidget()
        plot_controls.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred
        )
        plot_control_layout = qw.QVBoxLayout(plot_controls)
        plot_control_layout.setContentsMargins(0,0,0,0)
        plot_control_layout.setSpacing(0)

        preamble_controls = qw.QWidget()
        preamble_controls_lay = qw.QVBoxLayout(preamble_controls)
        preamble_controls_lay.setContentsMargins(8,8,8,8)
        preamble_controls_lay.setSpacing(10)
        preamble_controls_lay.addWidget(SectionDivider("Overall Settings"), alignment= qc.Qt.AlignmentFlag.AlignTop, stretch= 0)
        preamble_controls.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
        spinner_row_lay = qw.QHBoxLayout()
        spinner_row_lay.addWidget(qw.QLabel("Rows:"))
        self.rows_spinner = qw.QSpinBox()
        self.rows_spinner.setRange(1,3)
        self.rows_spinner.setValue(1)
        self.rows_spinner.setSizePolicy(qw.QSizePolicy.Policy.Preferred, qw.QSizePolicy.Policy.Fixed)
        spinner_row_lay.addWidget(self.rows_spinner)
        spinner_row_lay.addSpacing(6)
        spinner_row_lay.addWidget(qw.QLabel("Columns:"))
        self.cols_spinner = qw.QSpinBox()
        self.cols_spinner.setRange(1,3)
        self.cols_spinner.setValue(1)
        self.cols_spinner.setSizePolicy(qw.QSizePolicy.Policy.Preferred, qw.QSizePolicy.Policy.Fixed)
        spinner_row_lay.addWidget(self.cols_spinner)
        preamble_controls_lay.addLayout(spinner_row_lay)
        self.rows_spinner.valueChanged.connect(self._emit_plot_dim_change)
        self.cols_spinner.valueChanged.connect(self._emit_plot_dim_change)
        plot_control_layout.addWidget(preamble_controls, alignment= qc.Qt.AlignmentFlag.AlignTop, stretch= 0)

        self.plot_slot_controls = qw.QWidget()
        self.plot_slot_controls_lay = qw.QVBoxLayout(self.plot_slot_controls)
        self.plot_slot_controls.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
        self.plot_slot_controls_lay.setContentsMargins(0,0,0,0)
        self.plot_slot_controls_lay.setSpacing(0)

        plot_control_layout.addWidget(self.plot_slot_controls, qc.Qt.AlignmentFlag.AlignTop)
        plot_control_layout.addStretch(1)

        return plot_controls

    def _build_scroll_areas(self):
        scroll_main = VScrollArea()
        scroll_main.setWidgetResizable(True)
        scroll_main.setHorizontalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_main.setVerticalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
   
        scroll_plot = VScrollArea()
        scroll_plot.setWidgetResizable(True)
        scroll_plot.setHorizontalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_plot.setVerticalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        return scroll_main, scroll_plot

    def _collect_metadeps_from_info(self, widget_name, info, meta_deps):
        control_type = info.get("control_type", "")

        if control_type == "entry_block":
            if "dim_from" in info:
                meta_deps.add(widget_name)

        elif control_type == "dropdown":
            if "names_from" in info:
                meta_deps.add(widget_name)
            if "values_from" in info:
                meta_deps.add(widget_name)

        elif control_type.startswith("hsub_panel"):
            for widget_name, subinfo in info.get("entries", {}).items():
                self._collect_metadeps_from_info(widget_name, subinfo, meta_deps)

        elif control_type.startswith("vsub_panel"):
            for widget_name, subinfo in info.get("entries", {}).items():
                self._collect_metadeps_from_info(widget_name, subinfo, meta_deps)
                    
    def _get_metadeps(self):
        meta_deps = set()
        for row_name, row in self.panel_data.items():
            if row_name.startswith("divider"):
                continue
            for widget_name, info in row.items():
                self._collect_metadeps_from_info(widget_name, info, meta_deps)
        return meta_deps

    def set_slot_dropdown_index(self, slot_index: int, idx: int):
        if 0 <= slot_index < len(self.slot_dropdowns):
            self.slot_dropdowns[slot_index].dropdown_choices.setCurrentIndex(idx)

    def set_slot_axes_limits(self, slot_index: int, xlim, ylim, zlim= None):
        """ Update the axes for a given slot """
        if 0 <= slot_index < len(self.slot_axes_controls):
            self.slot_axes_controls[slot_index].set_limits(xlim, ylim, zlim)

    def set_slot_title(self, slot_index: int, title: str) -> None:
        if title is None or str(title).strip() == "":
            self.slot_titles.pop(slot_index, None)
        else:
            self.slot_titles[slot_index] = str(title)
        self.slotOptionsChanged.emit(slot_index)

    def _rebuild_slot_dropdowns(self, rows, cols, old_limits= None, old_dropdown_indices= None, old_checked= None, old_slot_settings= None, old_saved_limits= None):
        """ Destroy and rebuild all control widgets for individual plots (or build for the first time) """
        for i in reversed(range(self.plot_slot_controls_lay.count())):
            item = self.plot_slot_controls_lay.takeAt(i)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self.slot_dropdowns.clear()
        self.slot_options.clear()
        self.slot_axes_controls.clear()

        num_slots = rows * cols
        for slot_index in range(num_slots):

            # magic
            r = slot_index // cols
            c = slot_index % cols
            section_divider = SectionDivider(f"Axis ({r+1},{c+1})")

            dropdown = DropdownChoices()
            dropdown.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
            dropdown.addItems(self.dropdown_choices)
            dropdown_layout = qw.QVBoxLayout()

            for dropdown_choice in self.plotting_data:
                choice_dict = self.plotting_data[dropdown_choice]
                plots = choice_dict["plots"]
                for plot in plots:
                    plot_dict = plots[plot]
                    if "checkbox_name" in plot_dict:
                        dropdown.add_checkbox(choice_dict["name"], plot_dict["checkbox_name"], plot_dict["toggled"])

            if len(self.dropdown_choices) > 0:
                if (
                    old_dropdown_indices is not None
                    and slot_index < len(old_dropdown_indices)
                    and old_dropdown_indices[slot_index] is not None
                    and old_dropdown_indices[slot_index] >= 0
                ):
                    dropdown_idx = min(old_dropdown_indices[slot_index], len(self.dropdown_choices) - 1)
                else:
                    dropdown_idx = 0

                dropdown_choice = self._get_inter_name_from_name(self.dropdown_choices[dropdown_idx])
                choice_dict = self.plotting_data.get(dropdown_choice, {})
                projection = choice_dict.get("projection", "2d")
            else:
                dropdown_idx = 0
                projection = "2d"

            z_axis = (projection == "3d")
            default_font = self._auto_fontsize(rows, cols)
            options_widget = SlotControlsWidget()
            options_widget.legend_size_spin.setValue(default_font)
            if isinstance(old_saved_limits, list) and slot_index <= len(old_saved_limits)-1:
                axes_widget = AxesControlWidget(saved_limits= old_saved_limits[slot_index], z_axis= z_axis)
            else:
                axes_widget = AxesControlWidget(z_axis= z_axis)

            self.plot_slot_controls_lay.addWidget(section_divider)
            self.plot_slot_controls_lay.addWidget(SectionDivider("Settings", alignment= "left"))
            self.plot_slot_controls_lay.addWidget(axes_widget)
            self.plot_slot_controls_lay.addWidget(options_widget)
            self.plot_slot_controls_lay.addWidget(dropdown)

            self.slot_dropdowns.append(dropdown)
            self.slot_options.append(options_widget)
            self.slot_axes_controls.append(axes_widget)

            dropdown.currentIndexChanged.connect(lambda idx, s=slot_index: self._on_dropdown_changed(idx, s))
            dropdown.checkStateChanged.connect(lambda s=slot_index, source= "checkbox": self.slotPlotChoiceChanged.emit(s, source))
            dropdown.infoBoxHovered.connect(lambda s=slot_index: self._on_info_hovered(s))
            options_widget.settingsChanged.connect(lambda s=slot_index: self.slotOptionsChanged.emit(s))
            axes_widget.settingsChanged.connect(lambda s=slot_index: self.slotAxesChanged.emit(s))
            axes_widget.catSettingsChanged.connect(lambda s=slot_index: self._on_slot_axes_cat_save_request(s))
    
        if old_limits is not None:
            for i, lims in enumerate(old_limits):
                if i >= len(self.slot_axes_controls):
                    break
                if lims is None:
                    continue
                if len(lims) == 2:
                    xlim, ylim = lims
                    if xlim is None or ylim is None:
                        continue
                    self.slot_axes_controls[i].set_limits(xlim, ylim)
                elif len(lims) == 3:
                    xlim, ylim, zlim = lims
                    if xlim is None or ylim is None or zlim is None:
                        continue
                    self.slot_axes_controls[i].set_limits(xlim, ylim, zlim)

            last_valid = None
            for lims in reversed(old_limits):
                if lims is not None and lims[0] is not None and lims[1] is not None:
                    last_valid = lims
                    break

            if last_valid is not None:
                if len(last_valid) == 3:
                    xlim0, ylim0, zlim0 = last_valid
                else:
                    xlim0, ylim0 = last_valid
                    zlim0 = None
                for i in range(len(old_limits), len(self.slot_axes_controls)):
                    self.slot_axes_controls[i].set_limits(xlim0, ylim0, zlim0)

        if old_dropdown_indices is not None:
            # 1) Restore existing slots
            for i, idx in enumerate(old_dropdown_indices):
                if i >= len(self.slot_dropdowns):
                    break
                if idx is None:
                    continue
                if idx < 0:
                    continue
                idx = min(idx, len(self.dropdown_choices) - 1) # safeguard in case user deleted a category
                self.slot_dropdowns[i].dropdown_choices.setCurrentIndex(idx)

                if i < len(self.slot_axes_controls):
                    projection = self._get_slot_projection(idx)
                    self.slot_axes_controls[i].set_projection(projection)

            # 2) For new slots, copy from last existing choice
            last_idx = None
            for idx in reversed(old_dropdown_indices):
                if idx is not None and idx >= 0:
                    last_idx = min(idx, len(self.dropdown_choices)-1)
                    break

            if last_idx is not None:
                for i in range(len(old_dropdown_indices), len(self.slot_dropdowns)):
                    self.slot_dropdowns[i].dropdown_choices.setCurrentIndex(last_idx)

                    if i < len(self.slot_axes_controls):
                        projection = self._get_slot_projection(last_idx)
                        self.slot_axes_controls[i].set_projection(projection)

        # restore checkbox choices
        if old_checked is not None:
            for i, checked in enumerate(old_checked):
                if i >= len(self.slot_dropdowns):
                    break
                if checked is None:
                    continue
                dd = self.slot_dropdowns[i]
                if hasattr(dd, "set_checked_boxes"):
                    try:
                        dd.set_checked_boxes(checked)
                        continue
                    except Exception:
                        pass
                # Otherwise, try common internal shapes: dict name->QCheckBox
                for attr_name in ("checkboxes", "check_boxes", "checkbox_widgets"):
                    box_map = getattr(dd, attr_name, None)
                    if isinstance(box_map, dict):
                        for name, box in box_map.items():
                            try:
                                box.blockSignals(True)
                                box.setChecked(name in checked)
                                box.blockSignals(False)
                            except Exception:
                                pass
                        break

            # for new slots, copy from last existing choice
            last_checked = None
            for checked in reversed(old_checked):
                if checked is not None:
                    last_checked = checked
                    break

            if last_checked is not None:
                for i in range(len(old_checked), len(self.slot_dropdowns)):
                    dd = self.slot_dropdowns[i]
                    if hasattr(dd, "set_checked_boxes"):
                        try:
                            dd.set_checked_boxes(last_checked)
                            continue
                        except Exception:
                            pass
                    for attr_name in ("checkboxes", "check_boxes", "checkbox_widgets"):
                        box_map = getattr(dd, attr_name, None)
                        if isinstance(box_map, dict):
                            for name, box in box_map.items():
                                try:
                                    box.blockSignals(True)
                                    box.setChecked(name in last_checked)
                                    box.blockSignals(False)
                                except Exception:
                                    pass
                            break

        if old_slot_settings is not None:
            for i, settings in enumerate(old_slot_settings):
                if i >= len(self.slot_options):
                    break
                if settings is None:
                    continue

                w = self.slot_options[i]
                # Try a generic setter first if present
                if hasattr(w, "set_settings"):
                    w.blockSignals(True)
                    w.set_settings(settings)
                    w.blockSignals(False)

    def _on_slot_axes_cat_save_request(self, slot_index):
        cfg = self.get_slot_config(slot_index)
        lims = self.get_slot_axes_limits(slot_index)
        dropdown_index = cfg[0]

        dropdown_list = list(self.plotting_data)
        dropdown_name = dropdown_list[dropdown_index]
        
        self.plotting_data[dropdown_name]["default_lims"] = lims
        self.main_window.graph_panel.data[dropdown_name]["default_lims"] = lims
        self.slotAxesCatChanged.emit(slot_index)

    def _get_inter_name_from_name(self, name):
        for inter_name, plot_dict in self.plotting_data.items():
            if plot_dict["name"] == name:
                return inter_name

    def _on_info_hovered(self, slot_index: int):
        self._get_tooltip(slot_index)

    def _normalize_slot_settings(self, settings: dict) -> dict:
        if not settings:
            return {}

        out = dict(settings)

        # Legend settings
        if "visible" in out:
            out["legend_visible"] = out.pop("visible")

        if "fontsize" in out:
            out["legend_fontsize"] = out.pop("fontsize")

        if "loc" in out:
            out["legend_loc"] = out.pop("loc")

        return out

    def _get_slot_projection(self, idx):
        keys = list(self.plotting_data.keys())
        try:
            choice_name = keys[idx]
        except IndexError:
            return "2d"
        choice_dict = self.plotting_data.get(choice_name, {})
        projection = choice_dict.get("projection", "2d")

        return projection

    def _on_dropdown_changed(self, idx: int, slot_index: int):
        self._get_tooltip(slot_index)

        projection = self._get_slot_projection(idx)
        self.slot_axes_controls[slot_index].set_projection(projection)

        self.slotPlotChoiceChanged.emit(slot_index, "dropdown")

    def get_slot_axes_limits(self, slot_index: int):
        """ return (xlim, ylim) for a given slot """
        if slot_index < 0 or slot_index >= len(self.slot_axes_controls):
            return None
        return self.slot_axes_controls[slot_index].get_limits()

    def get_slot_settings(self):
        rows = self.rows_spinner.value()
        cols = self.cols_spinner.value()

        limits = [w.get_limits() for w in self.slot_axes_controls]
        saved_limits = [w.get_saved_limits() for w in self.slot_axes_controls]
        dropdown_indices = [w.dropdown_choices.currentIndex() for w in self.slot_dropdowns]
        checked = [w.get_current_checked_boxes() for w in self.slot_dropdowns]
        slot_settings = []
        for w in self.slot_options:
            try:
                slot_settings.append(w.get_settings())
            except Exception:
                slot_settings.append(None)

        return rows, cols, limits, saved_limits, dropdown_indices, checked, slot_settings

    def _emit_plot_dim_change(self):

        rows, cols, old_limits, old_saved_limits, old_dropdown_indices, old_checked, old_slot_settings = self.get_slot_settings()
        self._layout_rebuild_in_progress = True
        self.layoutChanged.emit(rows, cols) # this redundancy was necessary at some point I think, I can't remember what wasn't working without it
        self._rebuild_slot_dropdowns(
            rows, cols, 
            old_limits= old_limits, 
            old_dropdown_indices= old_dropdown_indices,
            old_checked=old_checked,
            old_slot_settings=old_slot_settings,
            old_saved_limits=old_saved_limits
        )

        self._layout_rebuild_in_progress = False
        self.layoutChanged.emit(rows, cols)

    def _alter_slot_layout(self, rows, cols, limits= [], saved_limits= [], dropdown_indices= [], checked= [], slot_settings= []):
        self._layout_rebuild_in_progress = True
        self.layoutChanged.emit(rows, cols)
        self._rebuild_slot_dropdowns(
            rows, cols,
            old_limits= limits,
            old_dropdown_indices= dropdown_indices,
            old_checked= checked,
            old_saved_limits= saved_limits,
            old_slot_settings= slot_settings,
        )
        self._layout_rebuild_in_progress = False
        self.rows_spinner.blockSignals(True)
        self.cols_spinner.blockSignals(True)
        self.rows_spinner.setValue(rows)
        self.cols_spinner.setValue(cols)
        self.rows_spinner.blockSignals(False)
        self.cols_spinner.blockSignals(False)

        self.layoutChanged.emit(rows, cols)

    def make_widget(self, entry_name, info, params):
        control_type = info["control_type"]

        if control_type == "checkbox":
            w = self._build_checkbox(entry_name, info, params)
            return w

        elif control_type == "dropdown":
            w = self._build_dropdown(entry_name, info, params)
            return w
        
        elif control_type == "button":
            w = self._build_button(entry_name, info)
            return w

        elif control_type == "entry_block": 
            w = self._build_entry_block(entry_name, info, params)
            return w

        elif control_type == "file_picker":
            w = self._build_file_path_entry(entry_name, info, params)
            return w

        elif control_type[0:10] == "vsub_panel":
            w = self._build_sub_panel(entry_name, info, params, orientation= "v")
            return w

        elif control_type[0:10] == "hsub_panel":
            w = self._build_sub_panel(entry_name, info, params, orientation= "h")
            return w

        else:
            print("Unrecognized control type.")
            return qw.QWidget()

    def _build_file_path_entry(self, entry_name, info, params) -> qw.QWidget:
        param_name, label, tooltip_plain = (
            info["param_name"], info['label'], info['tooltip']
        )
        mode = info.get("mode", "folder")
        tooltip = f"""{tooltip_plain}"""
        change_effect = info.get("change_effect", "restart")

        row_widget = qw.QWidget()
        row_layout = qw.QHBoxLayout(row_widget)
        widget = FilePicker(mode= mode)

        if hasattr(params, param_name):
            init_val = getattr(params, param_name)
            widget.setText(init_val)

        widget.pathChanged.connect(
            lambda path, pm= param_name, en= entry_name:
                self.update_plot(pm, path, widget_changed= en)

        )

        row_layout.addWidget(qw.QLabel(label))
        row_layout.addWidget(widget)
        row_layout.addWidget(HelpButton("?", tooltip), stretch= 0)
        self.file_pickers[entry_name] = {
            "widget": widget,
            "param_name": param_name,
            "change_effect": change_effect
        }


        return row_widget

    def _build_checkbox(self, entry_name, info, params) -> qw.QWidget:
        param_name, label, tooltip_plain = (
            info["param_name"], info['label'], info['tooltip']
        )
        tooltip = f"""{tooltip_plain}"""
        change_effect = info.get("change_effect", "restart")

        row_widget = qw.QWidget()
        row_layout = qw.QHBoxLayout(row_widget)
        widget = qw.QCheckBox(label)
        if hasattr(params, param_name):
            init_val = getattr(params, param_name)
            widget.setChecked(init_val)
        widget.setToolTip(tooltip)
        widget.checkStateChanged.connect(
            lambda state, pm= param_name, en= entry_name:
                self.update_plot(pm, state == qc.Qt.CheckState.Checked, widget_changed= en)
        )

        row_layout.addWidget(HelpButton("?", tooltip), stretch=0)
        row_layout.addWidget(widget)
        self.checkboxes[entry_name] = {"widget": widget, "change_effect": change_effect}

        return row_widget

    def _resolve_dropdown_names_and_vals(self, info):
        use_names_func = info.get("use_names_func", False)
        use_vals_func = info.get("use_vals_func", False)

        if use_names_func:
            func_name = info.get("names_from")
            if func_name is None:
                raise ValueError(f"Error: no name function specified")
            if func_name not in self.extra_functions_dict:
                raise ValueError(f"Error: parameter defined by function {func_name} not found in extra_functions.py")

            function = self.extra_functions_dict[func_name]
            try:
                names = function(self.params)
            except Exception as e:
                ValueError(f"Error while calculating new value for parameter with function {func_name}: {e}")
        else:
            names = info.get("names")
            if names is None:
                raise ValueError("Error, no names for dropdown found")

        if use_vals_func:
            func_name = info.get("values_from")
            if func_name is None:
                raise ValueError(f"Error: no value function specified")
            if func_name not in self.extra_functions_dict:
                raise ValueError(f"Error: parameter defined by function {func_name} not found in extra_functions.py")

            function = self.extra_functions_dict[func_name]
            try:
                values = function(self.params)
            except Exception as e:
                ValueError(f"Error while calculating new value for parameter with function {func_name}: {e}")
        else:
            values = info.get("values")
            if values is None:
                raise ValueError("Error, no values for dropdown found")

        return names, values

    def _build_dropdown(self, entry_name, info, params, replacing= False) -> qw.QWidget:
        outer_widget = qw.QWidget()
        outer_layout = qw.QVBoxLayout(outer_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(2)

        param_name, label, tooltip_plain = (
            info["param_name"], info["label"], info["tooltip"]
        )
        change_effect = info.get("change_effect", "restart")
        tooltip = f"""{tooltip_plain}"""
        names, values = self._resolve_dropdown_names_and_vals(info)

        label_widget = qw.QLabel(label)
        label_widget.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred
        )
        outer_layout.addWidget(label_widget, alignment = qc.Qt.AlignmentFlag.AlignCenter)

        top_row = qw.QWidget()
        row_layout = qw.QHBoxLayout(top_row)
        row_layout.setContentsMargins(5, 0, 5, 0)
        row_layout.setSpacing(0)

        dropdown = qw.QComboBox()
        dropdown.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)

        def no_wheel(event):
            event.ignore()
        dropdown.wheelEvent = no_wheel

        for name in names:
            dropdown.addItem(name)

        if hasattr(params, param_name):
            init_val = getattr(params, param_name)
            try:
                dropdown.setCurrentIndex(values.index(init_val))
            except ValueError:
                dropdown.setCurrentIndex(values.index(str(init_val)))
            
        dropdown.currentIndexChanged.connect(
            lambda idx, pn=param_name, vals=values, en= entry_name: self.update_plot(pn, vals[idx], widget_changed= en)
        )

        row_layout.addWidget(dropdown, stretch=1, alignment= qc.Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(HelpButton("?", tooltip), stretch=0)

        outer_layout.addWidget(top_row, alignment= qc.Qt.AlignmentFlag.AlignTop)

        if not replacing:
            self.dropdowns[entry_name] = {"widget": outer_widget, "dropdown": dropdown, "values": values, "change_effect": change_effect}
        else:
            self.dropdowns[entry_name]["dropdown"] = dropdown
            self.dropdowns[entry_name]["values"] = values
            self.dropdowns[entry_name]["change_effect"] = change_effect
        return outer_widget

    def _build_button(self, entry_name, info) -> qw.QWidget:
        button_name, function_name, tooltip_plain = info["name"], info["function"], info["tooltip"]
        tooltip = f"""{tooltip_plain}"""
        info_button = HelpButton("?", tooltip)
        button_wrapper = qw.QWidget()
        button_lay = qw.QHBoxLayout(button_wrapper)
        button = qw.QPushButton(button_name)
        button_lay.addWidget(button)
        button_lay.setContentsMargins(3, 15, 3, 15)
        button_lay.setSpacing(2)

        extra_functions_module = importlib.import_module(f"{self.sim_model}.simulation.extra_functions")

        action_type = info.get("action_type", "replace_params")
        functions_dict = dict(inspect.getmembers(extra_functions_module, inspect.isfunction))
        try:
            function = functions_dict[function_name]
        except ValueError:
            self.status_bar.showMessage(f"Error loading function: {function_name}. Skipping button", 3000)
            logger.log(logging.WARNING, f"Error loading function: {function_name}. Skipping button")

        def outer_func(_checked= False, action_type= action_type):
            try:
                result = function(self.params, self.env)
            except Exception as e:
                self.status_bar.showMessage(f"Error executing {function_name}: {e}", 3000)
                logger.log(logging.ERROR, f"Failed to resolve matrix dim entry", exc_info= e)
                return

            if result is None:
                return

            match action_type:
                case "replace_params":
                    self.params = result
                    self.load_new_params() 
                    self._apply_plot_preprocessing()
                    self.paramsReplaced.emit(result)

                case "sim_event":
                    print("emitting")
                    self.simEvent.emit(result)

        button.clicked.connect(outer_func)
        button_lay.addWidget(info_button)
        self.buttons[entry_name] = {"widget": button}
        return button_wrapper

    def _build_entry_block(self, entry_name, info, params, replacing= False, dim= None, init_val= None) -> qw.QWidget:
        param_name, label, tooltip_plain = info["param_name"], info["label"], info["tooltip"]
        change_effect = info.get("change_effect", "restart")
        tooltip = f"""{tooltip_plain}"""
        if init_val is None:
            if hasattr(params, param_name):
                init_val = getattr(params, param_name)
            else:
                init_val = -1

        if info["type"] == "scalar":
            scalar_range, scalar_type = tuple(info["range"]), info["scalar_type"]
            widget = EntryBlock(param_name, label, scalar_range, init_val, tooltip, scalar_type)
            if not replacing: 
                self.entry_blocks[entry_name] = {"widget": widget, "is_matrix": False, "change_effect": change_effect}
            widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
            widget.valueChanged.connect(
                lambda name, new_val, en= entry_name:
                    self.update_plot(name, new_val, widget_changed= en)
            )

        elif info["type"] == "matrix":
            if dim is None:
                try: 
                    dim = self._resolve_entry_dim(info)
                except Exception as e:
                    logger.log(logging.ERROR, f"Failed to resolve matrix dim entry", exc_info= e)
                    self.status_bar.showMessage(f"Failed to resolve matrix dim entry", 3000)
                    dim = [1,1]
            widget = MatrixEntry(param_name, label, dim, init_val, tooltip)
            widget.textChanged.connect(
                lambda name, new_val, en= entry_name:
                    self.update_plot(name, new_val, widget_changed= en)
            )
            if "vsize_policy" in info:
                if info["vsize_policy"] == "expanding":
                    widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Minimum)
            else:
                widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)
            if not replacing: 
                self.entry_blocks[entry_name] = {"widget": widget, "is_matrix": True, "change_effect": change_effect}
            
        elif info["type"] == "vector":
            if dim is None:
                try:
                    dim = self._resolve_entry_dim(info)
                    if isinstance(dim, int):
                        num = dim
                        dim = [num, 1]
                except Exception as e:
                    logger.log(logging.ERROR, f"Failed to resolve matrix dim entry", exc_info= e)
                    self.status_bar.showMessage(f"Failed to resolve matrix dim entry", 3000)
                    dim = [1,1]

            try:
                reshaped_init_val = init_val.reshape(-1,1)
            except AttributeError as e:
                logger.log(logging.ERROR, f"Coordinate {init_val} is not a proper vector!", exc_info= e)
                if self.status_bar is not None:
                    self.status_bar.showMessage(f"Coordinate {init_val} is not a proper vector!", 3000)
                dim = [1,1]
                reshaped_init_val = np.array([1])

            widget = MatrixEntry(param_name, label, dim, reshaped_init_val, tooltip)
            widget.textChanged.connect(
                lambda name, new_val, en= entry_name:
                    self.update_plot(name, new_val, widget_changed= en)
            )
            widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
            if not replacing:
                self.entry_blocks[entry_name] = {"widget": widget, "is_matrix": True, "change_effect": change_effect}
        else:
            print(f"Unrecognized type: {info["type"]}. Options for type are scalar, vector, and matrix.")
            return qw.QWidget()

        return widget

    def _build_sub_panel(self, entry_name, info, params, orientation= "v") -> qw.QWidget:
        widget = qw.QWidget()
        if orientation == "v":
            layout = qw.QVBoxLayout(widget)
        elif orientation == "h":
            layout = qw.QHBoxLayout(widget)
        else:
            print(f"Unrecognized sub-panel orientation.")
            return qw.QWidget()

        widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)

        subentries = info["entries"]
        for entry in subentries:
            subinfo = subentries[entry]
            subwidget = self.make_widget(entry, subinfo, params)
            pos = layout.count()
            layout.addWidget(subwidget)

            if subinfo.get("control_type") == "entry_block":
                self.entry_blocks[entry]["row_layout"] = layout
                self.entry_blocks[entry]["row_index"] = pos
                self.entry_blocks[entry]["panel_info"] = subinfo
                self.entry_blocks[entry]["param_name"] = subinfo["param_name"]

            if subinfo.get("control_type") == "dropdown":
                self.dropdowns[entry]["row_layout"] = layout
                self.dropdowns[entry]["row_index"] = pos
                self.dropdowns[entry]["panel_info"] = subinfo
                self.dropdowns[entry]["param_name"] = subinfo["param_name"]

            if subinfo.get("control_type") == "checkbox":
                self.checkboxes[entry]["row_layout"] = layout
                self.checkboxes[entry]["row_index"] = pos
                self.checkboxes[entry]["panel_info"] = subinfo
                self.checkboxes[entry]["param_name"] = subinfo["param_name"]

            if subinfo.get("control_type") == "button":
                self.buttons[entry]["row_layout"] = layout
                self.buttons[entry]["row_index"] = pos
                self.buttons[entry]["panel_info"] = subinfo

        return widget

    def _resize_vector(self, old, new_dim: int, safe_default=None) -> np.ndarray:
        """ Returns what the updated array should be to populate an updated vector widget with """
        try:
            old_arr = np.asarray(old, dtype=float).reshape(-1)
        except Exception:
            old_arr = np.zeros((0,), dtype=float)

        new = np.zeros((new_dim,), dtype=float)

        m = min(old_arr.shape[0], new_dim)
        if m > 0:
            new[:m] = old_arr[:m]

        if safe_default is not None and new_dim > old_arr.shape[0]:
            new[old_arr.shape[0]:] = safe_default


        return new

    def _resize_matrix(self, old, row: int, col: int, safe_default=None) -> np.ndarray:
        try:
            old_arr = np.asarray(old, dtype=float)
        except Exception:
            old_arr = np.zeros((0, 0), dtype=float)

        if old_arr.ndim != 2:
            old_arr = np.atleast_2d(old_arr)

        new = np.zeros((row, col), dtype=float)

        r = min(old_arr.shape[0], row)
        c = min(old_arr.shape[1], col)

        if r > 0 and c > 0:
            new[:r, :c] = old_arr[:r, :c]

        if safe_default is not None:
            if row > old_arr.shape[0]:
                new[old_arr.shape[0]:, :] = safe_default

            if col > old_arr.shape[1]:
                new[:, old_arr.shape[1]:] = safe_default

        return new

    def _resolve_entry_dim(self, info) -> tuple[int, int] | int:
        dim = info.get("dim")
        dim_from = info.get("dim_from")

        use_dim_func = info.get("use_dim_func", False)
        if use_dim_func: 
            if dim_from is None:
                raise ValueError("Error, no dimension function specified.")
            func_name = info.get("dim_from")
            if func_name not in self.extra_functions_dict:
                raise ValueError(f"Error: parameter defined by function {func_name} not found in extra_functions.py")
            function = self.extra_functions_dict[func_name]
            try:
                dim = function(self.params)
            except Exception as e:
                raise ValueError(f"Error while calculating new value for parameter with function {func_name}: {e}")
        else:
            if dim is None:
                raise ValueError("Error, no dimension specified.")

        return dim

    def _apply_meta_changes_entry(self, widget_name: str) -> None:
        entry_info = self.entry_blocks[widget_name]["panel_info"]

        if "dim_from" in entry_info:
            new_val, new_dim = self._get_new_resized_param_val(widget_name, entry_info)
            param_name = entry_info["param_name"]
            setattr(self.params, param_name, new_val)

            self.block_signals = True
            try: 
                new_widget = self._build_entry_block(widget_name, entry_info, self.params, replacing= True, dim= new_dim, init_val= new_val)
                self._replace_widget(widget_name, new_widget, "entry")
            finally:
                self.block_signals = False

    def _apply_meta_changes_dropdown(self, widget_name: str) -> None:
        dropdown_info = self.dropdowns[widget_name]["panel_info"]

        if "names_from" in dropdown_info or "values_from" in dropdown_info:
            self.block_signals = True
            try:
                new_widget = self._build_dropdown(widget_name, dropdown_info, self.params, replacing= True)
                self._replace_widget(widget_name, new_widget, "dropdown")
            finally:
                self.block_signals = False

    def _get_new_resized_param_val(self, metaparam_name, info):
        func_name = info.get("dim_from")
        if func_name not in self.extra_functions_dict:
            raise ValueError(f"Error: parameter defined by function {func_name} not found in extra_functions.py")
        function = self.extra_functions_dict[func_name]
        try:
            dim = function(self.params)
        except Exception as e:
            raise ValueError(f"Error while calculating new value for parameter with function {func_name}: {e}")

        entry_type = info["type"]
        old_val = getattr(self.params, info["param_name"], None)
        safe_default = info.get("safe_default", None)

        if entry_type == "vector":
            new_val = self._resize_vector(old_val, dim[0], safe_default)
        elif entry_type == "matrix":
            new_val = self._resize_matrix(old_val, dim[0], dim[1], safe_default)

        return new_val, dim

    def _replace_widget(self, widget_name: str, new_widget: qw.QWidget, type: str) -> None:
        if type == "entry":
            info = self.entry_blocks[widget_name]
        elif type == "dropdown":
            info = self.dropdowns[widget_name]
        else:
            return

        old = info["widget"]
        lay = info["row_layout"]
        idx = info["row_index"]

        lay.insertWidget(idx, new_widget, stretch=1, alignment=qc.Qt.AlignmentFlag.AlignTop)
        lay.removeWidget(old)
        old.setParent(None)
        old.deleteLater()

        info["widget"] = new_widget

    def _auto_fontsize(self, rows: int, cols: int) -> int:
        font_vals = {
            (1,1): 10, (1,2): 8, (1,3): 6,
            (2,1): 8,  (2,2): 8, (3,2): 6,
            (2,3): 6,  (3,3): 0
        }
        return font_vals.get((rows, cols), 10)
    
    def get_slot_config(self, slot_index: int):
        """ Return the current dropdown index, checkbox options, and legend settings for a slot """
        if slot_index < 0 or slot_index >= len(self.slot_dropdowns): return None

        plot_widget = self.slot_dropdowns[slot_index]
        dropdown_index = plot_widget.dropdown_choices.currentIndex()
        options = plot_widget.get_current_checked_boxes()

        if 0 <= slot_index < len(self.slot_options):
            raw_settings = self.slot_options[slot_index].get_settings()
            slot_settings = self._normalize_slot_settings(raw_settings)
        else:
            slot_settings = {
                "legend_visible": True,
                "legend_fontsize": 10,
                "legend_loc": "upper right"
            }

        return dropdown_index, options, slot_settings

    def update_plot(self, name, new_val, widget_changed= None):
        """ 
            Primarily just emits that a parameter has changed to the MainWindow, but also 
            updates itself if the parameter which changed has any metadependencies 
        """
        before_meta = self._meta_signature()

        try:
            setattr(self.params, name, new_val)
        except Exception:
            pass

        after_meta = self._meta_signature()

        changed_meta_widgets = {
            widget_name
            for widget_name in self._meta_dependents
            if before_meta.get(widget_name) != after_meta.get(widget_name)
        }

        is_meta = bool(changed_meta_widgets)

        if widget_changed is not None:
            if widget_changed in self.entry_blocks:
                info = self.entry_blocks[widget_changed]
            elif widget_changed in self.dropdowns:
                info = self.dropdowns[widget_changed]
            elif widget_changed in self.checkboxes:
                info = self.checkboxes[widget_changed]
            elif widget_changed in self.file_pickers:
                info = self.file_pickers[widget_changed]
            else:
                info = {}
        else:
            info = {}

        change_effect = info.get("change_effect", None)

        if is_meta:
            change_effect = "restart"

        sim_scroll = self.content.widget(0)
        plot_scroll = self.content.widget(1)

        sim_v = sim_scroll.verticalScrollBar().value()
        plot_v = plot_scroll.verticalScrollBar().value()
        focus_snap = self._snapshot_focus()

        try:
            for widget in self.dropdowns:
                if widget in self._meta_dependents:
                    self._apply_meta_changes_dropdown(widget)
            
            for widget in self.entry_blocks:
                if widget in self._meta_dependents:
                    self._apply_meta_changes_entry(widget)
        finally:
            qc.QTimer.singleShot(0, lambda: sim_scroll.verticalScrollBar().setValue(sim_v))
            qc.QTimer.singleShot(0, lambda: plot_scroll.verticalScrollBar().setValue(plot_v))
            qc.QTimer.singleShot(0, lambda: self._restore_focus(focus_snap))

        if not self.block_signals:
            if change_effect == "restart" and self.main_window._param_change_mode != "message" or is_meta:
                self._apply_plot_preprocessing()
            self.paramChanged.emit(name, new_val, change_effect, is_meta)

    def _snapshot_focus(self):
        fw = qw.QApplication.focusWidget()

        if fw is None:
            return None

        snap = {
            "widget": fw,
            "cursor": None,
            "selection_start": None,
            "selection_length": None,
            "matrix_cell": None,
            "entry_name": None,
        }

        if isinstance(fw, qw.QLineEdit):
            snap["cursor"] = fw.cursorPosition()
            snap["selection_start"] = fw.selectionStart()
            snap["selection_length"] = len(fw.selectedText())

        for entry_name, info in self.entry_blocks.items():
            w = info.get("widget")
            if hasattr(w, "focused_cell"):
                cell = w.focused_cell()
                if cell is not None:
                    snap["entry_name"] = entry_name
                    snap["matrix_cell"] = cell
                    break

        return snap

    def _restore_focus(self, snap):
        if not snap:
            return

        entry_name = snap.get("entry_name")
        matrix_cell = snap.get("matrix_cell")

        if entry_name is not None and matrix_cell is not None:
            info = self.entry_blocks.get(entry_name)
            if info is None:
                return

            w = info.get("widget")
            if hasattr(w, "focus_cell"):
                i, j = matrix_cell
                w.focus_cell(
                    i,
                    j,
                    cursor=snap.get("cursor"),
                    selection_start=snap.get("selection_start"),
                    selection_length=snap.get("selection_length"),
                )
                return

        # fallback for non-replaced normal widgets
        w = snap.get("widget")
        try:
            if w is None or w.parent() is None:
                return
            w.setFocus(qc.Qt.FocusReason.OtherFocusReason)
        except RuntimeError:
            return

    def _meta_signature_for_widget(self, widget_name: str):
        if widget_name in self.entry_blocks:
            info = self.entry_blocks[widget_name]["panel_info"]

            if "dim_from" in info:
                try:
                    dim = self._resolve_entry_dim(info)
                    return ("entry_dim", tuple(dim))
                except Exception:
                    logger.exception("Failed to resolve meta signature for %s", widget_name)
                    return ("entry_dim_error",)

        if widget_name in self.dropdowns:
            info = self.dropdowns[widget_name]["panel_info"]

            if "names_from" in info or "values_from" in info:
                try:
                    names, values = self._resolve_dropdown_names_and_vals(info)
                    return (
                        "dropdown_choices",
                        tuple(map(str, names)),
                        tuple(map(self._hashable_meta_value, values)),
                    )
                except Exception:
                    logger.exception("Failed to resolve meta signature for %s", widget_name)
                    return ("dropdown_choices_error",)

        return None

    def _meta_signature(self):
        return {
            widget_name: self._meta_signature_for_widget(widget_name)
            for widget_name in self._meta_dependents
        }

    def _hashable_meta_value(self, value):
        if isinstance(value, np.ndarray):
            return (
                "ndarray",
                value.shape,
                tuple(value.reshape(-1).tolist()),
            )

        if isinstance(value, list):
            return tuple(self._hashable_meta_value(v) for v in value)

        if isinstance(value, tuple):
            return tuple(self._hashable_meta_value(v) for v in value)

        if isinstance(value, dict):
            return tuple(
                sorted(
                    (k, self._hashable_meta_value(v))
                    for k, v in value.items()
                )
            )

        return value

    def _apply_plot_preprocessing(self):
        plot_preprocess = self.demo.get("details", {}).get("plot_preprocess")
        if plot_preprocess is not None:
            if plot_preprocess not in self.extra_functions_dict:
                self.status_bar.showMessage(f"Error: parameter defined by function {plot_preprocess} not found in extra_functions.py", 3000)
                return
            pre_process_function = self.extra_functions_dict[plot_preprocess]
            try:
                base_data = copy.deepcopy(self._base_plotting_data)
                new_data = pre_process_function(self.params, base_data)
                self.plotting_data = new_data
                self.refresh_dropdown_choices(new_data)
                self.preProcess.emit(new_data)
            except Exception as e:
                logger.log(logging.ERROR, f"Failed to apply plot pre-processing: {e}", exc_info= e)
                self.status_bar.showMessage(f"Failed to apply plot pre-processing: {e}", 3000)

    def refresh_dropdown_choices(self, new_plotting_data: dict) -> None:
        if not new_plotting_data:
            return

        old_block = self.block_signals
        self.block_signals = True

        try:
            for _, dropdown in enumerate(self.slot_dropdowns):
                old_checked = set(dropdown.get_current_checked_boxes())

                for category_key, category_dict in new_plotting_data.items():
                    category_display = category_dict.get("name", category_key)
                    if category_display not in dropdown.pages:
                        continue

                    plots = category_dict.get("plots", {}) or {}

                    desired_labels = []
                    # whether each should be checked or not based on new stuff and old user settings
                    desired_checked_by_label = {}

                    for _, plot_dict in plots.items():
                        if "checkbox_name" not in plot_dict:
                            continue

                        label = str(plot_dict["checkbox_name"])
                        desired_labels.append(label)

                        desired_checked_by_label[label] = (
                            label in old_checked
                            if label in old_checked
                            else bool(plot_dict.get("toggled", False))
                        )

                    existing_labels = set(dropdown.checkbox_labels(category_display))
                    desired_label_set = set(desired_labels)

                    for label in existing_labels - desired_label_set:
                        dropdown.remove_checkbox(category_display, label)

                    for label in desired_labels:
                        if label not in existing_labels:
                            dropdown.add_checkbox(
                                category_display,
                                label,
                                checked=desired_checked_by_label[label],
                            )

                    restore_checked = {
                        label
                        for label in desired_labels
                        if desired_checked_by_label.get(label, False)
                    }

                    previous_text = dropdown.dropdown_choices.currentText()
                    try:
                        idx = dropdown.dropdown_choices.findText(category_display)
                        if idx >= 0:
                            dropdown.dropdown_choices.blockSignals(True)
                            dropdown.dropdown_choices.setCurrentIndex(idx)
                            dropdown.set_checked_boxes(restore_checked)
                            dropdown.dropdown_choices.blockSignals(False)
                    finally:
                        prev_idx = dropdown.dropdown_choices.findText(previous_text)
                        if prev_idx >= 0:
                            dropdown.dropdown_choices.setCurrentIndex(prev_idx)

                # Make sure the visible page geometry updates.
                dropdown.stack.updateGeometry()
                dropdown.updateGeometry()

        finally:
            self.block_signals = old_block

    def _get_tooltip(self, slot_index: int= 0) -> str:
        """ When user hovers their mouse on the tooltip button by a dropdown menu of plots,
            the DropdownChoices widget emits an infoBoxHovered signal to the ControlPanel, which
            calls this function to return the string which is given as input to the 
            DropdownChoices.setToolTip method for displaying. 
        """
        if not (0 <= slot_index < len(self.slot_dropdowns)):
            return "No notes"

        wrapper = self.slot_dropdowns[slot_index]
        text = wrapper.dropdown_choices.currentText()
        tooltip_plain = self.dropdown_tooltips.get(text, "No notes")
        tooltip = f"""{tooltip_plain}"""

        wrapper.info.setToolTip(tooltip)

        wrapper.setToolTip(tooltip)
        return tooltip

    def _get_widgets_from_param_name(self, param):
        entry_widgets = set()
        dropdowns = set()
        for entry, entry_dict in self.entry_blocks.items():
            if entry_dict["param_name"] == param:
                entry_widgets.add(entry)
        for dropdown, dropdown_dict in self.dropdowns.items():
            if dropdown_dict["param_name"] == param:
                dropdowns.add(dropdown)

        return entry_widgets, dropdowns

    def receive_meta_update(self, details):
        param_name = details["param"]
        value = details["value"]
        action = details.get("action") # for later, if something else is ever needed

        if hasattr(self.params, param_name):
            setattr(self.params, param_name, value)
        else:
            logger.error(f"Error, received meta update call for parameter {param_name}, but no such parameter found.")
            self.status_bar.showMessage(f"Error, received meta update call for parameter {param_name}, but no such parameter found.", msecs= 4000)

        entries, dropdowns = self._get_widgets_from_param_name(param_name)
        self.block_signals = True
        for entry in entries:
            if self.entry_blocks[entry]["is_matrix"]:
                continue
            self.entry_blocks[entry]["widget"].entry.blockSignals(True)
            self.entry_blocks[entry]["widget"].entry.setText(str(value))
            self.entry_blocks[entry]["widget"].entry.blockSignals(False)
        for dropdown in dropdowns:
            self.dropdowns[dropdown]["dropdown"].blockSignals(True)
            self.dropdowns[dropdown]["dropdown"].setCurrentText(str(value))
            self.dropdowns[dropdown]["dropdown"].blockSignals(False)
        self.block_signals = False

    def load_new_params(self, params= None):
        old_block = self.block_signals
        self.block_signals = True

        if params is not None:
            self.params = params

        try:
            params_dict = asdict(self.params) if self.params else {}

            for param, value in params_dict.items():
                dep_entries, dep_dropdowns = self._get_widgets_from_param_name(param)
                for widget_name in dep_entries:
                    if widget_name in self._meta_dependents:
                        self._apply_meta_changes_entry(widget_name)
                        continue

                    widget_info = self.entry_blocks[widget_name]
                    widget = widget_info["widget"]

                    if widget_info["is_matrix"]:
                        widget.blockSignals(True)
                        widget.change_values(value)
                        widget.blockSignals(False)
                    else:
                        try:
                            float_value = float(value)
                            text = f"{float_value:.5g}"
                        except (TypeError, ValueError):
                            text = str(value)

                        widget.entry.blockSignals(True)
                        widget.entry.setText(text)
                        widget.entry.blockSignals(False)

                for widget_name in dep_dropdowns:
                    if widget_name in self._meta_dependents:
                        self._apply_meta_changes_dropdown(widget_name)
                        continue

                    info = self.dropdowns[widget_name]
                    dropdown = info["dropdown"]
                    values = info["values"]
                    new_val = params_dict[param]

                    try:
                        idx = values.index(new_val)
                    except ValueError:
                        continue

                    dropdown.blockSignals(True)
                    dropdown.setCurrentIndex(idx)
                    dropdown.blockSignals(False)

        finally:
            self.block_signals = old_block
