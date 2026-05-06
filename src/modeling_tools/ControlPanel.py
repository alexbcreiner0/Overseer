import logging
logger = logging.getLogger(__name__)

from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
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
    paramChanged = qc.pyqtSignal(str, object)
    layoutChanged = qc.pyqtSignal(int, int)
    slotPlotChoiceChanged = qc.pyqtSignal(int, str)
    slotOptionsChanged = qc.pyqtSignal(int)
    slotAxesChanged = qc.pyqtSignal(int)
    slotAxesCatChanged = qc.pyqtSignal(int)
    paramsReplaced = qc.pyqtSignal(object)

    def __init__(
            self, env, status_bar, params, 
            dropdown_choices, dropdown_tooltips, 
            panel_data, plotting_data, sim_model, 
            demo, current_tab= 0
    ):
        super().__init__()
        self.block_signals = True
        self.params = params
        self.sim_model = sim_model
        self.plotting_data = plotting_data
        self.dropdown_tooltips = dropdown_tooltips
        self.panel_data = panel_data if panel_data is not None else {}
        self.dropdown_choices = dropdown_choices
        self.demo = demo
        self.status_bar = status_bar
        self.env = env

        self.slot_dropdowns = []
        self.slot_options = []
        self.slot_axes_controls = []
        self.slot_titles = {}
        self.entry_blocks = {}
        self.dropdowns = {}
        self.row_wrappers = []

        self.content = qw.QTabWidget()
        outer_layout = qw.QVBoxLayout(self)
        outer_layout.addWidget(self.content)
        
        sim_controls_scroll_area, plot_controls_scroll_area = self._build_scroll_areas()
        self.content.addTab(sim_controls_scroll_area, "Simulation Controls")
        self.content.addTab(plot_controls_scroll_area, "Plot Controls")

        plot_controls = self._build_plot_controls_widget()
        sim_controls = self._build_sim_controls_widget()

        sim_controls_scroll_area.setWidget(sim_controls)
        plot_controls_scroll_area.setWidget(plot_controls)

        self.content.setCurrentIndex(current_tab)
        self._meta_dependents = self._get_metadeps()

        for i in range(len(self.slot_dropdowns)):
            self.get_tooltip(i)

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

            for entry in panel_data[row]:
                info = panel_data[row][entry]
                widget = self.make_widget(info, self.params)
                pos = preamble_controls_lay.count()
                preamble_controls_lay.addWidget(widget, stretch= 1, alignment= qc.Qt.AlignmentFlag.AlignTop)

                if info.get("control_type") == "entry_block":
                    pname = info["param_name"]
                    self.entry_blocks[pname]["row_layout"] = preamble_controls_lay
                    self.entry_blocks[pname]["row_index"] = pos
                    self.entry_blocks[pname]["panel_info"] = info


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

    def _collect_metadeps_from_info(self, info, meta_deps):
        """ 
            Collects metadependency references within widget settings
            and appends those parameters which do to the corresponding list
        """
        control_type = info.get("control_type", "")

        # presently, only entry blocks can have meta-dependencies
        if control_type == "entry_block" and "dim_from" in info:
            meta = info["dim_from"]
            deps = []

            if isinstance(meta, str):
                if meta in ["sum", "diff", "prod", "div"]:
                    for x in info["dim_from"][meta]:
                        deps.append(x)
                deps.append(meta)
            elif isinstance(meta, list):
                for x in meta:
                    if isinstance(x, str):
                        deps.append(x)

            for param in deps:
                meta_deps.setdefault(param, []).append(info["param_name"])
            return

        if control_type.startswith("hsub_panel") or control_type.startswith("vsub_panel"):
            for _, subinfo in info.get("entries", {}).items():
                self._collect_metadeps_from_info(subinfo, meta_deps)

    def _get_metadeps(self):
        """ 
            Creates a dictionary of metadependencies of the form 
            'param_name': [params which reference param_name]
        """
        meta_deps = {}
        for row_name, row in self.panel_data.items():
            if row_name.startswith("divider"):
                continue
            for _, info in row.items():
                self._collect_metadeps_from_info(info, meta_deps)
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
            # label = qw.QLabel(f"Plot ({r+1},{c+1}): ")
            # label.setMinimumWidth(70)

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

            if old_dropdown_indices is not None and len(old_dropdown_indices)-1 >= slot_index and len(self.dropdown_choices) > 0:
                dropdown_idx = old_dropdown_indices[slot_index]
                dropdown_choice = self._get_inter_name_from_name(self.dropdown_choices[dropdown_idx])
                choice_dict = self.plotting_data[dropdown_choice]
                projection = choice_dict.get("projection", "2d")
            else:
                projection = None

            z_axis = True if projection == "3d" else False
            default_font = self._auto_fontsize(rows, cols)
            options_widget = SlotControlsWidget()
            options_widget.legend_size_spin.setValue(default_font)
            if isinstance(old_saved_limits, list) and slot_index <= len(old_saved_limits)-1:
                axes_widget = AxesControlWidget(saved_limits= old_saved_limits[slot_index], z_axis= z_axis)
            else:
                axes_widget = AxesControlWidget(z_axis= z_axis)

            # never called?
            # if self.constructing: self._set_initial_plot_params(axes_widget)

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
            axes_widget.catSettingsChanged.connect(lambda s=slot_index: self.slotAxesCatChanged.emit(s))
    
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

    def _get_inter_name_from_name(self, name):
        for inter_name, plot_dict in self.plotting_data.items():
            if plot_dict["name"] == name:
                return inter_name

    def _on_info_hovered(self, slot_index: int):
        self.get_tooltip(slot_index)

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
        self.get_tooltip(slot_index)

        projection = self._get_slot_projection(idx)
        self.slot_axes_controls[slot_index].set_projection(projection)

        self.slotPlotChoiceChanged.emit(slot_index, "dropdown")

    # def _set_initial_plot_params(self, axes_widget):
    #     if "starting_lims" in self.demo["details"]:
    #         lims = self.demo["details"]["starting_lims"]
    #         try:
    #             xlim = tuple(lims[0])
    #             ylim = tuple(lims[1])
    #             if len(lims) == 3:
    #                 zlim = tuple(lims[2])
    #             else:
    #                 zlim = None
    #         except ValueError:
    #             return

    #         axes_widget.set_limits(xlim, ylim, zlim)

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

    def make_widget(self, info, params):
        control_type = info["control_type"]

        if control_type == "checkbox":
            w = self._build_checkbox(info, params)
            return w

        elif control_type == "dropdown":
            w = self._build_dropdown(info, params)
            return w
        
        elif control_type == "button_group":
            w = self._build_button_group(info)
            return w

        elif control_type == "entry_block": 
            w = self._build_entry_block(info, params)
            return w

        elif control_type[0:10] == "vsub_panel":
            w = self._build_sub_panel(info, params, orientation= "v")
            return w

        elif control_type[0:10] == "hsub_panel":
            w = self._build_sub_panel(info, params, orientation= "h")
            return w

        else:
            print("Unrecognized control type.")
            return qw.QWidget()

    def _build_checkbox(self, info, params) -> qw.QWidget:
        param_name, label, tooltip_plain = (
            info["param_name"], info['label'], info['tooltip']
        )
        tooltip = f"""{tooltip_plain}"""

        row_widget = qw.QWidget()
        row_layout = qw.QHBoxLayout(row_widget)
        widget = qw.QCheckBox(label)
        if hasattr(params, param_name):
            init_val = getattr(params, param_name)
            widget.setChecked(init_val)
        widget.setToolTip(tooltip)
        widget.checkStateChanged.connect(
            lambda state, pm= param_name: self.update_plot(pm, state == qc.Qt.CheckState.Checked))

        row_layout.addWidget(HelpButton("?", tooltip), stretch=0)
        row_layout.addWidget(widget)

        return row_widget

    def _build_dropdown(self, info, params) -> qw.QWidget:
        outer_widget = qw.QWidget()
        # outer_widget.setSizePolicy(qw.QSizePolicy.Policy.Preferred, qw.QSizePolicy.Policy.Maximum)
        outer_layout = qw.QVBoxLayout(outer_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(2)

        param_name, label, names, values, tooltip_plain = (
            info["param_name"], info["label"], info["names"], info["values"], info["tooltip"]
        )
        tooltip = f"""{tooltip_plain}"""

        label_widget = qw.QLabel(label)
        label_widget.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred
        )
        outer_layout.addWidget(label_widget, alignment = qc.Qt.AlignmentFlag.AlignCenter)

        top_row = qw.QWidget()
        # top_row.setSizePolicy(qw.QSizePolicy.Policy.Preferred, qw.QSizePolicy.Policy.Maximum)
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

        init_val = getattr(params, param_name)
        dropdown.setCurrentIndex(values.index(init_val))
        dropdown.currentIndexChanged.connect(
            lambda idx, pn=param_name, vals=values: self.update_plot(pn, vals[idx])
        )

        row_layout.addWidget(dropdown, stretch=1, alignment= qc.Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(HelpButton("?", tooltip), stretch=0)

        outer_layout.addWidget(top_row, alignment= qc.Qt.AlignmentFlag.AlignTop)

        self.dropdowns[param_name] = {"widget": dropdown, "values": values}
        return outer_widget

    def _build_button_group(self, info) -> qw.QWidget:
        widget = qw.QWidget()
        if info["display"] == "horizontal":
            button_layout = qw.QHBoxLayout(widget)
        else:
            button_layout = qw.QVBoxLayout(widget)
        
        names, functions = info["names"], info["functions"]
        for i,name in enumerate(names):
            button = qw.QPushButton(name)

            extra_functions_module = importlib.import_module(f"models.{self.sim_model}.simulation.extra_functions")

            functions_dict = dict(inspect.getmembers(extra_functions_module, inspect.isfunction))
            try:
                function = functions_dict[functions[i]]
                def outer_func(_checked= False):
                    new_params = None
                    sector_names = None
                    try:
                        new_params, sector_names = function(self.params, self.env)
                    except Exception as e:
                        print(f"Error: {e}")

                    if new_params is None: return

                    self.params = new_params
                    self.load_new_params(new_params)
                    self.paramsReplaced.emit((new_params, sector_names))

                    # self.load_new_params(output)

                button.clicked.connect(outer_func)
                button_layout.addWidget(button)

            except ValueError:
                print(f"Error loading function: {functions[i]}. Skipping button")
                continue

            button_layout.addWidget(button)

            return widget

    def _build_entry_block(self, info, params) -> qw.QWidget:
        param_name, label, tooltip_plain = info["param_name"], info["label"], info["tooltip"]
        tooltip = f"""{tooltip_plain}"""
        if hasattr(params, param_name):
            init_val = getattr(params, param_name)
        else:
            init_val = -1
        # print(getattr(params, param_name))

        if info["type"] == "scalar":
            scalar_range, scalar_type = tuple(info["range"]), info["scalar_type"]
            widget = EntryBlock(param_name, label, scalar_range, init_val, tooltip, scalar_type)
            self.entry_blocks[param_name] = {"widget": widget, "is_matrix": False}
            widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
            widget.valueChanged.connect(self.update_plot)

        elif info["type"] == "matrix":
            try: 
                dim = self._resolve_entry_dim(info, params)
            except Exception as e:
                logger.log(logging.ERROR, f"Failed to resolve matrix dim entry", exc_info= e)
                self.status_bar.showMessage(f"Failed to resolve matrix dim entry", 3000)
                dim = [1,1]
            widget = MatrixEntry(param_name, label, dim, init_val, tooltip)
            widget.textChanged.connect(self.update_plot)
            if "vsize_policy" in info:
                if info["vsize_policy"] == "expanding":
                    widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Minimum)
            else:
                widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)
            self.entry_blocks[param_name] = {"widget": widget, "is_matrix": True}
            
        elif info["type"] == "vector":
            if info.get("dim_from", None) is not None:
                try:
                    dep_param_info = info.get("dim_from")
                    if isinstance(dep_param_info, list):
                        if dep_param_info[0] == "sum":
                            dim1 = 0
                            for val in dep_param_info[1:]:
                                if isinstance(val, str):
                                    dim1 += getattr(params, val)
                                else:
                                    dim1 += int(val)
                            if dim1 == 0:
                                dim1 = 1
                        elif dep_param_info[0] == "diff":
                            dim1 = getattr(params, dep_param_info[1])
                            for val in dep_param_info[2:]:
                                if isinstance(val, str):
                                    dim1 -= getattr(params, val)
                                else:
                                    dim1 -= int(val)
                            if dim1 <= 0:
                                dim1 = 1
                    else:
                        dim1 = getattr(params, dep_param_info)
                except Exception as e:
                    logger.log(logging.ERROR, f"Dependent param not found: {dep_param_info}", exc_info= e)
                    if self.status_bar is not None:
                        self.status_bar.showMessage(f"Dependent param not found: {dep_param_info}", 3000)
                    dim1 = 1
            else:
                dim1 = info["dim"]

            if isinstance(dim1, tuple) or isinstance(dim1, list):
                for c in dim1:
                    if not isinstance(c, int):
                        logger.log(logging.ERROR, f"Coordinate {c} is not an integer!")
                        if self.status_bar is not None:
                            self.status_bar.showMessage(f"Coordinate {c} is not an integer!", 3000)
                    dim1 = 1
            elif not isinstance(dim1, int):
                logger.log(logging.ERROR, f"Coordinate {dim1} is not an integer!")
                if self.status_bar is not None:
                    self.status_bar.showMessage(f"Coordinate {dim1} is not an integer!", 3000)
                dim1 = 1
                       
            dim = (dim1, 1)
            try:
                reshaped_init_val = init_val.reshape(-1,1)
            except AttributeError as e:
                logger.log(logging.ERROR, f"Coordinate {init_val} is not a proper vector!", exc_info= e)
                if self.status_bar is not None:
                    self.status_bar.showMessage(f"Coordinate {init_val} is not a proper vector!", 3000)
                dim = [1,1]
                reshaped_init_val = np.array([1])
            print(f"{dim=}")
            widget = MatrixEntry(param_name, label, dim, reshaped_init_val, tooltip)
            widget.textChanged.connect(self.update_plot)
            widget.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)
            self.entry_blocks[param_name] = {"widget": widget, "is_matrix": True}
        else:
            print(f"Unrecognized type: {info["type"]}. Options for type are scalar, vector, and matrix.")
            return qw.QWidget()

        return widget

    def _build_sub_panel(self, info, params, orientation= "v") -> qw.QWidget:
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
            subwidget = self.make_widget(subinfo, params)
            pos = layout.count()
            layout.addWidget(subwidget)

            if subinfo.get("control_type") == "entry_block":
                pname = subinfo["param_name"]
                self.entry_blocks[pname]["row_layout"] = layout
                self.entry_blocks[pname]["row_index"] = pos
                self.entry_blocks[pname]["panel_info"] = subinfo

        return widget

    # def _resize_vector(self, old: np.ndarray, n: int, safe_default= None) -> np.ndarray:
    #     new = np.zeros((n,), dtype=float)
    #     if old is not None:
    #         m = min(len(old), n)
    #         new[:m] = old[:m]
    #     if safe_default is not None:
    #         # extra_rows
    #         if new.shape[0] > old.shape[0]:
    #             for i in range(old.shape[0], new.shape[0]):
    #                 new[i] = safe_default
    #     return new

    def _resize_vector(self, old, new_val: int, safe_default=None) -> np.ndarray:
        """ Returns what the updated array should be to populate an updated vector widget with """
        try:
            old_arr = np.asarray(old, dtype=float).reshape(-1)
        except Exception:
            old_arr = np.zeros((0,), dtype=float)

        new = np.zeros((new_val,), dtype=float)

        m = min(old_arr.shape[0], new_val)
        if m > 0:
            new[:m] = old_arr[:m]

        if safe_default is not None and new_val > old_arr.shape[0]:
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

    # def _resize_matrix(self, old: np.ndarray, row: int, col: int, safe_default= None) -> np.ndarray:
    #     new = np.zeros((row, col), dtype=float)
    #     if old is not None:
    #         r = min(old.shape[0], row)
    #         c = min(old.shape[1], col)
    #         new[:r, :c] = old[:r, :c]
    #     if safe_default is not None:
    #         # extra rows
    #         if new.shape[0] > old.shape[0]:
    #             for i in range(old.shape[0], new.shape[0]):
    #                 for j in range(0, new.shape[1]):
    #                     new[i, j] = safe_default
    #         if new.shape[1] > old.shape[1]:
    #             for j in range(old.shape[1], new.shape[1]):
    #                 for i in range(0, new.shape[0]):
    #                     new[i, j] = safe_default
    #     return new

    def _resolve_dim_token(self, token, params) -> int:
        """ resolve a dimension specification as either a constant or another parameter """
        if isinstance(token, int):
            return token

        if isinstance(token, str):
            if hasattr(params, token):
                return max(1, int(getattr(params, token)))
            raise ValueError(f"Unknown dim source '{token}'")

        raise TypeError(f"Bad dim token: {token!r}")

    def _resolve_entry_dim(self, info, params) -> tuple[int, int]:
        """ 
            resolve the dimension specification to a concrete dimension
            either based on the current value of a parameter or based on
            a literal number in the yaml
        """
        typ = info["type"]

        src = info.get("dim_from", info.get("dim"))

        if not isinstance(src, list):
            raise ValueError("Matrix dim must always be specified as a list.")
        if len(src) != 2:
            raise ValueError("Matrix dim_from/dim must have length 2")

        if isinstance(src[0], str):
            rows = getattr(params, src[0])
        else:
            rows = src[0]

        if isinstance(src[1], str):
            cols = getattr(params, src[1])
        else:
            cols = src[1]

        if not isinstance(rows, int) or not isinstance(cols, int):
            raise ValueError(f"One of {rows=}, {cols=} is not an integer!")

        return (rows, cols)

        # wrong?
        if typ == "scalar":
            return (1, 1)

        raise ValueError(f"Unsupported entry type: {typ}")

    def _apply_dim_meta(self, metaparam_name: str, new_val: object) -> None:
        """ 
            When a parameter has changed, if the name is listed in self._metadependents as a key,
            then the appropriate changes are made to the control panel itself before the simulation is
            re-run. This method is meant to apply those changes. 
        """
        # Don't let the new value be less than 1 or not an integer
        try:
            new_val = int(new_val)
        except Exception:
            return
        new_val = max(1, new_val)

        # get a list of parameters with widgets which depend on the input parameter
        dependent_params = self._meta_dependents.get(metaparam_name, [])
        if not dependent_params:
            return

        # 1) update dependent arrays on params
        for dependent in dependent_params:
            
            if dependent in self.entry_blocks:
                entry_info = self.entry_blocks[dependent]["panel_info"]
                entry_type = entry_info["type"]
                old_val = getattr(self.params, dependent, None)
                safe_default = entry_info.get("safe_default", None)

                if entry_type == "vector":
                    meta_info = entry_info["dim_from"]
                    if isinstance(meta_info, list):
                        if meta_info[0] == "sum":
                            for value in meta_info[1:]:
                                if isinstance(value, str):
                                    new_val += getattr(self.params, value)
                                else:
                                    new_val += int(value)

                    setattr(self.params, dependent, self._resize_vector(old_val, new_val, safe_default))

                if entry_type == "matrix":
                    dims = entry_info["dim_from"]
                    row, col = dims[0], dims[1]

                    if isinstance(row, list):
                        if row[0] == "sum":
                            new_new_val = new_val
                            for value in row[1:]:
                                if isinstance(value, str):
                                    if value != metaparam_name:
                                        new_new_val += getattr(self.params, value)
                                else:
                                    new_new_val += int(value)
                        row = new_new_val
                    elif row == metaparam_name:
                        row = new_val
                    elif isinstance(row, str):
                        row = getattr(self.params, row)

                    if col == metaparam_name:
                        col = new_val
                    elif isinstance(col, str):
                        col = getattr(self.params, col)

                    setattr(self.params, dependent, self._resize_matrix(old_val, row, col, safe_default))

        # 2) rebuild + replace widgets for those deps (vectors/matrices)
        self.block_signals = True
        try:
            for dependent in dependent_params:
                if self.entry_blocks[dependent]["is_matrix"]:
                    new_w = self._make_resized_entry_widget(dependent)
                    self._replace_entry_widget(dependent, new_w)
            # now push values to widgets (uses MatrixEntry.change_values) 
            self.load_new_params(self.params) # push values to the new widgets
        finally:
            self.block_signals = False

        # 3) tell MainWindow “params changed as a set” so it reruns once :contentReference[oaicite:10]{index=10}
        self.paramsReplaced.emit((self.params, None))

    def _replace_entry_widget(self, param_name: str, new_widget: qw.QWidget) -> None:
        info = self.entry_blocks[param_name]
        old = info["widget"]
        lay = info["row_layout"]
        idx = info["row_index"]

        lay.insertWidget(idx, new_widget, stretch=1, alignment=qc.Qt.AlignmentFlag.AlignTop)
        lay.removeWidget(old)
        old.setParent(None)
        old.deleteLater()

        info["widget"] = new_widget

    def _make_resized_entry_widget(self, param_name: str) -> qw.QWidget:
        """ Creates a newly resized entry widget based on current parameters """
        panel_info = self.entry_blocks[param_name]["panel_info"]
        label = panel_info["label"]
        tooltip = panel_info.get("tooltip", "")
        typ = panel_info["type"]

        init_val = getattr(self.params, param_name)

        if typ == "matrix":
            dim = (init_val.shape[0], init_val.shape[1])
            w = MatrixEntry(param_name, label, dim, init_val, tooltip)
            w.textChanged.connect(self.update_plot)
            return w

        if typ == "vector":
            dim = (init_val.shape[0], 1)
            w = MatrixEntry(param_name, label, dim, init_val.reshape(-1, 1), tooltip)
            w.textChanged.connect(self.update_plot)
            return w

        # scalar case shouldn’t need replacement for dimension changes
        return self.entry_blocks[param_name]["widget"]

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

    def get_data(self, index):
        data = {}
        for widget in self.entry_blocks:
            data[widget.name] = widget.get()
        return data

    def update_plot(self, name, new_val):
        """ 
            Primarily just emits that a parameter has changed to the MainWindow, but also 
            updates itself if the parameter which changed has any metadependencies 
        """
        try:
            setattr(self.params, name, new_val)
        except Exception:
            pass

        if name in getattr(self, "_meta_dependents", {}):
            self._apply_dim_meta(name, new_val)
            return

        if not self.block_signals:
            self.paramChanged.emit(name, new_val)

        # self.paramChanged.emit(name, new_val)

    def get_tooltip(self, slot_index: int= 0) -> str:
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

    def load_new_params(self, params):
        old_block = self.block_signals
        self.block_signals = True

        try:
            # Critical: keep ControlPanel's params reference synchronized with MainWindow.
            self.params = params

            # Critical: preset loads do not fire normal widget signals, so dependency
            # resizing must be done explicitly here.
            changed_dependents = self._normalize_dependent_param_values()
            self._rebuild_dependent_widgets_for_current_params(changed_dependents)

            params_dict = asdict(self.params) if self.params else {}

            for param, value in params_dict.items():
                if param in self.entry_blocks:
                    widget_info = self.entry_blocks[param]
                    widget = widget_info["widget"]

                    if widget_info["is_matrix"]:
                        widget.blockSignals(True)
                        widget.change_values(value)
                        widget.blockSignals(False)
                    else:
                        try:
                            v_float = float(value)
                            text = f"{v_float:.8g}"
                        except (TypeError, ValueError):
                            text = str(value)

                        widget.entry.blockSignals(True)
                        widget.entry.setText(text)
                        widget.entry.blockSignals(False)

                if param in self.dropdowns:
                    info = self.dropdowns[param]
                    dropdown = info["widget"]
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

    # def load_new_params(self, params):
    #     self.block_signals = True
    #     params_dict = asdict(params) if params else {}
    #     for param in params_dict:
    #         if param in self.entry_blocks:
    #             widget_info = self.entry_blocks[param]
    #             widget = widget_info["widget"]
    #             value = params_dict[param]

    #             if widget_info["is_matrix"]:
    #                 widget.blockSignals(True)
    #                 widget.change_values(value)
    #                 widget.blockSignals(False)
    #             else:
    #                 try:
    #                     v_float = float(value)
    #                     text = f"{v_float:.8g}"   
    #                 except (TypeError, ValueError):
    #                     text = str(value)

    #                 widget.entry.blockSignals(True)
    #                 widget.entry.setText(text)
    #                 widget.entry.blockSignals(False)

    #         if param in self.dropdowns:
    #             info = self.dropdowns[param]
    #             dropdown = info["widget"]
    #             values = info["values"]
    #             new_val = params_dict[param]

    #             try:
    #                 idx = values.index(new_val)
    #             except ValueError:
    #                 continue

    #             dropdown.blockSignals(True)
    #             dropdown.setCurrentIndex(idx)
    #             dropdown.blockSignals(False)

    #     self.block_signals = False

    def _resolve_vector_dim(self, info, params) -> int:
        src = info.get("dim_from", info.get("dim", 1))

        if isinstance(src, str):
            return max(1, int(getattr(params, src)))

        if isinstance(src, int):
            return max(1, int(src))

        # Optional support for YAML like dim_from: [num_sectors]
        if isinstance(src, list) and len(src) == 1 and isinstance(src[0], str):
            return max(1, int(getattr(params, src[0])))

        if isinstance(src, list) and len(src) == 1 and isinstance(src[0], int):
            return max(1, int(src[0]))

        raise ValueError(f"Bad vector dim/dim_from for {info.get('param_name')}: {src!r}")


    def _normalize_dependent_param_values(self) -> set[str]:
        """
        Make sure all matrix/vector params whose dimensions depend on meta params
        actually match the current params object.

        Returns the set of param names whose widgets should be rebuilt.
        """
        changed = set()

        for deps in getattr(self, "_meta_dependents", {}).values():
            for pname in deps:
                if pname not in self.entry_blocks:
                    continue

                pinfo = self.entry_blocks[pname]["panel_info"]
                typ = pinfo["type"]
                safe_default = pinfo.get("safe_default", None)
                old = getattr(self.params, pname, None)

                if typ == "vector":
                    n = self._resolve_vector_dim(pinfo, self.params)

                    try:
                        arr = np.asarray(old, dtype=float).reshape(-1)
                    except Exception:
                        arr = np.zeros((0,), dtype=float)

                    if arr.shape != (n,):
                        setattr(self.params, pname, self._resize_vector(arr, n, safe_default))
                        changed.add(pname)
                    else:
                        # normalize list/tuple inputs to ndarray
                        setattr(self.params, pname, arr)

                elif typ == "matrix":
                    rows, cols = self._resolve_entry_dim(pinfo, self.params)

                    try:
                        arr = np.asarray(old, dtype=float)
                    except Exception:
                        arr = np.zeros((0, 0), dtype=float)

                    if arr.ndim != 2:
                        arr = np.atleast_2d(arr)

                    if arr.shape != (rows, cols):
                        setattr(self.params, pname, self._resize_matrix(arr, rows, cols, safe_default))
                        changed.add(pname)
                    else:
                        # normalize list/tuple inputs to ndarray
                        setattr(self.params, pname, arr)

        return changed


    def _rebuild_dependent_widgets_for_current_params(self, only: set[str] | None = None) -> None:
        targets = only

        if targets is None:
            targets = set()
            for deps in getattr(self, "_meta_dependents", {}).values():
                targets.update(deps)

        for pname in targets:
            if pname not in self.entry_blocks:
                continue

            if self.entry_blocks[pname].get("is_matrix"):
                new_w = self._make_resized_entry_widget(pname)
                self._replace_entry_widget(pname, new_w)
