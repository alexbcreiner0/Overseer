from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
from os import name
from pathlib import Path
import re
import yaml
from dataclasses import fields, MISSING
from typing import Any, Callable, Optional
from importlib import import_module, reload
import numpy as np
from PyQt6 import QtCore as qc, QtWidgets as qw
from overseer.tools.loader import list_subdirs, open_in_known_editor
from overseer.tools.creation_tools import create_new_model_dir

class CheckFailure(Exception):
    """Raised for user-facing check failures with readable messages."""


def _required_param_names(ParamsCls: type) -> set[str]:
    req = set()
    for f in fields(ParamsCls):
        has_default = (f.default is not MISSING) or (f.default_factory is not MISSING)  # type: ignore
        if not has_default:
            req.add(f.name)
    return req


def _all_param_names(ParamsCls: type) -> set[str]:
    return {f.name for f in fields(ParamsCls)}


def _load_params_yml(env, model_name: str) -> dict[str, Any]:
    """
    Load models/<model>/data/params.yml and return the parsed dict.
    """
    path = Path(env.models_dir / model_name / "data" / "params.yml")
    if not path.exists():
        raise CheckFailure(f"Missing params.yml: {path}")
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception as e:
        raise CheckFailure(f"Could not parse params.yml ({path}): {e}")


def _extract_presets(params_yml: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Returns {preset_id: preset_dict}.
    Expects the structure you already use: presets -> <id> -> params -> ...
    """
    presets = params_yml.get("presets") or {}
    if not isinstance(presets, dict) or not presets:
        raise CheckFailure("params.yml has no presets section (or it is empty).")
    # normalize missing 'params' to {}
    out: dict[str, dict[str, Any]] = {}
    for pid, pdata in presets.items():
        if not isinstance(pdata, dict):
            out[pid] = {"params": {}}
            continue
        out[pid] = pdata
        if "params" not in out[pid] or out[pid]["params"] is None:
            out[pid]["params"] = {}
    return out

def _coerce_field_value(f, value):
    """
    Coerce YAML-loaded values into the type expected by the Params dataclass field.
    Primary goal: lists -> np.ndarray for ndarray fields.
    Secondary goal: basic scalar coercions for int/float/bool/str.
    """
    if value is None:
        return value

    # Normalize type objects we may see (numpy.ndarray imported as `ndarray`)
    ann = getattr(f, "type", None)

    # ---- ndarray coercion ----
    # Works whether annotation is numpy.ndarray or numpy.ndarray alias from `from numpy import ndarray`
    if ann is not None:
        ann_name = getattr(ann, "__name__", str(ann))
        if ann is np.ndarray or ann_name == "ndarray":
            if isinstance(value, np.ndarray):
                return value
            if isinstance(value, (list, tuple)):
                return np.array(value)
            # if someone put a scalar, make it a 0d/1d array (your call)
            return np.array(value)

    # ---- simple scalar coercions (optional but helpful) ----
    if ann in (int, float, str):
        try:
            return ann(value)
        except Exception:
            return value

    if ann is bool:
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "yes", "1", "on"):
                return True
            if v in ("false", "no", "0", "off"):
                return False
        return bool(value)

    return value

def _construct_params_from_preset(ParamsCls: type, preset_params: dict[str, Any]) -> Any:
    """
    Instantiate ParamsCls using:
      - preset values when provided
      - dataclass defaults/default_factory otherwise
    If a required field is missing from the preset and has no default -> raise CheckFailure.
    """
    kwargs: dict[str, Any] = {}
    for f in fields(ParamsCls):
        if f.name in preset_params:
            kwargs[f.name] = _coerce_field_value(f, preset_params[f.name])
            continue

        if f.default is not MISSING:
            kwargs[f.name] = f.default
            continue

        if f.default_factory is not MISSING:  # type: ignore
            kwargs[f.name] = f.default_factory()  # type: ignore
            continue

        raise CheckFailure(f"Required param '{f.name}' is missing and has no default.")

    return ParamsCls(**kwargs)


def _load_model_modules(model_name: str):
    """
    Returns (ParamsCls, sim_module).
    """
    try:
        params_mod = import_module(f"models.{model_name}.simulation.parameters")
        params_mod = reload(params_mod)
    except Exception as e:
        raise CheckFailure(f"Could not import parameters.py for model '{model_name}': {e}")

    try:
        sim_mod = import_module(f"models.{model_name}.simulation.simulation")
        sim_mod = reload(sim_mod)
    except Exception as e:
        raise CheckFailure(f"Could not import simulation.py for model '{model_name}': {e}")

    ParamsCls = getattr(params_mod, "Params", None)
    if ParamsCls is None:
        raise CheckFailure("parameters.py must define a dataclass named 'Params'.")

    return ParamsCls, sim_mod


def _list_sim_functions(sim_mod):
    """
    By convention: every user-defined top-level function in simulation.py is treated as
    a candidate simulation function.
    """
    funcs: list[tuple[str, Callable]] = []
    for name, obj in vars(sim_mod).items():
        if name == "MODEL_READY":
            if obj == False:
                return funcs, False
        if not callable(obj):
            continue
        # avoid private helpers + imported callables
        if name.startswith("_"):
            continue
        # must be defined in this module (not imported)
        if getattr(obj, "__module__", None) != sim_mod.__name__:
            continue
        funcs.append((name, obj))
    funcs.sort(key=lambda x: x[0].lower())
    if not funcs:
        raise CheckFailure("simulation.py defines no public functions to test.")
    return funcs, True


def _check_sim_contract(func_name: str, func: Callable, params: Any) -> list[str]:
    """
    Contract:
      - callable accepts one argument (params) OR can be called with (params) without TypeError
      - returns (traj, t, e)
      - traj is dict
      - t is 1D array-like
      - e is None or BaseException
    """
    try:
        out = func(params)
    except TypeError as e:
        raise CheckFailure(f"{func_name} could not be called as {func_name}(params): {e}")
    except Exception as e:
        raise CheckFailure(f"{func_name} raised an exception: {e}")

    if not isinstance(out, tuple) or len(out) != 3:
        raise CheckFailure(f"{func_name} must return a 3-tuple (traj, t, e). Got: {type(out).__name__}.")

    traj, t, e = out

    if not isinstance(traj, dict):
        raise CheckFailure(f"{func_name}: traj must be a dict, got {type(traj).__name__}.")

    t_arr = np.asarray(t)
    if t_arr.ndim != 1:
        raise CheckFailure(f"{func_name}: t must be 1D, got shape {t_arr.shape}.")

    if e is not None and not isinstance(e, BaseException):
        raise CheckFailure(f"{func_name}: e must be None or an Exception, got {type(e).__name__}.")

    return [f"{func_name} returned (traj, t, e) with valid basic types."]


def run_model_diagnostics(env, model_name: str) -> list[str]:
    """
    One combined report:
      - presets coverage diagnostics across ALL presets
      - simulation function contract checks across ALL functions in simulation.py
        (tested using EVERY preset, reporting per-preset failures)
    Returns lines to display.
    """
    lines: list[str] = []

    ParamsCls, sim_mod = _load_model_modules(model_name)
    params_yml = _load_params_yml(env, model_name)
    presets = _extract_presets(params_yml)
    sim_funcs, ready = _list_sim_functions(sim_mod)

    req = _required_param_names(ParamsCls)
    known = _all_param_names(ParamsCls)

    # ---- Preset checks (ALL presets) ----
    lines.append("Preset checks")
    any_preset_error = False
    any_warning_error = False

    for pid, pdata in presets.items():
        pparams = pdata.get("params") or {}
        if not isinstance(pparams, dict):
            lines.append(f"  ❌ {pid}: params is not a mapping/dict")
            any_preset_error = True
            continue

        provided = set(pparams.keys())
        missing_req = sorted(req - provided)
        unknown_keys = sorted(provided - known)

        if missing_req:
            any_preset_error = True
            lines.append(f"  ❌ {pid}: missing required params: {', '.join(missing_req)}")

        # else:

        if unknown_keys:
            # warning only (typos or extra config)
            lines.append(f"  ⚠️  {pid}: unknown params (not in Params dataclass): {', '.join(unknown_keys)}")
            any_warning_error = True

    if not any_preset_error:
        if any_warning_error:
            lines.append(f" ⚠️ All checks passed with some warnings.")
        else:
            lines.append(f"  ✅ All checks passed.")
    if any_preset_error:
        lines.append("")

    # ---- Simulation function checks (ALL functions, tested against ALL presets) ----
    lines.append("Simulation function checks")

    if not ready:
        lines.append(f" ⚠️ Model marked not ready (MODEL_READY=False)")

    for func_name, func in sim_funcs:
        tried_preset = False
        lines.append(f"  • {func_name}")

        # test against every preset, report failures per preset
        for pid, pdata in presets.items():
            if tried_preset:
                continue
            pparams = pdata.get("params") or {}
            missing_req = req - set(pparams.keys())
            if not isinstance(pparams, dict):
                lines.append(f"    ❌ preset '{pid}': params is not a dict")
                continue

            # If preset missing required, skip running this function (but we already reported preset error above)
            if missing_req:
                lines.append(f"    ⏭️  preset '{pid}': skipped (missing required params)")
                continue

            try:
                tried_preset = True
                params_obj = _construct_params_from_preset(ParamsCls, pparams)
            except CheckFailure as e:
                lines.append(f"    ❌ preset '{pid}': Params construction failed: {e}")
                continue
            except Exception as e:
                lines.append(f"    ❌ preset '{pid}': Params construction raised: {e}")
                continue

            try:
                msgs = _check_sim_contract(func_name, func, params_obj)
                for m in msgs:
                    lines.append(f"    ✅ preset '{pid}': {m}")
            except CheckFailure as e:
                lines.append(f"    ❌ preset '{pid}': {e}")

        if not tried_preset:
            lines.append(f" ❌ No valid presets found to test sim function on.")

        lines.append("")  # blank line between functions

    return lines

class ModelSettingsTab(qw.QWidget):

    modelSelected = qc.pyqtSignal(str)
    modelsChanged = qc.pyqtSignal()
    newModelCreated = qc.pyqtSignal()

    def __init__(self, env, model= None, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.window = self.window()  

        root = qw.QVBoxLayout(self)

        top = qw.QHBoxLayout()
        top.addWidget(qw.QLabel("Models"))
        top.addStretch(1)

        self.btn_refresh = qw.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_models)
        top.addWidget(self.btn_refresh)

        self.env = env

        root.addLayout(top)

        splitter = qw.QSplitter(qc.Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = qw.QWidget()
        left_l = qw.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)

        self.model_list = qw.QListWidget()
        self.model_list.setSelectionMode(qw.QAbstractItemView.SelectionMode.SingleSelection)
        self.model_list.currentTextChanged.connect(self._on_model_selected)
        left_l.addWidget(self.model_list, 1)

        splitter.addWidget(left)

        # ========= Right: details / actions =========
        right = qw.QWidget()
        right_l = qw.QVBoxLayout(right)
        # right_l.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = qw.QLabel("Select a model")
        f = self.lbl_title.font()
        f.setPointSize(max(10, f.pointSize() + 2))
        f.setBold(True)
        self.lbl_title.setFont(f)
        right_l.addWidget(self.lbl_title)

        self.info_box = qw.QPlainTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setMinimumHeight(120)

        right_l.addWidget(self.info_box, 1)

        actions = qw.QHBoxLayout()
        self.btn_run_checks = qw.QPushButton("Run checks")
        self.btn_run_checks.clicked.connect(self._run_checks_clicked)
        self.btn_run_checks.setEnabled(False)
        actions.addWidget(self.btn_run_checks)

        self.btn_open_in_editor = qw.QPushButton("Open in editor")
        self.btn_open_in_editor.clicked.connect(self.open_in_editor)
        actions.addWidget(self.btn_open_in_editor)

        actions.addStretch(1)
        right_l.addLayout(actions)


        new_box = qw.QGroupBox("New Model Creation")
        nb_l = qw.QVBoxLayout(new_box)
        nb_l.setContentsMargins(10, 10, 10, 10)

        top_row = qw.QHBoxLayout()

        name_label = qw.QLabel("Model / Directory Name")
        self.new_model_name_entry = qw.QLineEdit()
        self.new_model_name_entry.setPlaceholderText("e.g. Goodwin growth model")

        self.new_model_create_button = qw.QPushButton("Create Directory")
        self.new_model_create_button.clicked.connect(self._create_model_clicked)

        top_row.addWidget(name_label)
        top_row.addWidget(self.new_model_name_entry, 1)
        top_row.addWidget(self.new_model_create_button)

        nb_l.addLayout(top_row)

        self.success_text = qw.QLabel()
        self.success_text.setWordWrap(True)
        self.success_text.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Preferred,
        )
        self.success_text.setTextFormat(qc.Qt.TextFormat.RichText)
        self.success_text.setTextInteractionFlags(qc.Qt.TextInteractionFlag.TextSelectableByMouse)

        self.success_text.setMinimumHeight(80)

        nb_l.addWidget(self.success_text)

        right_l.addWidget(new_box)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        self._current_model: Optional[str] = None
        self._diag_cache: dict[str, str] = {}   # model_name -> rendered info_box text

        self.refresh_models(select_first=True)
        for model in list_subdirs(self.env.models_dir):
            self._diag_cache[model] = "Click the 'run checks' button to display model diagnostics."

        if model is not None:
            self.set_model(model)

    # -------------------------
    # Public
    # -------------------------

    def set_model(self, name):
        result = self.model_list.findItems(name, qc.Qt.MatchFlag.MatchExactly)
        if result != []:
            idx = self.model_list.indexFromItem(result[0])
            self.model_list.setCurrentIndex(idx)
            self._current_model = name

    def refresh_models(self, *, select_first: bool = False) -> None:
        """Reload the list of models from disk."""
        prev = self._current_model
        models = list_subdirs(self.env.models_dir)
        self.model_list.clear()
        self._diag_cache.clear()
        self.model_list.addItems(models)

        # restore selection if possible
        if prev and prev in models:
            self.model_list.setCurrentRow(models.index(prev))
        elif select_first and models:
            self.model_list.setCurrentRow(0)

        self.modelsChanged.emit()

    # -------------------------
    # Internals
    # -------------------------

    def _on_model_selected(self, model_name: str) -> None:
        model_name = (model_name or "").strip()
        self._current_model = model_name or None

        if not self._current_model:
            self.btn_run_checks.setEnabled(False)
            self.lbl_title.setText("Select a model")
            self.info_box.setPlainText("")
            return

        self.btn_run_checks.setEnabled(True)
        self.lbl_title.setText(f"Model: {self._current_model}")

        cached = self._diag_cache.get(self._current_model)
        if cached is not None:
            self.info_box.setPlainText(cached)
        # else:
        #     self._run_all_checks(self._current_model, show_status=False)

        self.modelSelected.emit(self._current_model)

    def _basic_file_check_lines(self, model_name: str) -> list[str]:
        base = self.env.models_dir / model_name

        checks = [
            ("data/plotting_data.yml", base / "data" / "plotting_data.yml"),
            ("data/control_panel_data.yml", base / "data" / "control_panel_data.yml"),
            ("data/params.yml", base / "data" / "params.yml"),
            ("simulation/parameters.py", base / "simulation" / "parameters.py"),
            ("simulation/simulation.py", base / "simulation" / "simulation.py"),
        ]

        lines = [f"Folder: {base}", ""]
        for label, path in checks:
            lines.append(f"{'OK ' if path.exists() else 'MISSING'}  {label}")
        return lines


    def _run_all_checks(self, model_name: str, *, show_status: bool) -> None:

        lines: list[str] = []

        # Always include file checks first
        lines.extend(self._basic_file_check_lines(model_name))
        lines.append("")
        lines.append("=== Diagnostics ===")

        try:
            for msg in run_model_diagnostics(self.env, model_name):
                lines.append(msg)

            if show_status:
                self.window.status.show(f"Checks passed for {model_name}.", 4000)

        except CheckFailure as e:
            lines.append("")
            lines.append("❌ Check failed")
            lines.append(str(e))
            if show_status:
                self.window.status.show(f"Checks failed for {model_name}.", 6000)

        text = "\n".join(lines)
        self.info_box.setPlainText(text)
        self._diag_cache[model_name] = text

    def _run_checks_clicked(self) -> None:
        if not self._current_model:
            return
        self._run_all_checks(self._current_model, show_status=True)

    def open_in_editor(self):
        name = self._current_model
        path = self.env.models_dir

        settings = self.parentWidget().parentWidget().settings
        preferred_editor = settings.get("preferred_editor")
        preferred_terminal = settings.get("preferred_terminal")
        open_in_known_editor(path, name, self.env, preferred_editor, preferred_terminal)

    def _create_model_clicked(self) -> None:
        name = self._make_shortname(self.new_model_name_entry.text().strip())
        if not name:
            self.window.status.show("Please enter a name.", 4000)
            return
        
        result = self.model_list.findItems(name, qc.Qt.MatchFlag.MatchExactly)
        if result != []:
            self.window.status.show("Name is already in use. Please either rename or choose something different.", 4000)
            return

        try:
            create_new_model_dir(self.env, name, gui_dialog= True)
            self._diag_cache.pop(name, None)
            self._update_new_model_created_text(name)
            self.newModelCreated.emit()
        except Exception as e:
            self.window.status.show(f"Something went wrong: {e}", 4000)
            logger.log(logging.ERROR, f"Error creating new model", exc_info= e)

        self.refresh_models(select_first=False)

    def _update_new_model_created_text(self, name: str) -> None:
        self.success_text.setText(
            f"""
            <div>
              <b>Model '{name}' created.</b><br/>
              Next steps:
              <ol style="margin-top: 6px; margin-left: 18px; padding-left: 0px;">
                <li>Create parameters and define your trajectory function. For at least the latter of these, you’ll need to leave this application and edit <code>simulation.py</code>.</li>
                <li>Come back here and run the checks.</li>
                <li>Create some plots.</li>
                <li>Create controls.</li>
                <li>Create a demo.</li>
                <li>Apply, close this window, and load your demo.</li>
              </ol>
            </div>
            """
        )

    def on_apply_clicked(self):
        pass

    def _make_shortname(self, display_name: str) -> str:
        s = display_name.lower()
        # replace spaces and punctuation with underscores
        s = re.sub(r"[^a-z0-9]+", "_", s)
        # collapse multiple underscores
        s = re.sub(r"_+", "_", s)
        s = s.strip("_")
        return s
