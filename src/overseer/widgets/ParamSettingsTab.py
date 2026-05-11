from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import copy
import importlib.util
import keyword
import os, re, ast
from dataclasses import MISSING, dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from overseer.tools.creation_tools import atomic_write
from overseer.tools.loader import load_parameters_class_from_file
from .common import refresh_models, get_default_value

import numpy as np
from numpy import ndarray

from PyQt6 import QtCore as qc, QtGui as qg, QtWidgets as qw

@dataclass
class ParamSpec:
    name: str
    data_type: str
    value: Any = None  # scalar default OR ndarray for vector/matrix OR str/bool
    annotation: Optional[str] = None  # optional human-friendly hint

class ParamSettingsTab(qw.QWidget):
    """
    GUI editor for models/<model>/simulation/parameters.py.

    Supports:
      - load Parameters dataclass (by importing parameters.py)
      - add / remove / rename parameters
      - set scalar type, vector/matrix shape, initial values
      - apply writes parameters.py (backups .bak)

    Assumption: parameters.py is *generated* (or at least safe to overwrite).
    If you need to preserve custom code, we'll need a different strategy.
    """

    availableParamsChanged = qc.pyqtSignal(str, list)
    paramSettingsChanged = qc.pyqtSignal()

    def __init__(self, env, model= None, parent=None):
        super().__init__(parent)
        self.window = self.window()

        self.env = env

        self._current_model: Optional[str] = None
        self._original_data: Dict[str, List[ParamSpec]] = {}
        self._working_data: Dict[str, List[ParamSpec]] = {}
        self._current_spec: Optional[ParamSpec] = None

        root = qw.QVBoxLayout(self)

        top = qw.QHBoxLayout()
        top.addWidget(qw.QLabel("Model:"))
        self.model_combo = qw.QComboBox()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        top.addWidget(self.model_combo, 1)

        self.btn_reload = qw.QPushButton("Reload")
        self.btn_reload.clicked.connect(self._reload_current_model)
        top.addWidget(self.btn_reload)

        root.addLayout(top)

        splitter = qw.QSplitter(qc.Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        left = qw.QWidget()
        llay = qw.QVBoxLayout(left)
        llay.addWidget(qw.QLabel("Parameters"))

        self.table = qw.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Default"])
        self.table.horizontalHeader().setSectionResizeMode(0, qw.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, qw.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, qw.QHeaderView.ResizeMode.Stretch)


        self.table.setEditTriggers(
            qw.QAbstractItemView.EditTrigger.DoubleClicked
            | qw.QAbstractItemView.EditTrigger.SelectedClicked
            | qw.QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.itemChanged.connect(self._on_table_item_changed)
        self._table_refreshing = False
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(qw.QHeaderView.ResizeMode.Interactive)

        header.setStretchLastSection(True)
        # qc.QTimer.singleShot(0, self._set_equal_column_widths)

        self.table.setSelectionBehavior(qw.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(qw.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        llay.addWidget(self.table, 1)

        self.data_dict = {"Int": "int", "Float": "float", "String": "str", "Boolean": "bool", "Array/Matrix": "ndarray"}
        self.data_dict_reverse = {"int": "Int", "float": "Float", "str": "String", "bool": "Boolean", "ndarray": "Array/Matrix"}

        btns = qw.QHBoxLayout()
        self.btn_add = qw.QPushButton("+ Parameter")
        self.btn_add.clicked.connect(self._add_parameter)

        self.btn_remove = qw.QPushButton("Delete")
        self.btn_remove.clicked.connect(self._remove_selected)

        # Row-only reordering via buttons (QTableWidget internal drag/drop is cell-based and too permissive)
        self.btn_move_up = qw.QPushButton("↑")
        self.btn_move_up.setFixedWidth(24)
        self.btn_move_up.setToolTip("Move selected parameter up")
        self.btn_move_up.clicked.connect(self._move_selected_row_up)

        self.btn_move_down = qw.QPushButton("↓")
        self.btn_move_down.setFixedWidth(24)
        self.btn_move_down.setToolTip("Move selected parameter down")
        self.btn_move_down.clicked.connect(self._move_selected_row_down)

        self.btn_move_defaults = qw.QPushButton("Sift defaults down")
        self.btn_move_defaults.setToolTip("Ensure all parameters with defaults appear after non-default parameters.")
        self.btn_move_defaults.clicked.connect(self._move_defaults_to_bottom)

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_remove)
        # btns.addStretch(1)
        btns.addWidget(self.btn_move_up)
        btns.addWidget(self.btn_move_down)
        btns.addWidget(self.btn_move_defaults)
        llay.addLayout(btns)

        # Warning label when default arguments are out of place
        self.lbl_default_order_warning = qw.QLabel("")
        self.lbl_default_order_warning.setWordWrap(True)
        self.lbl_default_order_warning.setVisible(False)
        self.lbl_default_order_warning.setStyleSheet("color: #b00020;")  # subtle red
        llay.addWidget(self.lbl_default_order_warning)
        splitter.addWidget(left)

        # --- right: editor ---
        right = qw.QWidget()
        rlay = qw.QVBoxLayout(right)

        self.editor_stack = qw.QStackedWidget()
        rlay.addWidget(self.editor_stack, 1)

        self.page_empty = qw.QLabel("Select a parameter to edit its settings.")
        self.page_empty.setWordWrap(True)
        self.page_empty.setAlignment(qc.Qt.AlignmentFlag.AlignTop | qc.Qt.AlignmentFlag.AlignLeft)
        self.editor_stack.addWidget(self.page_empty)

        self.page_param = self._build_param_editor()
        self.editor_stack.addWidget(self.page_param)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)

        self._refresh_models()

        if model is not None:
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            try:
                self.model_combo.setCurrentIndex(models.index(model))
            except ValueError:
                pass
            self._current_model = model

        self._emit_available_params()

    # -------------------------
    # UI build
    # -------------------------

    def _build_param_editor(self) -> qw.QWidget:
        w = qw.QWidget()
        outer = qw.QVBoxLayout(w)

        box = qw.QGroupBox("Parameter")
        form = qw.QFormLayout(box)
        form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.edit_name = qw.QLineEdit()
        self.edit_name.textChanged.connect(self._name_changed)

        # self.edit_name.textChanged.connect(self._name_changed)

        self.combo_type = qw.QComboBox()
        self.combo_type.addItems(["Int", "Float", "String", "Boolean", "Array/Matrix"])
        self.combo_type.currentTextChanged.connect(self._type_changed)

        self.edit_default_val = qw.QLineEdit()
        self.edit_default_val.textChanged.connect(self._default_val_changed)

        form.addRow("Name:", self.edit_name)
        form.addRow("Type:", self.combo_type)
        form.addRow("Default Value (Optional):", self.edit_default_val)

        outer.addWidget(box)

        outer.addStretch(0)
        return w

    def _emit_available_params(self) -> None:
        if not self._current_model:
            return
        names = [s.name for s in self._working_data.get(self._current_model, [])]
        self.availableParamsChanged.emit(self._current_model, names)

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
        self._refresh_table()
        self.editor_stack.setCurrentIndex(0)
        self._emit_available_params()

    def _on_table_item_changed(self, item: qw.QTableWidgetItem) -> None:

        if self._table_refreshing:
            return
        if not self._current_model:
            return

        row = item.row()
        col = item.column()

        specs = self._working_data.get(self._current_model, [])
        if not (0 <= row < len(specs)):
            return
        spec = specs[row]

        txt = item.text().strip()

        # Column 0: Name
        if col == 0:
            if not self._valid_identifier(txt):
                self.window.status.show("Invalid name.", 4000)
                self._refresh_table()
                return
            if any(s is not spec and s.name == txt for s in specs):
                self.window.status.show("Duplicate name.", 4000)
                self._refresh_table()
                return
            spec.name = txt

        # Column 1: Type (expect internal form like int/float/str/bool/ndarray)
        elif col == 1:
            # Allow either the pretty label or internal type
            if txt in self.data_dict:
                spec.data_type = self.data_dict[txt]
            elif txt in self.data_dict_reverse:
                spec.data_type = txt
            else:
                self.window.status.show("Type must be one of int/float/str/bool/ndarray.", 5000)
                self._refresh_table()
                return

        # Column 2: Default (raw text; empty -> None)
        elif col == 2:
            spec.value = None if txt == "" else txt

        # keep current-spec pointer stable and reflect in editor fields
        self._current_spec = spec
        self._load_spec_into_editor(spec)
        self._emit_available_params()
        self._update_default_order_warning()
        self._update_reorder_buttons()

    def _set_equal_column_widths(self) -> None:
        header = self.table.horizontalHeader()
        w = self.table.viewport().width()
        if w <= 0:
            return
        each = w // 3
        for col in range(3):
            header.resizeSection(col, each)

    def _reload_current_model(self) -> None:
        if not self._current_model:
            return
        self._original_data.pop(self._current_model, None)
        self._working_data.pop(self._current_model, None)
        self._ensure_loaded(self._current_model)
        self._refresh_table()
        self.editor_stack.setCurrentIndex(0)

    def _ensure_loaded(self, model: str) -> None:
        if model in self._working_data:
            return
        specs = self._load_specs_from_parameters_py(model)
        self._working_data[model] = specs
        self._original_data[model] = copy.deepcopy(specs)

    def _infer_data_type(self, dc_type: Any, default_val: Any | None, has_default: bool) -> str:

        # prefer type hint if possible
        if dc_type is float:
            return "float"
        if dc_type is int:
            return "int"
        if dc_type is bool:
            return "bool"
        if dc_type is str:
            return "str"
        if dc_type is ndarray:
            return "ndarray"

        # fall back using the the default value if present
        if has_default:
            if isinstance(default_val, bool):
                return "bool"
            if isinstance(default_val, int) and not isinstance(default_val, bool):
                return "int"
            if isinstance(default_val, float):
                return "float"
            if isinstance(default_val, str):
                return "str"
            if isinstance(default_val, ndarray):
                return "ndarray"

        # last resort
        return "float"

    def _load_specs_from_parameters_py(self, model: str) -> List[ParamSpec]:
        print(f"Loading specs from parameters.py")
        path = self.env.models_dir / model / "simulation" / "parameters.py"
        try:
            Parameters = load_parameters_class_from_file(path)
        except FileNotFoundError:
            return []
        except Exception as e:
            self.window.status.show(f"Error importing parameters.py: {e}", 8000)
            return []

        specs: List[ParamSpec] = []
        for f in fields(Parameters):
            has_default, default_val = get_default_value (f)
            data_type = self._infer_data_type(f.type, default_val, has_default)

            value = default_val if has_default else None

            specs.append(ParamSpec(
                    name= f.name,
                    data_type= data_type,
                    value= value,
                    annotation= str(f.type)
                ))

        return specs

    def _refresh_table(self) -> None:
        self._table_refreshing = True
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        if not self._current_model:
            self.table.blockSignals(False)
            return

        specs = self._working_data.get(self._current_model, [])
        for spec in specs:
            r = self.table.rowCount()
            self.table.insertRow(r)

            self.table.setItem(r, 0, qw.QTableWidgetItem(spec.name))
            self.table.setItem(r, 1, qw.QTableWidgetItem(spec.data_type))
            default_txt = "" if spec.value is None else (spec.value if isinstance(spec.value, str) else repr(spec.value))
            self.table.setItem(r, 2, qw.QTableWidgetItem(default_txt))

        if self._current_spec is not None and self._current_model:
            specs = self._working_data.get(self._current_model, [])
            try:
                idx = specs.index(self._current_spec)
            except ValueError:
                idx = -1
            if idx >= 0:
                self.table.selectRow(idx)

        self.table.blockSignals(False)
        self._table_refreshing = False
        self._emit_available_params()
        self._update_default_order_warning()

    def _selected_row(self) -> Optional[int]:
        rows = {i.row() for i in self.table.selectedItems()}
        return next(iter(rows)) if rows else None

    def _select_spec_from_table(self) -> Optional[ParamSpec]:
        if not self._current_model:
            return None
        row = self._selected_row()
        if row is None:
            return None
        specs = self._working_data[self._current_model]
        if 0 <= row < len(specs):
            return specs[row]
        return None

    def _selected_spec(self) -> Optional[ParamSpec]:
        if self._current_spec is not None:
            return self._current_spec
        return self._select_spec_from_table()

    def _on_selection_changed(self) -> None:
        spec = self._select_spec_from_table()
        self._current_spec = spec
        if spec is None:
            self.editor_stack.setCurrentIndex(0)
            return
        self._update_reorder_buttons()
        self._load_spec_into_editor(spec)
        self.editor_stack.setCurrentIndex(1)
        self._update_reorder_buttons()

    def _load_spec_into_editor(self, spec: ParamSpec) -> None:
        self._block_editor(True)

        self.edit_name.setText(spec.name)
        combo_type_setting = self.data_dict_reverse[spec.data_type]
        self.combo_type.setCurrentText(combo_type_setting)
        if spec.value is None:
            text = ""
        elif spec.data_type == "ndarray":
            try:
                text = self._get_str_from_nparray(str(spec.value))
            except Exception as e:
                logger.log(logging.ERROR, f"Error parsing parameter {spec.value}: {e}", exc_info= e)
                self.window.status.show(f"Error parsing parameter {spec.value}", 4000)
                text = str(spec.value)
        else:
            text = str(spec.value)
        self.edit_default_val.setText(text)

        self._block_editor(False)

    def _get_str_from_nparray(self, bad_str):
        s = bad_str.strip()

        if not s:
            return "[]"

        if not (s.startswith("[") and s.endswith("]")):
            return bad_str

        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple)):
                return bad_str
        except (SyntaxError, ValueError):
            pass

        inner = s[1:-1].strip()

        if not inner:
            return "[]"

        if inner.startswith("["):
            row_strings = re.findall(r"\[([^\[\]]*)\]", inner)

            if not row_strings:
                return bad_str

            rows = []
            for row in row_strings:
                row = row.strip()

                if not row:
                    rows.append("[]")
                    continue

                nums = row.split()
                rows.append("[" + ", ".join(nums) + "]")

            return "[" + ", ".join(rows) + "]"

        nums = inner.split()
        return "[" + ", ".join(nums) + "]"

    def _get_str_from_nparray2(self, bad_str):
        no_braks = bad_str[1:len(bad_str)-1].strip()
        is_matrix = (no_braks[0] == "[")

        if not is_matrix:
            inner_ls_str = "["
            if len(no_braks) < 2:
                return inner_ls_str + "]"
            raw_nums = no_braks.split()
            nums = [num.strip() for num in raw_nums]

            for j, num in enumerate(nums):
                inner_ls_str += num
                if j == len(nums)-1:
                    continue
                inner_ls_str += ", "

            inner_ls_str += "]"
            return inner_ls_str
        else:
            lists = no_braks.split("\n")
            outer_ls_str = "["
            for i, ls_str in enumerate(lists):
                inner_ls_str = "["
                ls_no_braks = ls_str[1:len(ls_str)-1]
                if len(ls_no_braks) < 2:
                    continue
                nums = ls_no_braks.split()

                for j, num in enumerate(nums):
                    inner_ls_str += num
                    if j == len(nums)-1:
                        continue
                    inner_ls_str += ", "

                inner_ls_str += "]"
                outer_ls_str += inner_ls_str
                if i == len(lists)-1:
                    continue
                outer_ls_str += ", "
            outer_ls_str += "]"

            return outer_ls_str

    def _set_table_text(self, row: int, col: int, text: str) -> None:
        item = self.table.item(row, col)
        if item is None:
            return

        self.table.blockSignals(True)
        item.setText(text)
        self.table.blockSignals(False)

    def _block_editor(self, block: bool) -> None:
        self.edit_name.blockSignals(block)
        self.combo_type.blockSignals(block)
        self.edit_default_val.blockSignals(block)

    def _name_changed(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return

        if not self._current_model:
            return

        new = self.edit_name.text().strip()

        if not self._valid_identifier(new):
            return

        if not self._valid_identifier(new):
            self.window.status.show(
                "Invalid name. Use a valid Python identifier that is not a keyword.",
                4000,
            )
            return

        specs = self._working_data[self._current_model]
        if any(s is not spec and s.name == new for s in specs):
            self.window.status.show("A parameter with that name already exists.", 4000)
            return

        if spec.name == new:
            return

        spec.name = new

        row = self._selected_row()
        if row is not None:
            self._set_table_text(row, 0, new)

        self._emit_available_params()

    def _type_changed(self, data_type: str) -> None:
        spec = self._selected_spec()
        if spec is None:
            return
        spec.data_type = self.data_dict[data_type]
        self._refresh_table()

    def _default_val_changed(self) -> None:
        spec = self._selected_spec()
        if spec is None:
            return

        raw_txt = self.edit_default_val.text().strip()
        if raw_txt == "":
            spec.value = None
            self._update_default_order_warning()
            return

        valid = True
        match spec.data_type:
            case "int":
                try:
                    int(raw_txt)
                    txt = raw_txt
                except ValueError:
                    valid = False
            case "float":
                try:
                    float(raw_txt)
                    txt = raw_txt
                except ValueError:
                    valid = False
            case "str":
                txt = raw_txt
            case "bool":
                try:
                    bool(raw_txt)
                    txt = raw_txt
                except ValueError:
                    valid = False
            case "ndarray":
                try:
                    txt = self._get_str_from_nparray(raw_txt)
                except Exception as e:
                    valid = False

        if valid:
            spec.value = txt
            self._update_default_order_warning()

        # row = self._selected_row()
        # if row is not None:
        #     default_txt = "" if spec.value is None else str(spec.value)
        #     item = self.table.item(row, 2)
        #     if item:
        #         item.setText(default_txt)
        # self._refresh_table()

    def _add_parameter(self) -> None:
        if not self._current_model:
            return

        specs = self._working_data[self._current_model]
        base = "new_param"
        name = base
        i = 1
        while any(s.name == name for s in specs):
            i += 1
            name = f"{base}{i}"

        specs.append(ParamSpec(name=name, data_type="float", value=None, annotation="float"))
        self._refresh_table()
        self.table.selectRow(len(specs) - 1)

    def _remove_selected(self) -> None:
        if not self._current_model:
            return
        row = self._selected_row()
        if row is None:
            return
        specs = self._working_data[self._current_model]
        if 0 <= row < len(specs):
            specs.pop(row)
        self._refresh_table()
        self.editor_stack.setCurrentIndex(0)

    def on_apply_clicked(self) -> None:
        if not self._current_model:
            return

        try:
            for model, _ in self._original_data.items():
                path = self.env.models_dir / model / "simulation" / "parameters.py"
                specs = self._working_data[model]
                code = self._render_parameters_py(specs)
                atomic_write(path, code)
        except Exception as e:
            self.window.status.show(f"Error writing changes: {e}", 8000)
            logger.log(logging.ERROR, "Error writing changes", exc_info= e)
        else:
            for model, _ in self._original_data.items():
                specs = self._working_data[model]
                self._original_data[model] = copy.deepcopy(specs)
        finally:
            self.paramSettingsChanged.emit()

    # def on_apply_clicked(self) -> None:
    #     if not self._current_model:
    #         return

    #     try:
    #         for model, model_data in self._original_data.items():
    #             path = rpath("models", model, "simulation", "parameters.py")
    #             bak = str(path) + ".bak"

    #             specs = self._working_data[model]
    #             code = self._render_parameters_py(specs)

    #             if os.path.exists(path):
    #                 with open(path, "r", encoding="utf-8") as f:
    #                     old = f.read()
    #                 with open(bak, "w", encoding="utf-8") as f:
    #                     f.write(old)

    #             with open(path, "w", encoding="utf-8") as f:
    #                 f.write(code)

    #     except Exception as e:
    #         self.window.status.show(f"Error writing parameters.py: {e}", 8000)
    #     finally:
    #         try:
    #             for model, model_data in self._original_data.items():
    #                 path = rpath("models", model, "simulation", "parameters.py.bak")
    #                 os.remove(path)
    #         except OSError as e:
    #             self.window.status.show("Error removing backup, you should check your directory.", 5000)
    #             logger.log(logging.WARNING, f"Error removing directory.", exc_info= e)

    #     self._original_data[model] = copy.deepcopy(specs)

    def _render_parameters_py(self, specs: List[ParamSpec]) -> str:
        """
        Generate a clean parameters.py file.
        """
        lines: List[str] = []
        lines.append("from dataclasses import dataclass, field")
        lines.append("from numpy import array, ndarray")
        lines.append("")
        lines.append("")
        lines.append("@dataclass")
        lines.append("class Params:")
        if not specs:
            lines.append("    pass")
            lines.append("")
            return "\n".join(lines)

        for spec in specs:
            name = spec.name
            data_type = spec.data_type

            ann, default = self._annotation_and_default(spec)
            if default is None:
                lines.append(f"    {name}: {ann}")
            else:
                lines.append(f"    {name}: {ann} = {default}")

        lines.append("")
        return "\n".join(lines)

    def _annotation_and_default(self, spec: ParamSpec) -> Tuple[str, Optional[str]]:
        ann = spec.data_type or "float"

        # ---- no default ----
        if spec.value is None:
            return ann, None

        # Normalize "raw text" vs "actual object"
        if isinstance(spec.value, str):
            raw = spec.value.strip()
            if raw == "":
                return ann, None
        else:
            raw = None  # means we have an actual python object default (from loader)

        # ---- ndarray defaults: always use field(default_factory=...) ----
        if ann == "ndarray":
            # Case 1: loaded object is already an ndarray (or list-like)
            if raw is None:
                arr = np.array(spec.value, dtype=float)
                return "ndarray", f"field(default_factory=lambda: array({arr.tolist()}))"

            # Case 2: user typed something
            # If they typed a list literal, wrap it.
            if raw.startswith("["):
                return "ndarray", f"field(default_factory=lambda: array({raw}))"

            # If they typed "array(...)" already, keep as-is but still make it default_factory
            # (prevents shared mutable default)
            if "array(" in raw or raw.startswith("np.array(") or raw.startswith("array("):
                inner = raw
                # If they used np.array, parameters.py only imports array; keep np.array if you also import numpy as np.
                # Better: normalize np.array -> array
                inner = inner.replace("np.array", "array")
                return "ndarray", f"field(default_factory=lambda: {inner})"

            # Otherwise assume they typed an expression returning an array-like
            return "ndarray", f"field(default_factory=lambda: array({raw}))"

        # ---- scalar defaults ----
        if ann == "str":
            if raw is None:
                return "str", repr(str(spec.value))
            # If they already quoted it, keep. Otherwise quote it.
            if (raw.startswith(("'", '"')) and raw.endswith(("'", '"')) and len(raw) >= 2):
                return "str", raw
            return "str", repr(raw)

        if ann == "bool":
            if raw is None:
                return "bool", "True" if bool(spec.value) else "False"
            t = raw.lower()
            if t in {"true", "t", "1", "yes", "y", "on"}:
                return "bool", "True"
            if t in {"false", "f", "0", "no", "n", "off"}:
                return "bool", "False"
            # If user typed something like "some_expr", trust it
            return "bool", raw

        if ann == "int":
            if raw is None:
                return "int", str(int(spec.value))
            return "int", raw

        # float (default)
        if raw is None:
            return "float", repr(float(spec.value))
        return "float", raw

    def _valid_identifier(self, s: str) -> bool:
        if not s:
            return False
        if keyword.iskeyword(s):
            return False
        return s.isidentifier()

    def _coerce_scalar_value(self, txt: str, st: str) -> Any:
        if st == "bool":
            # accept common strings
            t = txt.lower()
            if t in {"true", "1", "yes", "y", "on"}:
                return True
            if t in {"false", "0", "no", "n", "off"}:
                return False
            return False
        if st == "int":
            try:
                return int(float(txt))
            except Exception:
                return 0
        if st == "float":
            try:
                return float(txt)
            except Exception:
                return 0.0
        # str
        return txt

    # -------------------------
    # Row ordering / defaults
    # -------------------------

    def _spec_has_default(self, spec: ParamSpec) -> bool:
        """True if the parameter currently has a default value."""
        if spec.value is None:
            return False
        if isinstance(spec.value, str) and spec.value.strip() == "":
            return False
        return True

    def _defaults_out_of_order(self) -> bool:
        """
        Returns True if any non-default parameter appears after a default parameter.
        (Python requires non-default args before default args in a function signature.)
        """
        if not self._current_model:
            return False
        specs = self._working_data.get(self._current_model, [])
        seen_default = False
        for s in specs:
            if self._spec_has_default(s):
                seen_default = True
            elif seen_default:
                return True
        return False

    def _update_default_order_warning(self) -> None:
        if not hasattr(self, "lbl_default_order_warning"):
            return
        bad = self._defaults_out_of_order()
        self.lbl_default_order_warning.setVisible(bad)
        if bad:
            self.lbl_default_order_warning.setText(
                "Warning: A non-default parameter appears after a default parameter. "
                "Python requires all non-default parameters to come first."
            )
        else:
            self.lbl_default_order_warning.setText("")

    def _move_defaults_to_bottom(self) -> None:
        """Stable-partition parameters so non-default params come first."""
        if not self._current_model:
            return
        specs = self._working_data.get(self._current_model, [])
        if not specs:
            return

        non_defaults: List[ParamSpec] = []
        defaults: List[ParamSpec] = []
        for s in specs:
            (defaults if self._spec_has_default(s) else non_defaults).append(s)

        new_specs = non_defaults + defaults
        if new_specs == specs:
            self._update_default_order_warning()
            return

        # Keep current selection if possible
        keep = self._current_spec
        self._working_data[self._current_model] = new_specs
        self._refresh_table()

        if keep is not None and keep in new_specs:
            self._current_spec = keep
            self.table.selectRow(new_specs.index(keep))

        self._update_default_order_warning()

    def _update_reorder_buttons(self) -> None:
        row = self._selected_row()
        if row is None or not self._current_model:
            self.btn_move_up.setEnabled(False)
            self.btn_move_down.setEnabled(False)
            return

        specs = self._working_data.get(self._current_model, [])
        self.btn_move_up.setEnabled(row > 0)
        self.btn_move_down.setEnabled(0 <= row < len(specs) - 1)

    def _move_selected_row_up(self) -> None:
        self._move_selected_row(-1)

    def _move_selected_row_down(self) -> None:
        self._move_selected_row(1)

    def _move_selected_row(self, delta: int) -> None:
        if not self._current_model:
            return
        row = self._selected_row()
        if row is None:
            return

        specs = self._working_data.get(self._current_model, [])
        if not specs:
            return

        new_row = row + delta
        if new_row < 0 or new_row >= len(specs):
            return

        specs[row], specs[new_row] = specs[new_row], specs[row]
        self._current_spec = specs[new_row]

        self._refresh_table()
        # _refresh_table will try to reselect current_spec, but ensure the row is selected
        self.table.selectRow(new_row)

        self._update_reorder_buttons()
        self._update_default_order_warning()


    def set_model(self, model_name: str):
        idx = self.model_combo.findText(model_name)
        if idx >= 0 and idx != self.model_combo.currentIndex():
            self.model_combo.setCurrentIndex(idx)
