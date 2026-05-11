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

from overseer.tools.loader import load_presets
from .common import FormSection, make_shortname, replace_key_preserve_order, refresh_models
from overseer.tools.creation_tools import flow_seqify, atomic_write

class DemoSettingsTab(qw.QWidget):
    
    def __init__(self, env, parent= None):

        super().__init__(parent)

        self.env = env
        self._loading_editor = False

        with open(self.env.demos_file, "r") as f:
            self.original_data = yaml.safe_load(f)

        self.working_data = copy.deepcopy(self.original_data)
        self.names_dict = {}
        if self.working_data.get("demos"):
            for demo in self.working_data["demos"]:
                if not self.working_data["demos"].get(demo):
                    continue
                if not self.working_data["demos"][demo].get("name"):
                    continue
                name = self.working_data["demos"][demo]["name"]
                self.names_dict[name] = demo

        layout = qw.QHBoxLayout(self)
        layout.setSpacing(12)

        left = qw.QVBoxLayout()
        layout.addLayout(left, 1)

        demos_box = qw.QGroupBox("Demos")
        demos_layout = qw.QVBoxLayout(demos_box)

        self.demo_filter = qw.QLineEdit()
        self.demo_filter.setPlaceholderText("Filter demos…")

        self.demo_list = qw.QListWidget()
        self.combo_function = qw.QComboBox()
        self.combo_preset = qw.QComboBox()
        self.demo_list.setMinimumWidth(260)

        self.window = self.window()

        # self._refresh_demos()

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

        # Right: editor panel
        right = qw.QVBoxLayout()
        layout.addLayout(right, 2)

        sec = FormSection("Selected demo")
        self.lbl_internal_name = qw.QLabel("—")
        self.lbl_internal_name.setTextInteractionFlags(qc.Qt.TextInteractionFlag.TextSelectableByMouse)

        self.edit_demo_display_name = qw.QLineEdit()
        self.edit_demo_desc = qw.QPlainTextEdit()
        self.edit_demo_desc.setPlaceholderText("Description…")

        # Details
        self.combo_model = qw.QComboBox()

        # self.combo_model.currentIndexChanged.connect(self._refresh_functions)
        # self.combo_model.currentIndexChanged.connect(self._refresh_presets)

        # Starting lims
        # self.chk_starting_lims = qw.QCheckBox("Specify starting x/y limits")
        # self.edit_xlim_lo = qw.QLineEdit()
        # self.edit_xlim_hi = qw.QLineEdit()
        # self.edit_ylim_lo = qw.QLineEdit()
        # self.edit_ylim_hi = qw.QLineEdit()
        # for w in (self.edit_xlim_lo, self.edit_xlim_hi, self.edit_ylim_lo, self.edit_ylim_hi):
        #     w.setPlaceholderText("e.g. 0.0")

        # lims_grid = qw.QGridLayout()
        # lims_grid.setContentsMargins(0, 0, 0, 0)
        # lims_grid.addWidget(qw.QLabel("x min"), 0, 0)
        # lims_grid.addWidget(self.edit_xlim_lo, 0, 1)
        # lims_grid.addWidget(qw.QLabel("x max"), 0, 2)
        # lims_grid.addWidget(self.edit_xlim_hi, 0, 3)
        # lims_grid.addWidget(qw.QLabel("y min"), 1, 0)
        # lims_grid.addWidget(self.edit_ylim_lo, 1, 1)
        # lims_grid.addWidget(qw.QLabel("y max"), 1, 2)
        # lims_grid.addWidget(self.edit_ylim_hi, 1, 3)

        sec.form.addRow("Display name:", self.edit_demo_display_name)
        sec.form.addRow("Internal name:", self.lbl_internal_name)
        sec.form.addRow("Description:", self.edit_demo_desc)
        sec.form.addRow("Simulation model:", self.combo_model)
        sec.form.addRow("Simulation function:", self.combo_function)
        sec.form.addRow("Default preset:", self.combo_preset)
        # sec.form.addRow(self.chk_starting_lims)
        # sec.form.addRow(self._wrap_layout(lims_grid))

        # Editor actions
        editor_actions = qw.QHBoxLayout()
        self.btn_refresh_models = qw.QPushButton("Refresh Models")
        # self.btn_save_demo = qw.QPushButton("Save")
        # self.btn_save_as_new = qw.QPushButton("Save as New")
        # editor_actions.addWidget(self.btn_save_demo)
        # editor_actions.addWidget(self.btn_save_as_new)
        editor_actions.addWidget(self.btn_refresh_models)
        editor_actions.addStretch(1)

        right.addWidget(sec, 1)
        right.addLayout(editor_actions, 0)

        # Wiring for this page
        self.demo_filter.textChanged.connect(self._filter_demo_list)

        self.btn_refresh_models.clicked.connect(self._refresh_models)
        # self.btn_save_as_new.clicked.connect(self._on_save_as_new_clicked)
        # self.btn_save_demo.clicked.connect(self._save_demo_changes)

        # Demo-related wiring (page: Demos)
        self.demo_list.currentRowChanged.connect(self._on_demo_selected)
        self.btn_set_default.clicked.connect(self._on_set_default_clicked)

        self._editor_widgets = [
            self.edit_demo_display_name,
            self.edit_demo_desc,
            self.combo_model,
            self.combo_function,
            self.combo_preset,
        ]

        self._refresh_demos()
        self._refresh_models()
        self._wire_autosave_signals()
        if self.demo_list.count() > 0:
            self._on_demo_selected(0)

    def _refresh_models(self):
        old_combo = self.combo_model.currentText()
        old_function = self.combo_function.currentText()
        old_preset = self.combo_preset.currentText()

        self.combo_model.clear()
        models = refresh_models(self.env)
        for model in models:
            self.combo_model.addItem(model)
        self.combo_model.setCurrentText(old_combo)

        self._refresh_presets(old_preset)
        self._refresh_functions(old_function)

        self.window.status.show("Refreshed models.", 3000)

    def _refresh_demos(self, selected_key: str | None = None):
        if selected_key is None:
            selected_key = self._current_demo_key()

        self.demo_list.blockSignals(True)
        self.demo_list.clear()
        self.names_dict.clear()

        for intern_key, demo_dict in self.working_data["demos"].items():
            if demo_dict is None:
                continue
            if not demo_dict.get("name"):
                continue
            display_name = demo_dict["name"]
            self.names_dict[display_name] = intern_key

            item = qw.QListWidgetItem(display_name)
            item.setData(qc.Qt.ItemDataRole.UserRole, intern_key)
            self.demo_list.addItem(item)

        restored = False
        if selected_key is not None:
            for i in range(self.demo_list.count()):
                it = self.demo_list.item(i)
                if it.data(qc.Qt.ItemDataRole.UserRole) == selected_key:
                    self.demo_list.setCurrentRow(i)
                    restored = True
                    break

        if not restored and self.demo_list.count() > 0:
            self.demo_list.setCurrentRow(0)

        self.demo_list.blockSignals(False)
        self._apply_default_styling()

    def _current_demo_key(self) -> str | None:
        it = self.demo_list.currentItem()
        return it.data(qc.Qt.ItemDataRole.UserRole) if it else None

    def _delete_demo(self):
        key = self._current_demo_key()
        if not key:
            return

        # delete from working copy only
        self.working_data["demos"].pop(key, None)
        self._refresh_demos()

    def _on_changes(self):
        self._update_internal_name(self.edit_demo_display_name.text())
        self._save_demo_changes()

    def _update_internal_name(self, text):
        self.lbl_internal_name.setText(make_shortname(text))

    def _refresh_functions(self, old_function= None):
        self.combo_function.clear()
        current_model = self.combo_model.currentText()
        if not current_model: return
        try:
            sim_functions_module = importlib.import_module(f"models.{current_model}.simulation.simulation")
            functions_dict = dict(inspect.getmembers(sim_functions_module, inspect.isfunction))
            functions_list = list(functions_dict.keys())
        except Exception as e:
            self.window.status.show(f"Error loading sim functions module: {e}.", 4000)
            return

        for function in functions_list:
            self.combo_function.addItem(function)

        if old_function is not None:
            self.combo_function.setCurrentText(old_function)

    def _refresh_presets(self, old_preset= None):
        self.combo_preset.clear()
        current_model = self.combo_model.currentText()
        if not current_model: return
        try:
            presets = load_presets(self.env, current_model)
        except Exception:
            presets = []
        for preset in presets:
            self.combo_preset.addItem(preset)

        if old_preset is not None:
            self.combo_preset.setCurrentText(old_preset)

    def _wrap_layout(self, layout: qw.QLayout) -> qw.QWidget:
        w = qw.QWidget()
        w.setLayout(layout)
        return w

    def _filter_demo_list(self, text: str) -> None:
        t = text.strip().lower()
        for i in range(self.demo_list.count()):
            it = self.demo_list.item(i)
            key = (it.data(qc.Qt.ItemDataRole.UserRole) or "")
            it.setHidden(t not in key.lower())

    # def _set_lims_enabled(self, enabled: bool) -> None:
    #     for w in (self.edit_xlim_lo, self.edit_xlim_hi, self.edit_ylim_lo, self.edit_ylim_hi):
    #         w.setEnabled(enabled)

    def _on_save_as_new_clicked(self) -> None:
        if self.edit_demo_display_name.text() == "":
            self.window.status.show(f"Name field cannot be empty.", 4000)
        if self.edit_demo_display_name.text() in self.names_dict:
            self.window.status.show(f"You already have a demo by this name.", 4000)
            return
        
        new_demo = self._get_new_demo_dict()
        self.working_data["demos"][self.lbl_internal_name.text()] = new_demo
        self._refresh_demos()

    def _new_demo(self):

        # Generate a unique display + internal name
        base_display = "New Demo"
        i = 1
        display_name = base_display
        while display_name in self.names_dict:
            i += 1
            display_name = f"{base_display} {i}"

        internal_name = make_shortname(display_name)

        # Extremely minimal placeholder demo
        new_demo = {
            "name": display_name,
            "desc": "",
            "details": {
                "simulation_model": "",
                "simulation_function": "",
                "default_preset": "",
            },
        }

        # Insert into working copy
        self.working_data["demos"][internal_name] = new_demo

        # Refresh list
        self._refresh_demos()

        # Select the newly created demo
        for row in range(self.demo_list.count()):
            it = self.demo_list.item(row)
            if it.data(qc.Qt.ItemDataRole.UserRole) == internal_name:
                self.demo_list.setCurrentRow(row)
                break


    def _get_new_demo_dict(self, new= False):
        new_demo = {}
        new_demo["name"] = self.edit_demo_display_name.text()
        new_demo["desc"] = self.edit_demo_desc.toPlainText()
        new_demo["details"] = {}
        new_demo["details"]["simulation_model"] = self.combo_model.currentText()
        new_demo["details"]["simulation_function"] = self.combo_function.currentText()
        new_demo["details"]["default_preset"] = self.combo_preset.currentText()
        # if self.chk_starting_lims.isChecked():
            # try:
            #     xlims = [float(self.edit_xlim_lo.text().strip()), float(self.edit_xlim_hi.text().strip())]
            #     ylims = [float(self.edit_ylim_lo.text().strip()), float(self.edit_ylim_hi.text().strip())]
            # except ValueError:
            #     self.window.status.show("Error reading your limits. Please double check.", 4000)
            #     return new_demo
            # else:
            #     axis_settings = new_demo["details"].setdefault("axis_settings", {})
            #     lims = flow_seqify([xlims, ylims])
            #     # lims = FlowSeq([FlowSeq(xlims), FlowSeq(ylims)])
            #     axis_settings["limits"] = {"a1": lims}

        return new_demo

    def _on_demo_selected(self, row: int) -> None:
        if row < 0:
            self._clear_demo_editor()
            return

        item = self.demo_list.currentItem()
        choice = item.text()
        demo = self.names_dict[choice]
        demo_dict = self.working_data["demos"][demo]

        self._loading_editor = True
        self._block_editor_signals(True)
        try:
            self.lbl_internal_name.setText(demo)
            self.edit_demo_display_name.setText(demo_dict["name"])
            self.edit_demo_desc.setPlainText(demo_dict["desc"])

            details = demo_dict["details"]
            model_index = self.combo_model.findText(details["simulation_model"])

            self.combo_model.setCurrentIndex(model_index)
            self._refresh_functions()
            self._refresh_presets()
            func_index = self.combo_function.findText(details["simulation_function"])
            preset_index = self.combo_preset.findText(details["default_preset"])
            self.combo_function.setCurrentIndex(func_index)
            self.combo_preset.setCurrentIndex(preset_index)

            # lims = details.get("axis_settings", {}).get("limits", {}).get("a1", -1)
            # if lims != -1:
            #     x0, x1 = lims[0]
            #     y0, y1 = lims[1]
            #     self.chk_starting_lims.setChecked(True)
            #     self.edit_xlim_lo.setText(str(x0))
            #     self.edit_xlim_hi.setText(str(x1))
            #     self.edit_ylim_lo.setText(str(y0))
            #     self.edit_ylim_hi.setText(str(y1))
            # else:
            #     self.chk_starting_lims.setChecked(False)
            #     self.edit_xlim_lo.clear()
            #     self.edit_xlim_hi.clear()
            #     self.edit_ylim_lo.clear()
            #     self.edit_ylim_hi.clear()
        finally:
            self._block_editor_signals(False)
            self._loading_editor = False

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

        replace_key_preserve_order(self.working_data["demos"], old_key, new_key, new_demo)
        self._refresh_demos(selected_key= new_key)


    # def _on_save_changes_clicked(self) -> None:
    #     old_key = self._current_demo_key()
    #     new_key = self.lbl_internal_name.text().strip()  # the proposed internal name
    #     new_demo = self._get_new_demo_dict()

    #     if new_key == old_key:
    #         self.working_data["demos"][old_key] = new_demo
    #         # self.working_data["model_specific_settings"].setdefault(old_key, None)
    #         self.window.status.show("Updated demo (working copy). Click Apply to write to disk.")
    #         self._refresh_demos()
    #         return
    #     else:
    #         # prevent collisions
    #         if new_key in self.working_data["demos"]:
    #             self.window.status.show("That internal name is already in use.", 4000)
    #             return

    #         # rekey demos and model_specific_settings without changing ordering
    #         self.working_data["demos"][old_key] = new_demo
    #         self.working_data["demos"] = self._rekey_preserve_order(self.working_data["demos"], old_key, new_key)

    #         self._refresh_demos()
    #         return
 
    def _on_set_default_clicked(self) -> None:
        selected_key = self._current_demo_key()
        if not selected_key:
            self.window.show("No demo selected.", 3000)
            return

        old_default = self._get_default_demo_key()
        if old_default and old_default in self.working_data["demos"]:
            self.working_data["demos"][old_default].pop("default", None)

        self.working_data["demos"][selected_key]["default"] = True

        self._apply_default_styling()

    def _rekey_preserve_order(self, d: dict, old_key: str, new_key: str):
        if old_key == new_key:
            return d
        new_d = {}
        for k, v in d.items():
            if k == old_key:
                new_d[new_key] = v
            else:
                new_d[k] = v
        return new_d

    def _apply_default_styling(self) -> None:
        default_key = self._get_default_demo_key()
        for i in range(self.demo_list.count()):
            it = self.demo_list.item(i)
            key = it.data(qc.Qt.ItemDataRole.UserRole)

            if key == default_key:
                # pick ONE of these approaches:

                # A) simple foreground color + bold
                it.setForeground(qg.QBrush(qc.Qt.GlobalColor.darkGreen))
                f = it.font()
                f.setBold(True)
                it.setFont(f)

            else:
                # reset styling
                it.setForeground(qg.QBrush())  # default
                f = it.font()
                f.setBold(False)
                it.setFont(f)

    def _get_default_demo_key(self) -> str | None:
        demos = self.working_data.get("demos", {})
        for k, v in demos.items():
            if isinstance(v, dict) and v.get("default"):
                return k
        return None

    def on_apply_clicked(self):

        self._normalize_for_dump(self.working_data)
        path = self.env.demos_file
        atomic_write(path, self.working_data)
        self.original_data = copy.deepcopy(self.working_data)
        self.working_data = copy.deepcopy(self.original_data)

        self._refresh_demos()

    def _normalize_for_dump(self, data: dict) -> dict:
        """ Does basically nothing right now, but this is where you would apply any special formatting to the settings dict """
        flow_seqify(data)

        return data

    def _wire_autosave_signals(self) -> None:
        self.edit_demo_display_name.textEdited.connect(self._on_changes)
        self.edit_demo_desc.textChanged.connect(self._save_demo_changes)

        self.combo_model.currentIndexChanged.connect(self._on_model_changed_autosave)
        self.combo_function.currentIndexChanged.connect(self._save_demo_changes)
        self.combo_preset.currentIndexChanged.connect(self._save_demo_changes)

        # self.chk_starting_lims.toggled.connect(self._on_starting_lims_toggled)

        # self.edit_xlim_lo.textEdited.connect(self._save_demo_changes)
        # self.edit_xlim_hi.textEdited.connect(self._save_demo_changes)
        # self.edit_ylim_lo.textEdited.connect(self._save_demo_changes)
        # self.edit_ylim_hi.textEdited.connect(self._save_demo_changes)

    def _block_editor_signals(self, block: bool) -> None:
        for w in self._editor_widgets:
            try:
                w.blockSignals(block)
            except Exception:
                pass

    def _on_model_changed_autosave(self) -> None:
        if self._loading_editor:
            return

        self._refresh_functions()
        self._refresh_presets()
        self._save_demo_changes()

    def _on_starting_lims_toggled(self, enabled: bool) -> None:
        self._set_lims_enabled(enabled)
        if not self._loading_editor:
            self._save_demo_changes()
