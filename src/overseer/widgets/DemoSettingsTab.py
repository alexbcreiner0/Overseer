from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

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
from overseer.tools.loader import discover_model_demos, DemoSource, demo_file_for_model, make_demo_id
from overseer.tools.creation_tools import flow_seqify, atomic_write

class DemoSettingsTab(qw.QWidget):
    
    def __init__(self, env, parent= None):

        super().__init__(parent)

        self.env = env
        self._loading_editor = False

        self._load_demo_catalog()

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
        self.combo_preprocessing = qw.QComboBox()
        self.entry_sim_speed = qw.QLineEdit()
        self.entry_sim_speed.setPlaceholderText("0")
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
        sec.form.addRow("Plot preprocessing:", self.combo_preprocessing)
        sec.form.addRow("Simulation Speed", self.entry_sim_speed)
        # sec.form.addRow(self.chk_starting_lims)
        # sec.form.addRow(self._wrap_layout(lims_grid))

        # Editor actions
        editor_actions = qw.QHBoxLayout()
        self.btn_refresh_models = qw.QPushButton("Refresh Models")
        editor_actions.addWidget(self.btn_refresh_models)
        editor_actions.addStretch(1)

        right.addWidget(sec, 1)
        right.addLayout(editor_actions, 0)

        # Wiring for this page
        self.demo_filter.textChanged.connect(self._filter_demo_list)

        self.btn_refresh_models.clicked.connect(self._refresh_models)
        self.demo_list.currentRowChanged.connect(self._on_demo_selected)
        self.btn_set_default.clicked.connect(self._on_set_default_clicked)

        self._editor_widgets = [
            self.edit_demo_display_name,
            self.edit_demo_desc,
            self.combo_model,
            self.combo_function,
            self.combo_preset,
            self.combo_preprocessing,
            self.entry_sim_speed
        ]

        self._refresh_demos()
        self._refresh_models()
        self._wire_autosave_signals()
        if self.demo_list.count() > 0:
            self._on_demo_selected(0)

    def _refresh_models(self):
        old_combo = self.combo_model.currentText()
        old_sim_function = self.combo_function.currentText()
        old_preprocessing_function = self.combo_preprocessing.currentText()
        old_preset = self.combo_preset.currentText()

        self.combo_model.clear()
        models = refresh_models(self.env)
        for model in models:
            self.combo_model.addItem(model)
        self.combo_model.setCurrentText(old_combo)

        self._refresh_presets(old_preset)
        self._refresh_functions(old_sim_function, old_preprocessing_function)

        self.window.status.show("Refreshed models.", 3000)

    # def _refresh_demos(self, selected_key: str | None = None):
    #     if selected_key is None:
    #         selected_key = self._current_demo_key()

    #     self.demo_list.blockSignals(True)
    #     self.demo_list.clear()
    #     self.names_dict.clear()

    #     for intern_key, demo_dict in self.working_data["demos"].items():
    #         if demo_dict is None:
    #             continue
    #         if not demo_dict.get("name"):
    #             continue
    #         display_name = demo_dict["name"]
    #         self.names_dict[display_name] = intern_key

    #         item = qw.QListWidgetItem(display_name)
    #         item.setData(qc.Qt.ItemDataRole.UserRole, intern_key)
    #         self.demo_list.addItem(item)

    #     restored = False
    #     if selected_key is not None:
    #         for i in range(self.demo_list.count()):
    #             it = self.demo_list.item(i)
    #             if it.data(qc.Qt.ItemDataRole.UserRole) == selected_key:
    #                 self.demo_list.setCurrentRow(i)
    #                 restored = True
    #                 break

    #     if not restored and self.demo_list.count() > 0:
    #         self.demo_list.setCurrentRow(0)

    #     self.demo_list.blockSignals(False)
    #     self._apply_default_styling()

    def _refresh_demos(self, selected_key: str | None = None):
        if selected_key is None:
            selected_key = self._current_demo_key()

        self.demo_list.blockSignals(True)
        self.demo_list.clear()

        for demo_id, demo in self.working_data["demos"].items():
            if not isinstance(demo, dict):
                continue

            source = self.demo_sources[demo_id]
            display_name = demo.get("name") or source.local_key

            item = qw.QListWidgetItem(
                f"{display_name}"
            )
            item.setData(qc.Qt.ItemDataRole.UserRole, demo_id)
            self.demo_list.addItem(item)

        restored = False

        if selected_key is not None:
            for row in range(self.demo_list.count()):
                item = self.demo_list.item(row)
                if item.data(qc.Qt.ItemDataRole.UserRole) == selected_key:
                    self.demo_list.setCurrentRow(row)
                    restored = True
                    break

        if not restored and self.demo_list.count():
            self.demo_list.setCurrentRow(0)

        self.demo_list.blockSignals(False)
        self._apply_default_styling()

    def _current_demo_key(self) -> str | None:
        it = self.demo_list.currentItem()
        return it.data(qc.Qt.ItemDataRole.UserRole) if it else None

    def _load_demo_catalog(self) -> None:
        catalog = discover_model_demos(
            self.env.models_dir,
            include_models_without_files= True,
        )

        self.catalog_errors = list(catalog.errors)

        self.original_documents = copy.deepcopy(catalog.documents)
        self.original_data = {
            "demos": copy.deepcopy(catalog.demos)
        }

        self.working_data = copy.deepcopy(self.original_data)
        self.demo_sources = dict(catalog.sources)

        for message in catalog.warnings:
            logger.warning(message)

    def _delete_demo(self):
        key = self._current_demo_key()
        if not key:
            return

        # delete from working copy only
        self.working_data["demos"].pop(key, None)
        self.demo_sources.pop(key, None)
        self._refresh_demos()

    def _on_changes(self):
        self._update_internal_name(self.edit_demo_display_name.text())
        self._save_demo_changes()

    def _update_internal_name(self, text):
        self.lbl_internal_name.setText(make_shortname(text))

    def _refresh_functions(self, old_sim_function= None, old_preprocessing_function= None):
        self.combo_function.clear()
        self.combo_preprocessing.clear()

        current_model = self.combo_model.currentText()
        if not current_model: return
        try:
            sim_functions_module = importlib.import_module(f"{current_model}.simulation.simulation")
            sim_functions_dict = dict(inspect.getmembers(sim_functions_module, inspect.isfunction))
            sim_functions_list = list(sim_functions_dict.keys())
        except Exception as e:
            self.window.status.show(f"Error loading sim functions module: {e}.", 4000)
            return

        for function in sim_functions_list:
            self.combo_function.addItem(function)

        if old_sim_function is not None:
            self.combo_function.setCurrentText(old_sim_function)

        pot_extra_func_path = self.env.models_dir / current_model / "simulation"/ "extra_functions.py"
        if not pot_extra_func_path.exists():
            self.combo_preprocessing.addItem("None")
            self.combo_preprocessing.setCurrentText("None")
            return

        try:
            extra_functions_module = importlib.import_module(f"{current_model}.simulation.extra_functions")
            extra_functions_dict = dict(inspect.getmembers(extra_functions_module, inspect.isfunction))
            extra_functions_list = list(extra_functions_dict.keys())
        except Exception as e:
            self.window.status.show(f"Error loading sim functions module: {e}.", 4000)
            return

        self.combo_preprocessing.addItem("None")
        for function in extra_functions_list:
            self.combo_preprocessing.addItem(function)

        if old_preprocessing_function is not None:
            self.combo_preprocessing.setCurrentText(old_preprocessing_function)

    def _refresh_presets(self, old_preset= None):
        self.combo_preset.clear()
        current_model = self.combo_model.currentText()
        if not current_model: return
        try:
            presets = load_presets(self.env, current_model)
            if presets is None:
                presets = []
        except Exception:
            presets = ["default_preset"]
        for preset in presets:
            self.combo_preset.addItem(preset)

        if old_preset is not None:
            self.combo_preset.setCurrentText(old_preset)

    def _wrap_layout(self, layout: qw.QLayout) -> qw.QWidget:
        w = qw.QWidget()
        w.setLayout(layout)
        return w

    def _filter_demo_list(self, text: str) -> None:
        search_text = text.strip().lower()

        for row in range(self.demo_list.count()):
            item = self.demo_list.item(row)
            demo_id = item.data(qc.Qt.ItemDataRole.UserRole) or ""
            source = self.demo_sources.get(demo_id)

            searchable_text = " ".join(
                (
                    item.text(),
                    demo_id,
                    source.model_name if source else "",
                )
            ).lower()

            item.setHidden(search_text not in searchable_text)

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

    # def _new_demo(self):
    #     # Generate a unique display + internal name
    #     base_display = "New Demo"
    #     i = 1
    #     display_name = base_display
    #     while display_name in self.names_dict:
    #         i += 1
    #         display_name = f"{base_display} {i}"

    #     internal_name = make_shortname(display_name)

    #     # Extremely minimal placeholder demo
    #     new_demo = {
    #         "name": display_name,
    #         "desc": "",
    #         "details": {
    #             "simulation_model": "",
    #             "simulation_function": "",
    #             "default_preset": "",
    #         },
    #     }

    #     # Insert into working copy
    #     self.working_data["demos"][internal_name] = new_demo

    #     # Refresh list
    #     self._refresh_demos()

    #     # Select the newly created demo
    #     for row in range(self.demo_list.count()):
    #         it = self.demo_list.item(row)
    #         if it.data(qc.Qt.ItemDataRole.UserRole) == internal_name:
    #             self.demo_list.setCurrentRow(row)
    #             break

    def _new_demo(self):
        model_name = self.combo_model.currentText().strip()

        if not model_name:
            self.window.status.show(
                "Select a model before creating a demo.",
                4000,
            )
            return

        base_display = "New Demo"
        display_name = base_display
        number = 1

        existing_names = {
            demo.get("name")
            for demo_id, demo in self.working_data["demos"].items()
            if self.demo_sources[demo_id].model_name == model_name
        }

        while display_name in existing_names:
            number += 1
            display_name = f"{base_display} {number}"

        local_key = make_shortname(display_name)
        demo_id = make_demo_id(model_name, local_key)

        new_demo = {
            "name": display_name,
            "desc": "",
            "details": {
                # Runtime compatibility. Removed again when writing.
                "simulation_model": model_name,
                "simulation_function": "",
                "default_preset": "",
            },
        }

        self.working_data["demos"][demo_id] = new_demo
        self.demo_sources[demo_id] = DemoSource(
            model_name=model_name,
            local_key=local_key,
            path=demo_file_for_model(self.env.models_dir, model_name),
        )

        self._refresh_demos(selected_key=demo_id)

    def _get_new_demo_dict(self, new= False):
        old_key = self._current_demo_key()
        if old_key and old_key in self.working_data.get("demos", {}):
            new_demo = copy.deepcopy(self.working_data["demos"][old_key])
        else:
            new_demo = {
                "name": "",
                "desc": "",
                "details": {}
            }

        new_demo["name"] = self.edit_demo_display_name.text()
        new_demo["desc"] = self.edit_demo_desc.toPlainText()

        details = new_demo.setdefault("details", {})
        details["plot_preprocess"] = (
            self.combo_preprocessing.currentText()
            if self.combo_preprocessing.currentText() != "None"
            else None
        )
        details["simulation_model"] = self.combo_model.currentText()
        details["simulation_function"] = self.combo_function.currentText()
        details["default_preset"] = self.combo_preset.currentText()

        if self.entry_sim_speed.text():
            try:
                float(self.entry_sim_speed.text())
                new_demo["details"]["simulation_speed"] = self.entry_sim_speed.text()
            except ValueError:
                pass

        return new_demo

    def _on_demo_selected(self, row: int) -> None:
        if row < 0:
            self._clear_demo_editor()
            return

        item = self.demo_list.currentItem()
        demo_id = item.data(qc.Qt.ItemDataRole.UserRole)
        source = self.demo_sources[demo_id]

        # choice = item.text()
        # demo = self.names_dict[choice]
        demo_dict = self.working_data["demos"][demo_id]
        # demo_dict = self.working_data["demos"][demo]

        self._loading_editor = True
        self._block_editor_signals(True)
        try:
            self.lbl_internal_name.setText(source.local_key)
            # self.lbl_internal_name.setText(demo)
            self.edit_demo_display_name.setText(demo_dict["name"])
            self.edit_demo_desc.setPlainText(demo_dict["desc"])

            details = demo_dict["details"]
            sim_speed = details.get("simulation_speed", "0.0")
            self.entry_sim_speed.setText(str(sim_speed))
            model_index = self.combo_model.findText(details["simulation_model"])

            self.combo_model.setCurrentText(source.model_name)
            # self.combo_model.setCurrentIndex(model_index)
            self._refresh_functions()
            self._refresh_presets()
            func_index = self.combo_function.findText(details["simulation_function"])
            preset_index = self.combo_preset.findText(details["default_preset"])
            plot_preprocess_func = details.get("plot_preprocess")
            if plot_preprocess_func is not None:
                pre_process_index = self.combo_preprocessing.findText(details["plot_preprocess"])
                self.combo_preprocessing.setCurrentIndex(pre_process_index)
            else:
                self.combo_preprocessing.setCurrentIndex(0)
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

    # def _save_demo_changes(self):
    #     if self._loading_editor:
    #         print(f"returning becaue loading editor")
    #         return
    #     old_key = self._current_demo_key()
    #     if not old_key:
    #         print("returning because not old key")
    #         return
    #     new_key = self.lbl_internal_name.text().strip()
    #     if not new_key:
    #         print(f"returning becauese not new key")
    #         return

    #     new_demo = self._get_new_demo_dict()
    #     old_demo = self.working_data["demos"].get(old_key, {})

    #     if isinstance(old_demo, dict) and old_demo.get("default"):
    #         new_demo["default"] = True

    #     # update under current key first
    #     self.working_data["demos"][old_key] = new_demo

    #     item = self.demo_list.currentItem()
    #     new_display = new_demo.get("name", "") or old_key
    #     if item is not None and item.text() != new_display:
    #         item.setText(new_display)

    #     if new_key == old_key:
    #         return

    #     if new_key in self.working_data["demos"]:
    #         self.window.status.show("That internal name is already in use.", msecs=2000)
    #         return

    #     replace_key_preserve_order(self.working_data["demos"], old_key, new_key, new_demo)
    #     self._refresh_demos(selected_key= new_key)

    def _save_demo_changes(self):
        if self._loading_editor:
            return

        old_id = self._current_demo_key()
        if not old_id:
            return

        old_source = self.demo_sources[old_id]

        new_model = self.combo_model.currentText().strip()
        new_local_key = self.lbl_internal_name.text().strip()

        if not new_model or not new_local_key:
            return

        new_id = make_demo_id(new_model, new_local_key)

        if new_id != old_id and new_id in self.working_data["demos"]:
            self.window.status.show(
                "That internal demo name is already used by this model.",
                4000,
            )
            return

        new_demo = self._get_new_demo_dict()
        new_demo.setdefault("details", {})["simulation_model"] = new_model

        if new_id == old_id:
            self.working_data["demos"][old_id] = new_demo
            return

        replace_key_preserve_order(
            self.working_data["demos"],
            old_id,
            new_id,
            new_demo,
        )

        self.demo_sources.pop(old_id)
        self.demo_sources[new_id] = DemoSource(
            model_name=new_model,
            local_key=new_local_key,
            path=demo_file_for_model(self.env.models_dir, new_model),
        )

        self._refresh_demos(selected_key=new_id)

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

    # def on_apply_clicked(self):

    #     self._normalize_for_dump(self.working_data)
    #     path = self.env.demos_file
    #     atomic_write(path, self.working_data)
    #     self.original_data = copy.deepcopy(self.working_data)
    #     self.working_data = copy.deepcopy(self.original_data)

    #     self._refresh_demos()

    def on_apply_clicked(self):
        if self.catalog_errors:
            self.window.status.show(
                "One or more demos.yml files could not be read. "
                "Fix them before saving to avoid data loss.",
                6000,
            )
            return

        # Start with the original documents so future top-level fields survive.
        documents = copy.deepcopy(self.original_documents)

        # Include model folders that did not previously have demos.yml.
        for model_name in refresh_models(self.env):
            documents.setdefault(model_name, {"demos": {}})

        # Rebuild only each document's demos mapping.
        for document in documents.values():
            document["demos"] = {}

        for demo_id, runtime_demo in self.working_data["demos"].items():
            source = self.demo_sources[demo_id]

            stored_demo = copy.deepcopy(runtime_demo)
            details = stored_demo.setdefault("details", {})

            # The folder is the source of truth.
            details.pop("simulation_model", None)

            document = documents.setdefault(
                source.model_name,
                {"demos": {}},
            )
            document["demos"][source.local_key] = stored_demo

        for model_name, document in documents.items():
            path = demo_file_for_model(self.env.models_dir, model_name)
            original = self.original_documents.get(
                model_name,
                {"demos": {}},
            )

            if document == original:
                continue

            # Avoid creating empty files for models that never had demos.
            if not document["demos"] and not path.exists():
                continue

            output = copy.deepcopy(document)
            self._normalize_for_dump(output)
            atomic_write(path, output)

        self._load_demo_catalog()
        self._refresh_demos()

        self.window.status.show("Demo settings saved.", 3000)

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
        self.combo_preprocessing.currentIndexChanged.connect(self._save_demo_changes)

        self.entry_sim_speed.textChanged.connect(self._save_demo_changes)

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
