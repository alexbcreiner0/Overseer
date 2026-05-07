from __future__ import annotations
from pathlib import Path
import copy
import yaml
import importlib, inspect

from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc,
    QtGui as qg
)

from overseer.tools.loader import deepcopy, load_presets
from .common import FormSection, make_shortname, replace_key_preserve_order
from overseer.tools.creation_tools import flow_seqify, atomic_write

class DemoSettingsTab(qw.QWidget):
    
    def __init__(self, env, parent= None):

        super().__init__(parent)
        self.env = env
        self.window = self.window()
        self._loading_editor = False

        with open(self.env.config_file, "r") as f:
            self.original_data = yaml.safe_load(f)

        self.working_data = copy.deepcopy(self.original_data)
        self._repopulate_model_names() # (re)creates self.names_dict

        layout = qw.QHBoxLayout(self)
        layout.setSpacing(12)

        left = self._create_demo_selection_pane()
        layout.addLayout(left, 1)

        right = qw.QVBoxLayout()
        layout.addLayout(right, 2)

        sec = FormSection("Selected demo")
        self.lbl_internal_name = qw.QLabel("—")
        self.lbl_internal_name.setTextInteractionFlags(qc.Qt.TextInteractionFlag.TextSelectableByMouse)

        self.edit_demo_display_name = qw.QLineEdit()
        self.edit_demo_display_name.textChanged.connect(self._on_changes)
        self.edit_demo_desc = qw.QPlainTextEdit()
        self.edit_demo_desc.setPlaceholderText("Description…")

        self.combo_model = qw.QComboBox()
        self._refresh_models()

        self.chk_starting_lims = qw.QCheckBox("Specify starting x/y limits")
        self.edit_xlim_lo = qw.QLineEdit()
        self.edit_xlim_hi = qw.QLineEdit()
        self.edit_ylim_lo = qw.QLineEdit()
        self.edit_ylim_hi = qw.QLineEdit()
        for w in (self.edit_xlim_lo, self.edit_xlim_hi, self.edit_ylim_lo, self.edit_ylim_hi):
            w.setPlaceholderText("e.g. 0.0")

        lims_grid = qw.QGridLayout()
        lims_grid.setContentsMargins(0, 0, 0, 0)
        lims_grid.addWidget(qw.QLabel("x min"), 0, 0)
        lims_grid.addWidget(self.edit_xlim_lo, 0, 1)
        lims_grid.addWidget(qw.QLabel("x max"), 0, 2)
        lims_grid.addWidget(self.edit_xlim_hi, 0, 3)
        lims_grid.addWidget(qw.QLabel("y min"), 1, 0)
        lims_grid.addWidget(self.edit_ylim_lo, 1, 1)
        lims_grid.addWidget(qw.QLabel("y max"), 1, 2)
        lims_grid.addWidget(self.edit_ylim_hi, 1, 3)

        sec.form.addRow("Display name:", self.edit_demo_display_name)
        sec.form.addRow("Internal name:", self.lbl_internal_name)
        sec.form.addRow("Description:", self.edit_demo_desc)
        sec.form.addRow("Simulation model:", self.combo_model)
        sec.form.addRow("Simulation function:", self.combo_function)
        sec.form.addRow("Default preset:", self.combo_preset)
        sec.form.addRow(self.chk_starting_lims)
        sec.form.addRow(self._wrap_layout(lims_grid))

        # most of this is probably deprecated
        self.combo_model.currentIndexChanged.connect(self._refresh_functions)
        self.combo_model.currentIndexChanged.connect(self._refresh_presets)
        self.demo_filter.textChanged.connect(self._filter_demo_list)
        self.chk_starting_lims.toggled.connect(self._set_lims_enabled)
        self._set_lims_enabled(False)
        self.demo_list.currentRowChanged.connect(self._on_demo_selected)
        self.btn_set_default.clicked.connect(self._on_set_default_clicked)

        self._wire_autosave_signals()

        self._editor_widgets = [
            self.edit_demo_display_name,
            self.edit_demo_desc,
            self.combo_model,
            self.combo_function,
            self.combo_preset,
            self.chk_starting_lims,
            self.edit_xlim_lo,
            self.edit_xlim_hi,
            self.edit_ylim_lo,
            self.edit_ylim_hi
        ]

    def _save_demo_changes(self):
        if self._loading_editor:
            return

        old_key = self._current_demo_key()
        if not old_key:
            return

        new_key = self.lbl_internal_name.text().strip()
        if not new_key:
            return

        new_demo = self._get_new_demo_dict()

        old_demo = self.working_data["demos"].get(old_key, {})
        if isinstance(old_demo, dict) and old_demo.get("default"):
            new_demo["default"] = True

        # update under current key first
        self.working_data["demos"][old_key] = new_demo

        item = self.demo_list.currentItem()
        new_display = new_demo.get("name", "") or old_key
        if item is not None and item.text() != new_display:
            item.setText(new_display)

        if new_key == old_key:
            return

        if new_key in self.working_data["demos"]:
            self.window.status.show("That internal name is already in use.", msecs=2000)
            return

        replace_key_preserve_order(self.working_data["demos"], old_key, new_key)

        self._refresh_demos()

    def _wire_autosave_signals(self) -> None:
        self.edit_demo_display_name.textEdited.connect(self._on_changes)
        self.edit_demo_desc.textChanged.connect(self._save_demo_changes)

        self.combo_model.currentIndexChanged.connect(self._on_model_changed_autosave)
        self.combo_function.currentIndexChanged.connect(self._save_demo_changes)
        self.combo_preset.currentIndexChanged.connect(self._save_demo_changes)

        self.chk_starting_lims.toggled.connect(self._on_starting_lims_toggled)

        self.edit_xlim_lo.textEdited.connect(self._save_demo_changes)
        self.edit_xlim_hi.textEdited.connect(self._save_demo_changes)
        self.edit_ylim_lo.textEdited.connect(self._save_demo_changes)
        self.edit_ylim_hi.textEdited.connect(self._save_demo_changes)

    def _repopulate_model_names(self):
        self.names_dict = {}
        if self.working_data.get("demos"):
            for demo in self.working_data["demos"]:
                if not self.working_data["demos"].get(demo):
                    continue
                if not self.working_data["demos"][demo].get("name"):
                    continue
                name = self.working_data["demos"][demo]["name"]
                self.names_dict[name] = demo

    def _create_demo_selection_pane(self):
        left = qw.QVBoxLayout()

        demos_box = qw.QGroupBox("Demos")
        demos_layout = qw.QVBoxLayout(demos_box)

        self.demo_filter = qw.QLineEdit()
        self.demo_filter.setPlaceholderText("Filter demos…")

        self.demo_list = qw.QListWidget()
        self.combo_function = qw.QComboBox()
        self.combo_preset = qw.QComboBox()
        self.demo_list.setMinimumWidth(260)

        demos_layout.addWidget(self.demo_filter, 0)
        demos_layout.addWidget(self.demo_list, 1)
        left.addWidget(demos_box, 1)

        bottom_butts = qw.QWidget()
        bottom_butts.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Maximum)
        bottom_butts_layout = qw.QHBoxLayout(bottom_butts)
        self.btn_set_default = qw.QPushButton("Set as default")
        self.btn_delete_demo = qw.QPushButton("Delete")
        self.btn_new_demo = qw.QPushButton("+ Demo")
        bottom_butts_layout.addWidget(self.btn_set_default, 0)
        bottom_butts_layout.addWidget(self.btn_delete_demo, 0)
        bottom_butts_layout.addWidget(self.btn_new_demo, 0)
        self.btn_delete_demo.clicked.connect(self._delete_demo)
        self.btn_new_demo.clicked.connect(self._new_demo)
        left.addWidget(bottom_butts, 0)

        return left

    def _block_editor_signals(self, block: bool) -> None:
        for w in self._editor_widgets:
            try:
                w.blockSignals(block)
            except Exception:
                pass

    def _current_demo_key(self) -> str | None:
        it = self.demo_list.currentItem()
        return it.data(qc.Qt.ItemDataRole.UserRole) if it else None

    def _delete_demo(self):
        pass

    def _new_demo(self):
        pass

    def _on_changes(self):
        pass

    def _refresh_models(self):
        pass

    def _refresh_functions(self):
        pass

    def _refresh_presets(self):
        pass

    def _wrap_layout(self, grid: qw.QLayout):
        pass

    def _set_lims_enabled(self, enabled: bool) -> None:
        for w in (self.edit_xlim_lo, self.edit_xlim_hi, self.edit_ylim_lo, self.edit_ylim_hi):
            w.setEnabled(enabled)

    def _get_new_demo_dict(self, new= False):
        new_demo = {}
        new_demo["name"] = self.edit_demo_display_name.text()
        new_demo["desc"] = self.edit_demo_desc.toPlainText()
        new_demo["details"] = {}
        new_demo["details"]["simulation_model"] = self.combo_model.currentText()
        new_demo["details"]["simulation_function"] = self.combo_function.currentText()
        new_demo["details"]["default_preset"] = self.combo_preset.currentText()
        if self.chk_starting_lims.isChecked():
            try:
                xlims = [float(self.edit_xlim_lo.text().strip()), float(self.edit_xlim_hi.text().strip())]
                ylims = [float(self.edit_ylim_lo.text().strip()), float(self.edit_ylim_hi.text().strip())]
            except ValueError:
                self.window.status.show("Error reading your limits. Please double check.", 4000)
                return new_demo
            else:
                axis_settings = new_demo["details"].setdefault("axis_settings", {})
                lims = flow_seqify([xlims, ylims])
                # lims = FlowSeq([FlowSeq(xlims), FlowSeq(ylims)])
                axis_settings["limits"] = {"a1": lims}

        return new_demo

