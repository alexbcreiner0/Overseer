from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import dataclasses
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import copy
import os
import yaml
import numpy as np
from PyQt6 import QtCore as qc, QtGui as qg, QtWidgets as qw

from overseer.tools.loader import load_parameters_class_from_file, try_instantiate_with_defaults
from overseer.tools.creation_tools import flow_seqify, atomic_write
from overseer.widgets.common import refresh_models, get_default_value

def _yaml_inline(value: Any) -> str:
    """ return a string representation of a parameter value """
    if value is None:
        return ""

    # numpy arrays stringify without commas; convert first
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            value = value.tolist()
    except Exception:
        pass

    if isinstance(value, (list, tuple, dict)):
        # Flow style => [[1, 2], [3, 4]] (commas included)
        return yaml.safe_dump(
            value,
            default_flow_style=True,
            sort_keys=False,
            allow_unicode=True,
        ).strip()

    return str(value)

_MISSING = object()

class PresetParamRow(qw.QWidget):
    """
    Widget representing a single row of a single preset.
    - required: override checkbox locked on
    - optional: override checkbox controls whether param is included in preset
    - value editor: line for scalars, yaml text for arrays/structures
    """
    valueChanged = qc.pyqtSignal()
    removeRequested = qc.pyqtSignal(str)

    def __init__(self, name: str, required: bool, default_exists: bool, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.param_name = name
        self.required = required
        self.default_exists = default_exists

        lay = qw.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.param_label = qw.QLabel(name + ("*" if required else ""))
        self.param_label.setMinimumWidth(160)

        self.value_edit = qw.QLineEdit()

        lay.addWidget(self.param_label, 0)
        lay.addWidget(self.value_edit, 1)

        self.value_edit.textChanged.connect(self.valueChanged.emit)

        self.remove_button = qw.QToolButton()
        self.remove_button.setText("✕")  # or "x"
        self.remove_button.setAutoRaise(True)
        self.remove_button.setCursor(qg.QCursor(qc.Qt.CursorShape.PointingHandCursor))
        self.remove_button.setToolTip("Remove from preset")

        self.remove_button.clicked.connect(lambda: self.removeRequested.emit(self.param_name))
        lay.addWidget(self.remove_button, 0)

    def set_value(self, value: Any) -> None:
        self.value_edit.blockSignals(True)
        self.value_edit.setText(_yaml_inline(value))
        self.value_edit.blockSignals(False)

    def get_included(self) -> bool:
        raw = self.value_edit.text().strip()
        if self.required:
            return True
        return raw != ""

    def get_value(self) -> Tuple[bool, Any, Optional[str]]:
        raw = self.value_edit.text().strip()

        if not self.get_included():
            return True, None, None
        if raw == "":
            return False, None, "Empty value"

        try:
            val = yaml.safe_load(raw)
        except Exception as e:
            return False, None, f"Invalid YAML: {e}"

        return True, val, None

class PresetSettingsTab(qw.QWidget):
    def __init__(self, env, model= None, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.window = self.window()  
        self._current_model: Optional[str] = None

        self.env = env

        self._working_data: Dict[str, Dict[str, Any]] = {}    # model_name -> entire yaml dict
        self._original_data: Dict[str, Dict[str, Any]] = {}
        self._params_metadata: Dict[str, Dict[str, Any]] = {} # model -> {names, required, optional, defaults}

        self._current_preset_key: Optional[str] = None
        self._row_widgets: Dict[str, PresetParamRow] = {}

        self._build_ui()
        self._refresh_models()

        if model is not None:
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            try:
                self.model_combo.setCurrentIndex(models.index(model))
            except ValueError:
                pass
            self._current_model = model

    def set_model(self, model_name: str):
        idx = self.model_combo.findText(model_name)
        self.model_combo.setCurrentIndex(idx)

    def _build_ui(self) -> None:
        root = qw.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        top = qw.QHBoxLayout()
        root.addLayout(top, 0)

        self.model_combo = qw.QComboBox()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        top.addWidget(qw.QLabel("Model:"))
        top.addWidget(self.model_combo, 1)


        body = qw.QHBoxLayout()
        root.addLayout(body, 1)

        left_box = qw.QGroupBox("Presets")
        left_lay = qw.QVBoxLayout(left_box)
        self.preset_list = qw.QListWidget()
        self.preset_list.currentRowChanged.connect(self._on_preset_selected)
        left_lay.addWidget(self.preset_list, 1)

        btnrow = qw.QHBoxLayout()
        self.add_button = qw.QPushButton("+ Preset")
        self.delete_button = qw.QPushButton("Remove")
        self.refresh_button = qw.QPushButton("Refresh params")
        self.add_button.clicked.connect(self._add_preset)
        self.delete_button.clicked.connect(self._remove_preset)
        self.refresh_button.clicked.connect(self.refresh_rows)
        btnrow.addWidget(self.add_button)
        btnrow.addWidget(self.delete_button)
        btnrow.addWidget(self.refresh_button)
        btnrow.addStretch(1)
        left_lay.addLayout(btnrow)

        body.addWidget(left_box, 0)

        # right: editor
        right_box = qw.QGroupBox("Preset editor")
        right_lay = qw.QVBoxLayout(right_box)

        form = qw.QFormLayout()
        self.edit_key = qw.QLineEdit()
        self.edit_name = qw.QLineEdit()
        self.edit_desc = qw.QLineEdit()
        self.edit_key.setPlaceholderText("internal key (snake_case)")
        self.edit_name.setPlaceholderText("display name")
        self.edit_desc.setPlaceholderText("description / asset key / notes")
        form.addRow("Key:", self.edit_key)
        form.addRow("Name:", self.edit_name)
        form.addRow("Desc:", self.edit_desc)
        right_lay.addLayout(form)

        self.hint = qw.QLabel(
            "Parameters marked with * are required (no default value found in parameters.py)."
        )
        self.hint.setWordWrap(True)
        right_lay.addWidget(self.hint)

        # scroll area for many params
        self.scroll = qw.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.param_container = qw.QWidget()
        self.param_form = qw.QVBoxLayout(self.param_container)
        self.param_form.setContentsMargins(8, 8, 8, 8)
        self.param_form.setSpacing(6)
        self.param_form.addStretch(1)
        self.scroll.setWidget(self.param_container)
        right_lay.addWidget(self.scroll, 1)

        body.addWidget(right_box, 1)

        # apply/save buttons are handled by dialog; we provide an apply method like other tabs
        # (call this from EditConfigDialog._on_apply_clicked)
        # self.on_apply_clicked_presets()

        # wire changes
        self.edit_key.textChanged.connect(self._on_editor_changed)
        self.edit_name.textChanged.connect(self._on_editor_changed)
        self.edit_desc.textChanged.connect(self._on_editor_changed)

    def _refresh_models(self) -> None:
        models = refresh_models(self.env)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, model: str) -> None:
        if not model:
            return
        self._current_model = model
        self._ensure_loaded(model)
        self._refresh_preset_list()

    def _ensure_loaded(self, model: str) -> None:
        if model not in self._working_data:
            data = self._load_params_yml(model)
            self._working_data[model] = data
            self._original_data[model] = copy.deepcopy(data)
        if model not in self._params_metadata:
            self._params_metadata[model] = self._load_param_meta_from_parameters_py(model)

    def _load_params_yml(self, model: str) -> Dict[str, Any]:
        path = self.env.models_dir / model / "data" / "params.yml"
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raw = {}
        except Exception as e:
            self.window.status.show(f"Error opening params.yml: {e}", 7000)
            raw = {}
        raw.setdefault("presets", {})
        return raw

    def _load_param_meta_from_parameters_py(self, model: str) -> Dict[str, Any]:
        """
        Populates the self._params_metadata dictionary, which ends up looking like this:
          {
            "names": [...],
            "required": set(...),
            "optional": set(...),
            "defaults": {name: default_value or None},
          }
        """
        path = self.env.models_dir / model / "simulation" / "parameters.py"
        try:
            Params = load_parameters_class_from_file(path)
        except FileNotFoundError:
            return {"names": [], "required": set(), "optional": set(), "defaults": {}}
        except Exception as e:
            self.window.status.show(f"Error importing parameters.py: {e}", 4000)
            return {"names": [], "required": set(), "optional": set(), "defaults": {}}

        required = set()
        optional = set()
        defaults: Dict[str, Any] = {}
        names: List[str] = []

        for field in fields(Params):
            names.append(field.name)
            has_default, default_value = get_default_value(field)
            if has_default:
                optional.add(field.name)
                defaults[field.name] = default_value
            else:
                required.add(field.name)

        # if you can create an instance of the dataclass, use that for better accuracy
        try:
            instance = try_instantiate_with_defaults(Params)
            if instance is not None:
                for param_name in names:
                    if param_name in optional:
                        try:
                            defaults[param_name] = getattr(instance, param_name)
                        except Exception:
                            pass
        except Exception:
            pass

        flowseq_params = set()
        matrix_params = set()

        for param_name, default_value in defaults.items():
            if isinstance(default_value, np.ndarray):
                flowseq_params.add(param_name)
                if getattr(default_value, "ndim", 1) >= 2:
                    matrix_params.add(param_name)
                continue

            if isinstance(default_value, (list, tuple)):
                flowseq_params.add(param_name)
                if default_value and all(isinstance(r, (list, tuple)) for r in default_value):
                    matrix_params.add(param_name)

        meta = {"names": names, "required": required, "optional": optional, "defaults": defaults}
        meta["flowseq_params"] = flowseq_params
        meta["matrix_params"] = matrix_params
        return meta

    def _refresh_preset_list(self) -> None:
        self.preset_list.blockSignals(True)
        self.preset_list.clear()

        if not self._current_model:
            self.preset_list.blockSignals(False)
            return

        presets = self._working_data[self._current_model].get("presets", {}) or {}
        for key in sorted(presets.keys()):
            item = qw.QListWidgetItem(key)
            self.preset_list.addItem(item)

        self.preset_list.blockSignals(False)

        if self.preset_list.count() > 0:
            self.preset_list.setCurrentRow(0)
        else:
            self._clear_editor()

    def _on_preset_selected(self, row: int) -> None:
        if not self._current_model:
            return
        if row < 0 or row >= self.preset_list.count():
            self._clear_editor()
            return
        key = self.preset_list.item(row).text()
        self._load_preset_into_editor(key)

    def _clear_editor(self) -> None:
        self._current_preset_key = None
        self.edit_key.blockSignals(True)
        self.edit_name.blockSignals(True)
        self.edit_desc.blockSignals(True)
        self.edit_key.setText("")
        self.edit_name.setText("")
        self.edit_desc.setText("")
        self.edit_key.blockSignals(False)
        self.edit_name.blockSignals(False)
        self.edit_desc.blockSignals(False)
        self._rebuild_param_rows({})
        self.delete_button.setEnabled(False)

    def _load_preset_into_editor(self, preset_key: str) -> None:
        self._current_preset_key = preset_key
        self.delete_button.setEnabled(True)

        preset = (self._working_data[self._current_model].get("presets", {}) or {}).get(preset_key, {}) or {}
        name = str(preset.get("name", ""))
        desc = str(preset.get("desc", ""))
        params = preset.get("params", {}) or {}

        self.edit_key.blockSignals(True)
        self.edit_name.blockSignals(True)
        self.edit_desc.blockSignals(True)
        self.edit_key.setText(preset_key)
        self.edit_name.setText(name)
        self.edit_desc.setText(desc)
        self.edit_key.blockSignals(False)
        self.edit_name.blockSignals(False)
        self.edit_desc.blockSignals(False)

        self._rebuild_param_rows(params)

    def _rebuild_param_rows(self, preset_params: Dict[str, Any]) -> None:
        while self.param_form.count() > 0:
            item = self.param_form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        self._row_widgets.clear()

        meta = self._params_metadata.get(self._current_model or "", {"names": [], "required": set(), "defaults": {}})
        names: List[str] = meta["names"]
        required: set = meta["required"]
        defaults: Dict[str, Any] = meta["defaults"]

        for param_name in names:
            is_required = param_name in required
            has_default = param_name in defaults

            param_row = PresetParamRow(param_name, required=is_required, default_exists=has_default)
            self._row_widgets[param_name] = param_row

            if param_name in preset_params:
                param_row.set_value(preset_params[param_name])
            else:
                # show default in UI if it exists; optional will only be included if user types something
                param_row.set_value(defaults.get(param_name, ""))

            param_row.valueChanged.connect(self._on_editor_changed)
            param_row.removeRequested.connect(self._remove_param_row)
            self.param_form.addWidget(param_row)

        self.param_form.addStretch(1)

    def refresh_rows(self):
        model = self.model_combo.currentText()
        if not model:
            return

        self._params_metadata[model] = self._load_param_meta_from_parameters_py(model)
        current_preset = (self._working_data[self._current_model].get("presets", {}) or {}).get(self._current_preset_key, {}) or {}
        current_params = current_preset.get("params", {}) or {}
        self._rebuild_param_rows(current_params)

    def _remove_param_row(self, param_name: str) -> None:
        """ 'removes' a parameter specification by just clearing the row and hiding it. """
        param_row = self._row_widgets.get(param_name)
        if param_row is None:
            return

        param_row.set_value("")     
        param_row.setVisible(False) 

        # Persist change into working yaml
        self._on_editor_changed()

    def _on_editor_changed(self) -> None:
        if not self._current_model or not self._current_preset_key:
            return

        old_key = self._current_preset_key
        new_key = self.edit_key.text().strip()

        presets = self._working_data[self._current_model].setdefault("presets", {})
        if old_key not in presets:
            return

        payload: Dict[str, Any] = presets[old_key]
        payload["name"] = self.edit_name.text().strip()
        payload["desc"] = self.edit_desc.text().strip()

        params_out: Dict[str, Any] = {}
        for pname, roww in self._row_widgets.items():
            ok, val, err = roww.get_value()
            if not ok:
                roww.setToolTip(err or "Invalid")
                roww.param_label.setStyleSheet("color: #b00020;")
                continue
            roww.setToolTip("")
            roww.param_label.setStyleSheet("")
            if roww.get_included():
                params_out[pname] = val
        payload["params"] = params_out

        if new_key and new_key != old_key:
            if new_key in presets:
                self.window.status.show(f"Preset key '{new_key}' already exists.", 4000)
                self.edit_key.blockSignals(True)
                self.edit_key.setText(old_key)
                self.edit_key.blockSignals(False)
                return

            presets[new_key] = payload
            del presets[old_key]
            self._current_preset_key = new_key

            self._refresh_preset_list()
            self._select_preset_key(new_key)

    def _select_preset_key(self, key: str) -> None:
        for i in range(self.preset_list.count()):
            if self.preset_list.item(i).text() == key:
                self.preset_list.setCurrentRow(i)
                return

    def _add_preset(self) -> None:
        if not self._current_model:
            return
        presets = self._working_data[self._current_model].setdefault("presets", {})

        base = "new_preset"
        k = base
        i = 1
        while k in presets:
            i += 1
            k = f"{base}_{i}"

        presets[k] = {"name": "New preset", "desc": "", "params": {}}
        self._refresh_preset_list()
        self._select_preset_key(k)

    def _remove_preset(self) -> None:
        if not self._current_model or not self._current_preset_key:
            return
        presets = self._working_data[self._current_model].get("presets", {})
        if self._current_preset_key in presets:
            del presets[self._current_preset_key]
        self._refresh_preset_list()

    def on_apply_clicked(self) -> None:
        flow_seqify(self._working_data)
        try:
            for model in self._working_data:
                meta = self._params_metadata.get(model, {"required": set()})
                required = meta["required"]

                presets = self._working_data[model].get("presets", {}) or {}
                for pkey, pobj in presets.items():
                    pparams = (pobj or {}).get("params", {}) or {}
                    missing = [r for r in required if r not in pparams or pparams[r] in ("", None)]
                    if missing:
                        self.window.status.show(
                            f"Model '{model}': preset '{pkey}' missing required params: {', '.join(sorted(missing))}",
                            9000
                        )
                        return
                    
                path = self.env.models_dir / model / "data" / "params.yml"
                new_dict = self._working_data[model]
                atomic_write(path, new_dict)
        except Exception as e:
            self.window.status.show(f"Error writing changes: {e}", 8000)
            logger.log(logger.ERROR, "Error writing changes", exc_info= e)
        else:
            for model in self._working_data:
                self._original_data[model] = copy.deepcopy(self._working_data[model])
