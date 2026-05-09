from __future__ import annotations

import dataclasses
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import copy
import os
import yaml
from PyQt6 import QtCore as qc, QtGui as qg, QtWidgets as qw

from overseer.tools.loader import load_parameters_class_from_file, try_instantiate_with_defaults
from overseer.tools.creation_tools import flow_seqify, atomic_write
from overseer.widgets.common import refresh_models

def list_subdirs(path: str | os.PathLike) -> List[str]:
    p = Path(path)
    if not p.exists():
        return []
    return sorted([x.name for x in p.iterdir() if x.is_dir()])

def _yaml_inline(value: Any) -> str:
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

logger = logging.getLogger(__name__)

def safe_default_value(dc_field) -> Tuple[bool, Any]:
    """
    Returns (has_default, value).
    - has_default True means: either a literal default or a default_factory.
    - value is the default value when possible; if default_factory exists we call it.
    """
    # dataclasses.MISSING is not imported here; compare by repr-safe attr presence
    if getattr(dc_field, "default", dataclasses.MISSING) is not dataclasses.MISSING:
        return True, dc_field.default

    # Factory default
    factory = getattr(dc_field, "default_factory", dataclasses.MISSING)
    if factory is not dataclasses.MISSING:
        try:
            return True, factory()
        except Exception:
            # still counts as default, but we can't materialize it
            return True, None

    return False, None

# ---- UI row widget for one param in a preset ----
class _PresetParamRow(qw.QWidget):
    """
    Row UI for a single parameter.
    - required: override checkbox locked on
    - optional: override checkbox controls whether param is included in preset
    - value editor: line for scalars, yaml text for arrays/structures
    """
    changed = qc.pyqtSignal()
    removeRequested = qc.pyqtSignal(str)

    def __init__(self, name: str, required: bool, default_exists: bool, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.param_name = name
        self.required = required
        self.default_exists = default_exists

        lay = qw.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.lbl = qw.QLabel(name + ("*" if required else ""))
        self.lbl.setMinimumWidth(160)

        # heuristic editor choice: start with scalar editor, but allow multiline yaml
        self.edit_scalar = qw.QLineEdit()

        lay.addWidget(self.lbl, 0)
        lay.addWidget(self.edit_scalar, 1)


        self.edit_scalar.textChanged.connect(self.changed.emit)

        self.btn_remove = qw.QToolButton()
        self.btn_remove.setText("✕")  # or "x"
        self.btn_remove.setAutoRaise(True)
        self.btn_remove.setCursor(qg.QCursor(qc.Qt.CursorShape.PointingHandCursor))
        self.btn_remove.setToolTip("Remove from preset")

        # Only optional params can be removed
        # self.btn_remove.setEnabled(not self.required)
        # self.btn_remove.setVisible(not self.required)

        self.btn_remove.clicked.connect(lambda: self.removeRequested.emit(self.param_name))
        lay.addWidget(self.btn_remove, 0)


        # self._set_enabled_state()

    # def _on_any_changed(self) -> None:
    #     # self._set_enabled_state()
    #     self.changed.emit()

    def set_value(self, value: Any) -> None:
        # Choose representation based on current editor
        self.edit_scalar.blockSignals(True)
        self.edit_scalar.setText(_yaml_inline(value))
        self.edit_scalar.blockSignals(False)

    def get_included(self) -> bool:
        raw = self.edit_scalar.text().strip()
        if self.required:
            return True
        return raw != ""

    def get_value(self) -> Tuple[bool, Any, Optional[str]]:
        raw = self.edit_scalar.text().strip()

        if not self.get_included():
            return True, None, None
        if raw == "":
            return False, None, "Empty value"

        # Parse scalars/lists/dicts as YAML so numbers become int/float, true/false become bool, etc.
        try:
            val = yaml.safe_load(raw)
        except Exception as e:
            return False, None, f"Invalid YAML: {e}"

        # yaml.safe_load("") would be None, but we already guarded raw == ""
        return True, val, None

class PresetSettingsTab(qw.QWidget):
    """
    Edits models/<model>/data/params.yml -> top-level 'presets' mapping.

    Rules:
      1) A preset must specify values for params that have NO default in parameters.py
      2) Params with defaults are optional in presets; if not specified, defaults apply.
    """

    def __init__(self, env, model= None, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.window = self.window()  # expects window.status.show(...)
        self._current_model: Optional[str] = None

        self.env = env

        # caches
        self._working_data: Dict[str, Dict[str, Any]] = {}    # model -> entire yaml dict
        self._original_data: Dict[str, Dict[str, Any]] = {}   # model -> deep copy for revert
        self._param_meta: Dict[str, Dict[str, Any]] = {} # model -> {names, required, optional, defaults}

        self._current_preset_key: Optional[str] = None
        self._row_widgets: Dict[str, _PresetParamRow] = {}

        self._build_ui()
        self._refresh_models()

        if model is not None:
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            try:
                self.model_combo.setCurrentIndex(models.index(model))
            except ValueError:
                pass
            self._current_model = model

    # -------- public hook (matches your other tabs) --------
    def set_model(self, model_name: str):
        idx = self.model_combo.findText(model_name)
        self.model_combo.setCurrentIndex(idx)

    # ------------------------- UI -------------------------
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

        # left: preset list
        left_box = qw.QGroupBox("Presets")
        left_lay = qw.QVBoxLayout(left_box)
        self.preset_list = qw.QListWidget()
        self.preset_list.currentRowChanged.connect(self._on_preset_selected)
        left_lay.addWidget(self.preset_list, 1)

        btnrow = qw.QHBoxLayout()
        self.btn_add = qw.QPushButton("+ Preset")
        self.btn_del = qw.QPushButton("Remove")
        self.btn_add.clicked.connect(self._add_preset)
        self.btn_del.clicked.connect(self._remove_preset)
        btnrow.addWidget(self.btn_add)
        btnrow.addWidget(self.btn_del)
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

    # ------------------------- model switching -------------------------

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

    # ------------------------- loading -------------------------
    def _ensure_loaded(self, model: str) -> None:
        if model not in self._working_data:
            data = self._load_params_yml(model)
            self._working_data[model] = data
            self._original_data[model] = copy.deepcopy(data)
        if model not in self._param_meta:
            self._param_meta[model] = self._load_param_meta_from_parameters_py(model)

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
        Returns:
          {
            "names": [...],
            "required": set(...),
            "optional": set(...),
            "defaults": {name: default_value or None},
          }
        """
        path = self.env.models_dir / model / "simulation" / "parameters.py"
        try:
            Parameters = load_parameters_class_from_file(path)
        except FileNotFoundError:
            return {"names": [], "required": set(), "optional": set(), "defaults": {}}
        except Exception as e:
            self.window.status.show(f"Error importing parameters.py: {e}", 8000)
            return {"names": [], "required": set(), "optional": set(), "defaults": {}}

        required = set()
        optional = set()
        defaults: Dict[str, Any] = {}
        names: List[str] = []

        for f in fields(Parameters):
            names.append(f.name)
            has_def, defval = safe_default_value(f)
            if has_def:
                optional.add(f.name)
                defaults[f.name] = defval
            else:
                required.add(f.name)

        # As a convenience: try to instantiate defaults to better detect arrays via try_instantiate_with_defaults
        # (only improves defaults; required stays required)
        try:
            inst = try_instantiate_with_defaults(Parameters)
            if inst is not None:
                for n in names:
                    if n in optional:
                        try:
                            defaults[n] = getattr(inst, n)
                        except Exception:
                            pass
        except Exception:
            pass

        # --- detect array/matrix defaults for nicer YAML dump ---
        flowseq_params = set()
        matrix_params = set()

        try:
            import numpy as np
        except Exception:
            np = None

        for n, v in defaults.items():
            # numpy array default
            if np is not None and isinstance(v, np.ndarray):
                flowseq_params.add(n)
                if getattr(v, "ndim", 1) >= 2:
                    matrix_params.add(n)
                continue

            # python list default (matrix if list-of-lists)
            if isinstance(v, (list, tuple)):
                flowseq_params.add(n)
                if v and all(isinstance(r, (list, tuple)) for r in v):
                    matrix_params.add(n)

        meta = {"names": names, "required": required, "optional": optional, "defaults": defaults}
        meta["flowseq_params"] = flowseq_params
        meta["matrix_params"] = matrix_params
        return meta

        return {"names": names, "required": required, "optional": optional, "defaults": defaults}

    # ------------------------- preset list + selection -------------------------
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
        self.btn_del.setEnabled(False)

    def _load_preset_into_editor(self, preset_key: str) -> None:
        self._current_preset_key = preset_key
        self.btn_del.setEnabled(True)

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

        meta = self._param_meta.get(self._current_model or "", {"names": [], "required": set(), "defaults": {}})
        names: List[str] = meta["names"]
        required: set = meta["required"]
        defaults: Dict[str, Any] = meta["defaults"]

        for pname in names:
            is_req = pname in required
            has_default = pname in defaults

            roww = _PresetParamRow(pname, required=is_req, default_exists=has_default)
            self._row_widgets[pname] = roww

            if pname in preset_params:
                roww.set_value(preset_params[pname])
            else:
                # show default in UI if it exists; optional will only be included if user types something
                roww.set_value(defaults.get(pname, ""))

            roww.changed.connect(self._on_editor_changed)
            roww.removeRequested.connect(self._remove_param_row)
            self.param_form.addWidget(roww)

        self.param_form.addStretch(1)

    def _remove_param_row(self, pname: str) -> None:
        # required params are not removable (button should already be hidden)
        roww = self._row_widgets.get(pname)
        if not roww:
            return

        # Make it "not included" by clearing text
        roww.set_value("")     # ensures get_included() becomes False for optional :contentReference[oaicite:3]{index=3}
        roww.setVisible(False) # removes it from the visible list

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
                roww.lbl.setStyleSheet("color: #b00020;")
                continue
            roww.setToolTip("")
            roww.lbl.setStyleSheet("")
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

    # ------------------------- add/remove -------------------------
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
                meta = self._param_meta.get(model, {"required": set()})
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
