from __future__ import annotations
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pprint import pprint
import os
import copy
import yaml
import re
from numpy import ndarray
from .HelpFormLayout import HelpFormLayout

from overseer.tools.loader import load_presets, params_from_mapping, load_parameters_class_from_file, try_instantiate_with_defaults
from overseer.tools.creation_tools import flow_seqify, FlowSeq, atomic_write
import logging

logger = logging.getLogger(__name__)

from PyQt6 import QtWidgets as qw, QtCore as qc, QtGui as qg

_DIVIDER_RE = re.compile(r"^divider(\d+)$")
_ROW_RE     = re.compile(r"^row(\d+)$")

def is_divider(key: str) -> bool:
    return bool(_DIVIDER_RE.match(key))

def is_row(key: str) -> bool:
    return bool(_ROW_RE.match(key))

def divider_index(key: str) -> int | None:
    m = _DIVIDER_RE.match(key)
    return int(m.group(1)) if m else None

# yaml.add_representer(FlowSeq, flowseq_representer, Dumper=yaml.SafeDumper)
logger = logging.getLogger(__name__)

def list_subdirs(path: str | os.PathLike) -> List[str]:
    p = Path(path)
    if not p.exists():
        return []
    return sorted([x.name for x in p.iterdir() if x.is_dir()])

class InitControlsDialog(qw.QDialog):
    """
    Minimal "one-click initializer" dialog:
      - shows params detected from the model preset/Parameters dataclass
      - allows include/exclude
      - generates basic defaults
    """

    def __init__(self, env, model_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Initialize Control Panel – {model_name}")
        self.resize(720, 520)

        self._model_name = model_name
        self._params_instance = None  # populated in _load_params()
        self._Parameters = None
        self._param_fields = {}
        self._missing_required = []
        self.env = env

        root = qw.QVBoxLayout(self)

        info = qw.QLabel(
            "Select which parameters to include. The initializer will generate a basic\n"
            "control panel layout (3 controls per row) you can refine afterwards."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = qw.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Include", "Name", "Type", "Shape"])
        self.table.horizontalHeader().setSectionResizeMode(0, qw.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, qw.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, qw.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, qw.QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        # Defaults
        defaults_box = qw.QGroupBox("Defaults")
        form = HelpFormLayout(defaults_box)
        self.edit_divider_title = qw.QLineEdit("Parameters")
        self.edit_label_template = qw.QLineEdit("{name}=")
        self.numeric_min = qw.QLineEdit()
        self.numeric_min.setText("0.0")
        self.numeric_max = qw.QLineEdit()
        self.numeric_max.setText("1.0")
        # self.spin_numeric_min = qw.QDoubleSpinBox()
        # self.spin_numeric_min.setRange(-1e12, 1e12)
        # self.spin_numeric_min.setDecimals(6)
        # self.spin_numeric_min.setValue(0.0)
        # self.spin_numeric_max = qw.QDoubleSpinBox()
        # self.spin_numeric_max.setRange(-1e12, 1e12)
        # self.spin_numeric_max.setDecimals(6)
        # self.spin_numeric_max.setValue(1.0)

        label_template_help = "A string of text to accompany every control widget. Insert the placeholder {name} where you want the parameter to be substituted. For example, the default text will have your parameter name, followed by an equal sign, followed by the entry box for an entry widget. Alternatively, you could surround both sides of this with dollar signs to have the name displayed in LaTeX math mode font."

        form.addRow("Divider title:", self.edit_divider_title, help_text= "A title which appears at the top of your control panel. Mostly just there to look nice. You can place more dividers to group controls together later in the actual editor.")
        form.addRow("Label template:", self.edit_label_template, help_text= label_template_help)
        form.addRow("Numeric range min:", self.numeric_min, help_text= "For scalar ints and floats, a slider will be created along with a text box for entering the number. These two numbers specify the upper and lower bound for every slider. (You can change individual slider settings after finishing this initialization.) Non-numeric text will be ignored. If the app detects that your parameter is an int, but the number you enter is a float, it will be truncated automatically.")
        form.addRow("Numeric range max:", self.numeric_max)
        root.addWidget(defaults_box)

        btns = qw.QDialogButtonBox(
            qw.QDialogButtonBox.StandardButton.Ok | qw.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._load_params()

    def _load_params(self) -> None:
        try:
            Parameters = load_parameters_class_from_file(
                self.env.models_dir / self._model_name / "simulation" / "parameters.py"
            )
        except Exception as e:
            qw.QMessageBox.warning(self, "Parameters load error", str(e))
            return

        self._Parameters = Parameters
        self._param_fields = {f.name: f for f in fields(Parameters)}
        instance, missing = try_instantiate_with_defaults(Parameters)
        self._params_instance = instance
        self._missing_required = missing  # store if you want to display it

        self.table.setRowCount(0)

        for f in fields(Parameters):
            name = f.name
            typ = f.type
            shape = ""

            if instance is not None:
                try:
                    val = getattr(instance, name)
                    if isinstance(val, ndarray):
                        shape = str(val.shape)
                    elif isinstance(val, (int, float, bool, str)):
                        shape = ""
                except Exception:
                    pass

            row = self.table.rowCount()
            self.table.insertRow(row)

            chk = qw.QTableWidgetItem()
            chk.setFlags(chk.flags() | qc.Qt.ItemFlag.ItemIsUserCheckable)
            chk.setCheckState(qc.Qt.CheckState.Checked)
            self.table.setItem(row, 0, chk)

            self.table.setItem(row, 1, qw.QTableWidgetItem(name))
            self.table.setItem(row, 2, qw.QTableWidgetItem(getattr(typ, "__name__", str(typ))))
            self.table.setItem(row, 3, qw.QTableWidgetItem(shape))

        if missing:
            # Optional: show a non-blocking warning in the dialog
            # (still useful: you can generate scalar controls using default ranges even without instance)
            qw.QMessageBox.information(
                self,
                "Some parameters have no defaults",
                "Some dataclass fields have no default/default_factory, so Parameters() could not be instantiated.\n"
                "The initializer can still create controls, but array shapes / current values may be unknown for:\n\n"
                + ", ".join(missing),
            )

    def build_dividers(self):
        """
        Convert table selection + defaults into internal divider list.
        Wizard still defaults to 3 controls per row.
        Output schema: [{"title": str, "rows": [{"controls": [spec, ...]}, ...]}]
        """
        import numpy as np  # ensure np.ndarray is available

        div_title = self.edit_divider_title.text().strip() or "Parameters"
        label_tmpl = self.edit_label_template.text() or ""
        rmin_text, rmax_text = self.numeric_min.text(), self.numeric_max.text()
        try:
            rmin = float(rmin_text)
            rmax = float(rmax_text)
        except ValueError:
            rmin = 0.0
            rmax = 1.0

        rows = []
        current = {"controls": []}

        def flush_row():
            nonlocal current
            if current["controls"]:
                rows.append(current)
            current = {"controls": []}

        # If we can't inspect params, still return a valid divider in the new shape
        if self._Parameters is None:
            return [{"title": div_title, "rows": [{"controls": []}]}]

        for row in range(self.table.rowCount()):
            include_item = self.table.item(row, 0)
            if include_item is None or include_item.checkState() != qc.Qt.CheckState.Checked:
                continue

            name_item = self.table.item(row, 1)
            if name_item is None:
                continue

            pname = name_item.text().strip()
            if not pname:
                continue

            val = None
            has_val = False
            if self._params_instance is not None:
                try:
                    val = getattr(self._params_instance, pname)
                    has_val = True
                except Exception:
                    has_val = False

            f = self._param_fields.get(pname)
            ann = None if f is None else f.type

            spec = {"param_name": pname, "tooltip": ""}

            if has_val:
                # since bools are also ints, this must go at top!
                if isinstance(val, bool):
                    spec["control_type"] = "checkbox"
                    spec["label"] = pname

                elif isinstance(val, (int, float)):
                    spec["control_type"] = "entry_block"
                    spec["type"] = "scalar"

                    if ann is float:
                        spec["scalar_type"] = "float"
                    elif ann is int:
                        spec["scalar_type"] = "int"
                    else:
                        spec["scalar_type"] = "int" if isinstance(val, int) else "float"

                    is_int = (spec["scalar_type"] == "int")
                    spec["range"] = flow_seqify([int(rmin) if is_int else rmin,
                                             int(rmax) if is_int else rmax])

                    # label template: support {name}
                    if label_tmpl in ["", "name"]:
                        spec["label"] = pname
                    elif "{name}" in label_tmpl:
                        spec["label"] = label_tmpl.replace("{name}", pname)

                elif isinstance(val, np.ndarray):
                    spec["control_type"] = "entry_block"
                    shape = val.shape
                    if len(shape) > 1:
                        spec["type"] = "matrix"
                        spec["dim"] = flow_seqify(list(shape))
                    else:
                        spec["type"] = "vector"
                        spec["dim"] = int(shape[0])

                    if label_tmpl in ["", "name"]:
                        spec["label"] = pname
                    elif "{name}" in label_tmpl:
                        spec["label"] = label_tmpl.replace("{name}", pname)

                elif isinstance(val, str):
                    spec["control_type"] = "dropdown"
                    spec["label"] = pname
                    spec["names"] = flow_seqify([val])
                    spec["values"] = flow_seqify([val])

            else:
                if ann is bool:
                    spec["control_type"] = "checkbox"
                    spec["label"] = pname
                    # spec["names"] = FlowSeq(["True", "False"])
                    # spec["values"] = FlowSeq([True, False])

                elif ann is str:
                    spec["control_type"] = "dropdown"
                    spec["label"] = pname
                    spec["names"] = flow_seqify(["(set me)"])
                    spec["values"] = flow_seqify([""])

                elif ann is np.ndarray or (ann is not None and "ndarray" in str(ann)):
                    spec["control_type"] = "entry_block"
                    spec["type"] = "vector"
                    spec["dim"] = 1
                    spec["label"] = f"${pname}=$"

                else:
                    spec["control_type"] = "entry_block"
                    spec["type"] = "scalar"
                    spec["scalar_type"] = "float"
                    spec["range"] = flow_seqify([rmin, rmax])
                    spec["label"] = f"${pname}=$"

            current["controls"].append(spec)
            if len(current["controls"]) >= 3:
                flush_row()

        flush_row()
        div: DividerModel = {"title": div_title, "rows": rows if rows else [{"controls": []}]}
        return [div]


# =========================
# ControlSettingsTab
# =========================

class ControlSettingsTab(qw.QWidget):
    """
    Starter control panel editor:
      - Model selector
      - Load existing control_panel_data.yml into a tree:
          Divider -> Rows (derived, 3 per row) -> Controls
      - One-click initializer builds a basic divider+controls from Parameters
      - Right-side editor updates selected divider/control spec
      - Apply writes control_panel_data.yml (with .bak safety)
    """
    ROLE = qc.Qt.ItemDataRole.UserRole

    def __init__(self, env, model= None, parent=None):
        super().__init__(parent)
        self.window = self.window()

        self.env = env

        self._current_model: Optional[str] = None
        self._original_data: Dict[str, List[DividerModel]] = {}
        self._working_data: Dict[str, List[DividerModel]] = {}
        self._available_params: Dict[str, List[str]] = {}
        self._in_refresh_tree = False
        self._tree_sync_pending = False

        root = qw.QVBoxLayout(self)

        # --- top bar ---
        top = qw.QHBoxLayout()
        top.addWidget(qw.QLabel("Model:"))
        self.model_combo = qw.QComboBox()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        top.addWidget(self.model_combo, 1)

        self.btn_reload = qw.QPushButton("Reload")
        self.btn_reload.clicked.connect(self._reload_current_model)
        top.addWidget(self.btn_reload)

        self.btn_init = qw.QPushButton("Initialize from parameters…")
        self.btn_init.clicked.connect(self._initialize_clicked)
        top.addWidget(self.btn_init)

        root.addLayout(top)

        splitter = qw.QSplitter(qc.Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # --- left: tree ---
        left = qw.QWidget()
        left_l = qw.QVBoxLayout(left)
        left_l.addWidget(qw.QLabel("Control panel layout"))

        self.tree = qw.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(qw.QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setDragDropMode(qw.QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(qc.Qt.DropAction.MoveAction)
        self.tree.setDropIndicatorShown(True)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        m = self.tree.model()
        m.rowsMoved.connect(lambda *args: self._schedule_tree_sync())
        m.rowsInserted.connect(lambda *args: self._schedule_tree_sync())
        m.rowsRemoved.connect(lambda *args: self._schedule_tree_sync())
        m.layoutChanged.connect(self._schedule_tree_sync)
        self.tree.model().rowsMoved.connect(self._on_tree_rows_moved)
        left_l.addWidget(self.tree, 1)

        # quick add/remove
        btn_row = qw.QHBoxLayout()
        self.btn_add_div = qw.QPushButton("+ Divider")
        self.btn_add_div.clicked.connect(self._add_divider)
        btn_row.addWidget(self.btn_add_div)

        self.btn_add_control = qw.QPushButton("+ Control")
        self.btn_add_control.clicked.connect(self._add_control)
        btn_row.addWidget(self.btn_add_control)

        self.btn_add_row = qw.QPushButton("+ Row")
        self.btn_add_row.clicked.connect(self._add_row)
        btn_row.addWidget(self.btn_add_row)

        self.btn_delete = qw.QPushButton("Delete")
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        left_l.addLayout(btn_row)

        splitter.addWidget(left)

        # --- right: editor stack ---
        right = qw.QWidget()
        right_l = qw.QVBoxLayout(right)

        self.editor_stack = qw.QStackedWidget()
        right_l.addWidget(self.editor_stack, 1)

        self.page_empty = qw.QLabel("Select a divider or control on the left to edit its settings.")
        self.page_empty.setWordWrap(True)
        self.page_empty.setAlignment(qc.Qt.AlignmentFlag.AlignTop | qc.Qt.AlignmentFlag.AlignLeft)
        self.editor_stack.addWidget(self.page_empty)

        self.page_divider = self._build_divider_editor()
        self.editor_stack.addWidget(self.page_divider)

        self.page_control = self._build_control_editor()
        self.editor_stack.addWidget(self.page_control)

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
            self._refresh_models()
            self._on_model_changed(model)

    def _ensure_available_params(self, model: str) -> None:
        if model in self._available_params and self._available_params[model]:
            return

        try:
            Parameters = load_parameters_class_from_file(
                self.env.models_dir / model / "simulation" / "parameters.py"
            )
            self._available_params[model] = [f.name for f in fields(Parameters)]
        except Exception:
            self._available_params[model] = []

    @qc.pyqtSlot(str, list)
    def set_available_params(self, model: str, names: list) -> None:
        self._available_params[model] = list(names)

        # If we’re currently viewing that model and a control is selected,
        # refresh the combobox contents to reflect latest params.
        if model == self._current_model:
            ref = self._current_control_ref()
            if ref:
                di, ri, ci = ref
                spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
                self._populate_param_combo(spec.get("param_name", ""))

    # -------------------------
    # UI builders
    # -------------------------

    def _build_divider_editor(self) -> qw.QWidget:
        w = qw.QWidget()
        form = qw.QFormLayout(w)
        form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.div_title = qw.QLineEdit()
        self.div_title.textChanged.connect(self._divider_title_changed)

        form.addRow("Divider title:", self.div_title)
        form.addRow(qw.QLabel("Rows are derived automatically (3 controls per row)."))

        return w

    def _add_row(self) -> None:
        if not self._current_model:
            return
        divs = self._working_data[self._current_model]
        if not divs:
            divs.append({"title": "Parameters", "rows": [{"controls": []}]})

        payload = self._selected_payload()
        di = payload[1] if payload and payload[0] in {"divider", "row", "control"} else 0

        div = divs[di]
        div.setdefault("rows", [])
        div["rows"].append({"controls": []})
        self._refresh_tree()

    def _schedule_tree_sync(self) -> None:
        # Avoid reacting to the clear/rebuild done by _refresh_tree itself
        if self._in_refresh_tree or not self._current_model:
            return
        if self._tree_sync_pending:
            return

        self._tree_sync_pending = True

        def _do():
            self._tree_sync_pending = False
            if not self._current_model or self._in_refresh_tree:
                return
            self._rebuild_model_from_tree()
            self._refresh_tree()

        qc.QTimer.singleShot(0, _do)

    def _build_control_editor(self) -> qw.QWidget:
        w = qw.QWidget()
        outer = qw.QVBoxLayout(w)

        header = qw.QGroupBox("Control")
        hform = qw.QFormLayout(header)
        hform.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.combo_param_name = qw.QComboBox()
        self.combo_param_name.setEditable(False)
        self.combo_param_name.currentTextChanged.connect(self._param_name_changed)
        self.param_choice = qw.QComboBox()
        self.combo_control_type = qw.QComboBox()
        self.combo_control_type.addItems(["entry_block", "dropdown", "checkbox"])
        self.combo_control_type.currentTextChanged.connect(self._control_type_changed)

        self.edit_label = qw.QLineEdit()
        self.edit_label.textChanged.connect(self._control_label_changed)

        self.edit_tooltip = qw.QPlainTextEdit()
        self.edit_tooltip.textChanged.connect(self._control_tooltip_changed)

        hform.addRow("Param:", self.combo_param_name)
        hform.addRow("Control type:", self.combo_control_type)
        hform.addRow("Label:", self.edit_label)
        hform.addRow("Tooltip:", self.edit_tooltip)
        outer.addWidget(header)

        # type-specific editor
        self.control_stack = qw.QStackedWidget()
        outer.addWidget(self.control_stack, 1)

        # entry_block page
        entry_page = qw.QWidget()
        eform = qw.QFormLayout(entry_page)
        eform.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)
        # Prevent QFormLayout from wrapping the field onto the next line when space is tight.
        # Wrapping is what makes the Dim spinboxes appear "under" the label.
        eform.setRowWrapPolicy(qw.QFormLayout.RowWrapPolicy.DontWrapRows)
        eform.setFieldGrowthPolicy(qw.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        # Keep a handle so we can hide/show entire form rows without leaving gaps
        self._entry_form = eform

        self.combo_entry_kind = qw.QComboBox()
        self.combo_entry_kind.addItems(["scalar", "vector", "matrix"])
        self.combo_entry_kind.currentTextChanged.connect(self._entry_kind_changed)

        self.combo_scalar_type = qw.QComboBox()
        self.combo_scalar_type.addItems(["int", "float"])
        self.combo_scalar_type.currentTextChanged.connect(self._scalar_type_changed)

        self.range_min = qw.QLineEdit()
        self.range_min.textChanged.connect(self._range_changed)

        self.range_max = qw.QLineEdit()
        self.range_max.textChanged.connect(self._range_changed)

        # Dimension editor: vector uses one spinbox, matrix uses two.
        self.dim_stack = qw.QStackedWidget()
        # Keep the dimension editor from greedily taking vertical space in the form layout.
        # (If it expands vertically, the spinboxes can end up looking "below" the label.)
        self.dim_stack.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Fixed)

        self.dependent_checks = {"vec": False, "mat_rows": False, "mat_cols": False}

        vec_w = qw.QWidget()
        vec_l = qw.QHBoxLayout(vec_w)
        vec_l.setContentsMargins(0, 0, 0, 0)
        vec_l.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        self.vec_dep = qw.QCheckBox("Dependent")
        self.vec_dim = qw.QLineEdit()
        # self.spin_vec_dim = qw.QSpinBox()
        # self.spin_vec_dim.setRange(1, 10**9)
        self.vec_dim.textChanged.connect(self._dim_changed)
        self.vec_dep.checkStateChanged.connect(self._dim_changed)
        vec_l.addWidget(self.vec_dim, 0)
        vec_l.addWidget(self.vec_dep, 0)
        self.dim_stack.addWidget(vec_w)

        mat_w = qw.QWidget()
        mat_w_edits = qw.QWidget()
        mat_w_boxes = qw.QWidget()
        mat_l_outer = qw.QVBoxLayout(mat_w)
        mat_l_boxes = qw.QHBoxLayout(mat_w_boxes)
        mat_l_dims = qw.QHBoxLayout(mat_w_edits)
        mat_l_dims.setContentsMargins(0, 0, 0, 0)
        mat_l_dims.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        self.mat_rows_dep = qw.QCheckBox("Dependent rows")
        self.mat_rows = qw.QLineEdit()
        self.mat_rows.textChanged.connect(self._dim_changed)
        self.mat_cols_dep = qw.QCheckBox("Dependent columns")
        self.mat_rows_dep.checkStateChanged.connect(self._dim_changed)
        self.mat_cols = qw.QLineEdit()
        self.mat_cols.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        self.mat_cols.textChanged.connect(self._dim_changed)
        self.mat_cols_dep.checkStateChanged.connect(self._dim_changed)
        mat_l_boxes.addWidget(self.mat_rows_dep, 0)
        mat_l_boxes.addWidget(self.mat_cols_dep, 0)
        mat_l_dims.addWidget(self.mat_rows, 0)
        mat_l_dims.addWidget(qw.QLabel("x"), 0)
        mat_l_dims.addWidget(self.mat_cols, 0)
        mat_l_outer.addWidget(mat_w_boxes)
        mat_l_outer.addWidget(mat_w_edits)
        self.dim_stack.addWidget(mat_w)

        # Ensure the stacked widget height matches a single row of controls.
        self.dim_stack.setMaximumHeight(max(vec_w.sizeHint().height(), mat_w.sizeHint().height()))

        eform.addRow("Entry type:", self.combo_entry_kind)
        eform.addRow("Scalar type:", self.combo_scalar_type)
        eform.addRow("Range min:", self.range_min)
        eform.addRow("Range max:", self.range_max)
        eform.addRow("Dim:", self.dim_stack)

        self.control_stack.addWidget(entry_page)

        # dropdown page
        drop_page = qw.QWidget()
        dlay = qw.QVBoxLayout(drop_page)
        self.dropdown_table = qw.QTableWidget(0, 2)
        self.dropdown_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.dropdown_table.horizontalHeader().setSectionResizeMode(0, qw.QHeaderView.ResizeMode.Stretch)
        self.dropdown_table.horizontalHeader().setSectionResizeMode(1, qw.QHeaderView.ResizeMode.Stretch)
        self.dropdown_table.itemChanged.connect(self._dropdown_item_changed)
        dlay.addWidget(self.dropdown_table, 1)

        dbtns = qw.QHBoxLayout()
        self.btn_add_option = qw.QPushButton("+ Option")
        self.btn_add_option.clicked.connect(self._add_dropdown_option)
        dbtns.addWidget(self.btn_add_option)
        self.btn_del_option = qw.QPushButton("Remove option")
        self.btn_del_option.clicked.connect(self._remove_dropdown_option)
        dbtns.addWidget(self.btn_del_option)
        dbtns.addStretch(1)
        dlay.addLayout(dbtns)

        self.control_stack.addWidget(drop_page)

        check_page = qw.QWidget()
        self.control_stack.addWidget(check_page)

        outer.addStretch(0)
        return w

    # -------------------------
    # Model loading / saving
    # -------------------------

    def _refresh_models(self) -> None:
        models = list_subdirs(self.env.models_dir)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.blockSignals(False)

        if models:
            self.model_combo.setCurrentIndex(0)
            self._on_model_changed(models[0])

    def _on_model_changed(self, model: str) -> None:
        if not model:
            return
        self._current_model = model
        self._ensure_loaded(model)
        self._ensure_available_params(model)
        self._refresh_tree()
        self.editor_stack.setCurrentIndex(0)

    def _reload_current_model(self) -> None:
        if not self._current_model:
            return
        # discard caches for this model and reload
        self._original_data.pop(self._current_model, None)
        self._working_data.pop(self._current_model, None)
        self._ensure_loaded(self._current_model)
        self._refresh_tree()

    def _ensure_loaded(self, model: str) -> None:
        if model in self._working_data:
            return

        divs = self._load_from_yaml(model)
        self._original_data[model] = copy.deepcopy(divs)
        self._working_data[model] = copy.deepcopy(divs)


    def _load_from_yaml(self, model: str):
        path = self.env.models_dir / model / "data" / "control_panel_data.yml"
        if not os.path.exists(path):
            return []

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        dividers = []
        current = None

        # raw is ordered in YAML; you rely on order already :contentReference[oaicite:3]{index=3}
        for key, val in raw.items():
            if is_divider(key):
                title = ""
                if isinstance(val, dict):
                    title = (val.get("title") or "").strip()
                current = {"title": title, "rows": []}
                dividers.append(current)

            elif is_row(key):
                if current is None:
                    current = {"title": "Parameters", "rows": []}
                    dividers.append(current)

                row = {"controls": []}

                if isinstance(val, dict):
                    for pname, spec in val.items():
                        if not isinstance(spec, dict):
                            continue
                        c = copy.deepcopy(spec)
                        c.setdefault("param_name", pname)
                        row["controls"].append(c)

                current["rows"].append(row)

            # else: ignore unknown keys

        return dividers

    def _populate_param_combo(self, current: str) -> None:
        model = self._current_model
        names = self._available_params.get(model, []) if model else []

        self.combo_param_name.blockSignals(True)
        self.combo_param_name.clear()

        if not names:
            # still allow showing current (even if missing) so user understands state
            if current:
                self.combo_param_name.addItem(f"(missing) {current}", userData=current)
            self.combo_param_name.blockSignals(False)
            return

        # If current param isn't in lis add a visible "missing" entry at top
        if current and current not in names:
            self.combo_param_name.addItem(f"(missing) {current}", userData=current)

        for n in names:
            self.combo_param_name.addItem(n, userData=n)

        # Select current if possible; otherwise first real param
        if current:
            idx = self.combo_param_name.findText(current)
            if idx >= 0:
                self.combo_param_name.setCurrentIndex(idx)
            else:
                self.combo_param_name.setCurrentIndex(0)
        else:
            self.combo_param_name.setCurrentIndex(0)

        self.combo_param_name.blockSignals(False)


    def _param_name_changed(self, txt: str) -> None:
        ref = self._current_control_ref()
        if not ref or not self._current_model:
            return

        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]

        # If it's a "(missing) X" display, keep the underlying userData if present
        idx = self.combo_param_name.currentIndex()
        val = self.combo_param_name.itemData(idx)
        if isinstance(val, str) and val:
            spec["param_name"] = val
        else:
            # fallback: direct text, stripping marker if user somehow got it
            spec["param_name"] = txt.replace("(missing) ", "").strip()

        self._refresh_tree()


    def _dump_to_yaml(self, dividers: List[DividerModel]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        dnum = 1
        rownum = 1

        for div in dividers:
            out[f"divider{dnum}"] = {"title": div.get("title", f"Divider {dnum}")}

            # New model: explicit rows
            rows = div.get("rows", None)

            # If anything still provides legacy "controls", treat it as a single row
            if rows is None:
                rows = [{"controls": div.get("controls", []) or []}]

            for row in (rows or []):
                row_dict: Dict[str, Any] = {}
                controls = row.get("controls", []) or []

                for spec in controls:
                    pname = spec.get("param_name", "")
                    if not pname:
                        continue

                    spec2 = copy.deepcopy(spec)

                    # keep FlowSeq for nice YAML where relevant
                    for k in ("range", "names", "values", "dim"):
                        if k in spec2 and isinstance(spec2[k], list):
                            spec2[k] = flow_seqify(spec2[k])

                    row_dict[pname] = spec2

                out[f"row{rownum}"] = row_dict
                rownum += 1

            dnum += 1

        return out

    def on_apply_clicked(self) -> None:
        if not self._current_model:
            return

        try:
            self._rebuild_model_from_tree()
            for model, _ in self._original_data.items():
                path = self.env.models_dir / model / "data" / "control_panel_data.yml"
                new_dict = self._dump_to_yaml(self._working_data[model])
                atomic_write(path, new_dict)
        except Exception as e:
            self.window.status.show(f"Error writing changes: {e}", 8000)
            logger.log(logger.ERROR, "Error writing changes", exc_info= e)
        else:
            self._original_data.clear()
            self._working_data.clear()
            self._ensure_loaded(self._current_model)
            self._refresh_tree()

    # -------------------------
    # Tree build / selection payload
    # -------------------------

    def _refresh_tree(self) -> None:
        self._in_refresh_tree = True
        # Remember selection before clearing
        prev_payload = self._selected_payload()

        self.tree.blockSignals(True)
        self.tree.clear()

        if not self._current_model:
            self.tree.blockSignals(False)
            return

        divs = self._working_data.get(self._current_model, [])
        for di, div in enumerate(divs):
            d_item = qw.QTreeWidgetItem([div.get("title", f"Divider {di+1}")])
            d_item.setData(0, self.ROLE, ("divider", di))
            d_item.setFlags(
                d_item.flags()
                | qc.Qt.ItemFlag.ItemIsDragEnabled
                | qc.Qt.ItemFlag.ItemIsDropEnabled
            )
            self.tree.addTopLevelItem(d_item)

            rows = div.get("rows", []) or []
            for ri, row in enumerate(rows):
                row_item = qw.QTreeWidgetItem([f"Row {ri+1}"])
                row_item.setData(0, self.ROLE, ("row", di, ri))
                row_item.setFlags(
                    row_item.flags()
                    | qc.Qt.ItemFlag.ItemIsDragEnabled
                    | qc.Qt.ItemFlag.ItemIsDropEnabled
                )
                d_item.addChild(row_item)

                controls = row.get("controls", []) or []
                for ci, spec in enumerate(controls):
                    label = spec.get("param_name", "control")
                    c_item = qw.QTreeWidgetItem([label])
                    c_item.setFlags(
                        c_item.flags()
                        | qc.Qt.ItemFlag.ItemIsDragEnabled
                        | qc.Qt.ItemFlag.ItemIsDropEnabled
                    )
                    c_item.setData(0, self.ROLE, ("control", di, ri, ci))
                    row_item.addChild(c_item)

                row_item.setExpanded(True)

            d_item.setExpanded(True)

        self.tree.blockSignals(False)

        # Restore selection if possible
        if prev_payload is not None:
            it = self._find_item_by_payload(prev_payload)
            if it is not None:
                self.tree.setCurrentItem(it)

        self._in_refresh_tree = False

    def _find_item_by_payload(self, payload: tuple) -> Optional[qw.QTreeWidgetItem]:
        def walk(root: qw.QTreeWidgetItem) -> Optional[qw.QTreeWidgetItem]:
            if root.data(0, self.ROLE) == payload:
                return root
            for i in range(root.childCount()):
                hit = walk(root.child(i))
                if hit is not None:
                    return hit
            return None

        for i in range(self.tree.topLevelItemCount()):
            hit = walk(self.tree.topLevelItem(i))
            if hit is not None:
                return hit
        return None

    def _selected_payload(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        return item.data(0, self.ROLE)


    def _on_tree_selection_changed(self) -> None:
        payload = self._selected_payload()
        if not payload or not self._current_model:
            self.editor_stack.setCurrentIndex(0)
            return

        kind = payload[0]

        if kind == "divider":
            _, di = payload
            div = self._working_data[self._current_model][di]
            self.div_title.blockSignals(True)
            self.div_title.setText(div.get("title", ""))
            self.div_title.blockSignals(False)
            self.editor_stack.setCurrentWidget(self.page_divider)
            return

        if kind == "control":
            _, di, ri, ci = payload
            try:
                spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
            except Exception:
                self.editor_stack.setCurrentIndex(0)
                return
            self._load_control_into_editor(spec)
            self.editor_stack.setCurrentWidget(self.page_control)
            return

        # rows don't have settings yet
        self.editor_stack.setCurrentIndex(0)

    # -------------------------
    # Drag/drop -> sync back to internal model
    # -------------------------

    def _on_tree_rows_moved(self, *args) -> None:
        """
        Starter approach: after a move in the tree, rebuild divider->controls order from
        the tree structure (dividers and control item ordering). Then refresh.
        """
        if not self._current_model:
            return
        self._rebuild_model_from_tree()
        self._refresh_tree()


    def _rebuild_model_from_tree(self) -> None:
        """
        Read current tree ordering into working model.
        Uses explicit divider -> rows -> controls structure.

        Tree payloads are expected to be:
          ("divider", di)
          ("row", di, ri)
          ("control", di, ri, ci)
        """
        model = self._current_model
        if not model:
            return

        old_divs = self._working_data.get(model, [])
        new_divs: List[DividerModel] = []

        for top_i in range(self.tree.topLevelItemCount()):
            d_item = self.tree.topLevelItem(top_i)
            dp = d_item.data(0, self.ROLE)
            if not dp or dp[0] != "divider":
                continue

            title = d_item.text(0)
            new_rows: List[Dict[str, Any]] = []

            for r_i in range(d_item.childCount()):
                row_item = d_item.child(r_i)
                rp = row_item.data(0, self.ROLE)
                if not rp or rp[0] != "row":
                    continue

                row_controls: List[ControlSpec] = []
                for c_i in range(row_item.childCount()):
                    c_item = row_item.child(c_i)
                    cp = c_item.data(0, self.ROLE)
                    if not cp or cp[0] != "control":
                        continue

                    _, old_di, old_ri, old_ci = cp
                    try:
                        row_controls.append(
                            copy.deepcopy(old_divs[old_di]["rows"][old_ri]["controls"][old_ci])
                        )
                    except Exception:
                        # if something went out of sync, skip gracefully
                        pass

                new_rows.append({"controls": row_controls})

            new_divs.append({"title": title, "rows": new_rows})

        self._working_data[model] = new_divs


    # -------------------------
    # Divider operations
    # -------------------------

    def _add_divider(self) -> None:
        if not self._current_model:
            return
        divs = self._working_data[self._current_model]
        divs.append({"title": f"Divider {len(divs)+1}", "rows": [{"controls": []}]})
        self._refresh_tree()

    def _divider_title_changed(self, txt: str) -> None:
        payload = self._selected_payload()
        if not payload or payload[0] != "divider" or not self._current_model:
            return
        _, di = payload
        self._working_data[self._current_model][di]["title"] = txt
        # update tree label live
        it = self.tree.currentItem()
        if it:
            it.setText(0, txt)

    # -------------------------
    # Control operations
    # -------------------------

    def _add_control(self) -> None:
        """
        Starter: adds a placeholder control to the currently selected divider (or first divider).
        """
        if not self._current_model:
            return

        divs = self._working_data[self._current_model]
        if not divs:
            divs.append({"title": "Parameters", "rows": [{"controls": []}]})

        payload = self._selected_payload()
        di = 0
        if payload and payload[0] in {"divider", "row", "control"}:
            di = payload[1]

        div = divs[di]
        div.setdefault("rows", [])
        if not div["rows"]:
            div["rows"].append({"controls": []})
        # Choose row index
        if payload and payload[0] == "row":
            ri = payload[2]
        elif payload and payload[0] == "control":
            ri = payload[2]
        else:
            # divider selected (or nothing): append to last row
            ri = len(div["rows"]) - 1

        # Clamp ri in case selection payload is stale
        ri = max(0, min(ri, len(div["rows"]) - 1))

        names = self._available_params.get(self._current_model, [])
        default_param = names[0] if names else ""

        new_spec: ControlSpec = {
            "param_name": default_param,
            "control_type": "entry_block",
            "type": "scalar",
            "scalar_type": "float",
            "range": flow_seqify([0.0, 1.0]),
            "label": "$new\\_param=$",
            "tooltip": "",
        }
        div = divs[di]
        div["rows"][ri].setdefault("controls", [])
        div["rows"][ri]["controls"].append(new_spec)
        self._refresh_tree()

    def _delete_selected(self) -> None:
        if not self._current_model:
            return
        payload = self._selected_payload()
        if not payload:
            return

        model = self._current_model
        divs = self._working_data[model]

        kind = payload[0]

        if kind == "divider":
            _, di = payload
            if 0 <= di < len(divs):
                divs.pop(di)
            self._refresh_tree()
            self.editor_stack.setCurrentIndex(0)
            return

        if kind == "row":
            _, di, ri = payload
            try:
                rows = divs[di].get("rows", [])
                if 0 <= ri < len(rows):
                    rows.pop(ri)
                    # Optional: ensure divider always has at least one row
                    if not rows:
                        rows.append({"controls": []})
            except Exception:
                pass
            self._refresh_tree()
            self.editor_stack.setCurrentIndex(0)
            return

        if kind == "control":
            _, di, ri, ci = payload
            try:
                controls = divs[di]["rows"][ri].get("controls", [])
                if 0 <= ci < len(controls):
                    controls.pop(ci)
            except Exception:
                pass
            self._refresh_tree()
            self.editor_stack.setCurrentIndex(0)
            return


    # -------------------------
    # Control editor sync
    # -------------------------

    def _current_control_ref(self) -> Optional[Tuple[int, int]]:
        payload = self._selected_payload()
        if not payload or payload[0] != "control" or not self._current_model:
            return None
        _, di, ri, ci = payload
        return (di, ri, ci)

    def _load_control_into_editor(self, spec: ControlSpec) -> None:
        # Block signals to prevent feedback loops
        # self.lbl_param_name.setText(str(spec.get("param_name", "")))
        self._populate_param_combo(str(spec.get("param_name", "")))

        self.combo_control_type.blockSignals(True)
        self.combo_control_type.setCurrentText(str(spec.get("control_type", "entry_block")))
        self.combo_control_type.blockSignals(False)

        self.edit_label.blockSignals(True)
        self.edit_label.setText(str(spec.get("label", "")))
        self.edit_label.blockSignals(False)

        self.edit_tooltip.blockSignals(True)
        self.edit_tooltip.setPlainText(str(spec.get("tooltip", "")))
        self.edit_tooltip.blockSignals(False)

        ctype = spec.get("control_type", "entry_block")
        if ctype == "dropdown":
            self.control_stack.setCurrentIndex(1)
            self._load_dropdown_table(spec)
        elif ctype == "checkbox":
            self.control_stack.setCurrentIndex(2)
        else:
            self.control_stack.setCurrentIndex(0)
            self._load_entry_fields(spec)

    def _load_entry_fields(self, spec: ControlSpec) -> None:
        kind = str(spec.get("type", "scalar"))

        # --- entry kind ---
        self.combo_entry_kind.blockSignals(True)
        if kind in {"scalar", "vector", "matrix"}:
            self.combo_entry_kind.setCurrentText(kind)
        else:
            kind = "scalar"
            self.combo_entry_kind.setCurrentText("scalar")
        self.combo_entry_kind.blockSignals(False)

        # --- scalar type ---
        st = str(spec.get("scalar_type", "float"))
        self.combo_scalar_type.blockSignals(True)
        self.combo_scalar_type.setCurrentText(st if st in {"int", "float"} else "float")
        self.combo_scalar_type.blockSignals(False)

        # --- range ---
        rng = spec.get("range", flow_seqify([0.0, 1.0]))
        try:
            r0, r1 = list(rng)
        except Exception:
            r0, r1 = 0.0, 1.0

        self.range_min.blockSignals(True)
        self.range_max.blockSignals(True)
        self.range_min.setText(str(r0))
        self.range_max.setText(str(r1))
        self.range_min.blockSignals(False)
        self.range_max.blockSignals(False)


        # --- dim ---
        if spec.get("dim_from"):
            dim = spec.get("dim_from", 1)
            self.vec_dep.setChecked(True)
        else:
            dim = spec.get("dim", 1)

        self.vec_dim.blockSignals(True)
        self.mat_rows.blockSignals(True)
        self.mat_cols.blockSignals(True)
        self.vec_dep.blockSignals(True)
        self.mat_rows_dep.blockSignals(True)
        self.mat_cols_dep.blockSignals(True)

        if kind == "vector":
            try:
                self.vec_dim.setText(str(dim))
            except Exception:
                self.vec_dim.setText("1")
            self.dim_stack.setCurrentIndex(0)

        elif kind == "matrix":
            rows, cols = 1, 1
            if isinstance(dim, (list, tuple, FlowSeq)) and len(dim) == 2:
                try:
                    rows, cols = dim[0], dim[1]
                    if isinstance(rows, str):
                        self.mat_rows_dep.setChecked(True)
                    if isinstance(cols, str):
                        self.mat_cols_dep.setChecked(True)
                except Exception:
                    rows, cols = 1, 1
            self.mat_rows.setText(str(rows))
            self.mat_cols.setText(str(cols))
            self.dim_stack.setCurrentIndex(1)
        else:
            # scalar
            self.dim_stack.setCurrentIndex(0)

        self.vec_dim.blockSignals(False)
        self.mat_rows.blockSignals(False)
        self.mat_cols.blockSignals(False)
        self.vec_dep.blockSignals(False)
        self.mat_rows_dep.blockSignals(False)
        self.mat_cols_dep.blockSignals(False)


        # --- show only relevant rows (no blank gaps) ---
        eform = getattr(self, "_entry_form", None)
        if eform is not None:
            show_scalar = (kind == "scalar")
            show_dim = (kind in {"vector", "matrix"})

            # Scalar: show scalar_type + range min/max
            eform.setRowVisible(self.combo_scalar_type, show_scalar)
            eform.setRowVisible(self.range_min, show_scalar)
            eform.setRowVisible(self.range_max, show_scalar)

            # Vector/Matrix: show dim editor only
            eform.setRowVisible(self.dim_stack, show_dim)
        else:
            # Fallback: at least hide widgets if the form reference is missing
            self.combo_scalar_type.setVisible(kind == "scalar")
            self.range_min.setVisible(kind == "scalar")
            self.range_max.setVisible(kind == "scalar")
            self.dim_stack.setVisible(kind in {"vector", "matrix"})


    def _load_dropdown_table(self, spec: ControlSpec) -> None:
        names = list(spec.get("names", []))
        values = list(spec.get("values", []))

        self.dropdown_table.blockSignals(True)
        self.dropdown_table.setRowCount(0)
        for i, (n, v) in enumerate(zip(names, values)):
            r = self.dropdown_table.rowCount()
            self.dropdown_table.insertRow(r)
            self.dropdown_table.setItem(r, 0, qw.QTableWidgetItem(str(n)))
            self.dropdown_table.setItem(r, 1, qw.QTableWidgetItem(str(v)))
        self.dropdown_table.blockSignals(False)

    # --- live updates from editor ---

    def _control_type_changed(self, ctype: str) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
        spec["control_type"] = ctype

        # normalize shape for the chosen type
        if ctype == "dropdown":
            spec.setdefault("names", flow_seqify(["True", "False"]))
            spec.setdefault("values", flow_seqify([True, False]))
            spec.pop("type", None)
            spec.pop("scalar_type", None)
            spec.pop("range", None)
            spec.pop("dim", None)
            self.control_stack.setCurrentIndex(1)
            self._load_dropdown_table(spec)
        elif ctype == "checkbox":
            spec.pop("type", None)
            spec.pop("scalar_type", None)
            spec.pop("range", None)
            spec.pop("dim", None)
            spec.pop("names", None)
            spec.pop("values", None)
            self.control_stack.setCurrentIndex(2)
        else:
            spec.setdefault("type", "scalar")
            spec.setdefault("scalar_type", "float")
            spec.setdefault("range", flow_seqify([0.0, 1.0]))
            spec.pop("names", None)
            spec.pop("values", None)
            self.control_stack.setCurrentIndex(0)
            self._load_entry_fields(spec)

        self._refresh_tree()

    def _control_label_changed(self, txt: str) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]["label"] = txt

    def _control_tooltip_changed(self) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]["tooltip"] = self.edit_tooltip.toPlainText()

    def _entry_kind_changed(self, kind: str) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
        spec["type"] = kind

        # normalize keys for kind
        if kind == "scalar":
            spec.setdefault("scalar_type", "float")
            spec.setdefault("range", flow_seqify([0.0, 1.0]))
            spec.pop("dim", None)
        elif kind == "vector":
            spec.pop("scalar_type", None)
            spec.pop("range", None)
            # store as int
            if not isinstance(spec.get("dim", 1), int):
                spec["dim"] = 1
            spec.setdefault("dim", 1)
        else:  # matrix
            spec.pop("scalar_type", None)
            spec.pop("range", None)
            d = spec.get("dim")
            if not (isinstance(d, (list, tuple, FlowSeq)) and len(d) == 2):
                spec["dim"] = flow_seqify([1, 1])

        self._load_entry_fields(spec)

    def _scalar_type_changed(self, st: str) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
        spec["scalar_type"] = st

    def _range_changed(self, _ = None) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
        if spec.get("type") != "scalar":
            return
        try:
            r0 = float(self.range_min.text())
            r1 = float(self.range_max.text())
        except ValueError:
            return

        spec["range"] = flow_seqify([int(r0), int(r1)]) if spec.get("scalar_type") == "int" else flow_seqify([r0, r1])

    def _dim_changed(self, _=None) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]

        kind = spec.get("type")
        if kind == "vector":
            if self.vec_dep.isChecked():
                spec["dim_from"] = self.vec_dim.text()
                if spec.get("dim"):
                    del spec["dim"]
                return
            
            try:
                dim = int(self.vec_dim.text())
                spec["dim"] = dim
            except ValueError:
                return
            finally:
                if spec.get("dim_from"):
                    del spec["dim_from"]
        elif kind == "matrix":
            dim_rows = self.mat_rows.text()
            dim_cols = self.mat_cols.text()
            if self.mat_rows_dep.isChecked() or self.mat_cols_dep.isChecked():
                spec["dim_from"] = flow_seqify([dim_rows, dim_cols])
                if spec.get("dim"):
                    del spec["dim"]
            else:
                spec["dim"] = flow_seqify([dim_rows, dim_cols])
                if spec.get("dim_from"):
                    del spec["dim_from"]

    def _dropdown_item_changed(self, item: qw.QTableWidgetItem) -> None:
        ref = self._current_control_ref()
        if not ref:
            return
        di, ri, ci = ref
        spec = self._working_data[self._current_model][di]["rows"][ri]["controls"][ci]
        if spec.get("control_type") != "dropdown":
            return

        names, values = [], []
        for r in range(self.dropdown_table.rowCount()):
            n = self.dropdown_table.item(r, 0)
            v = self.dropdown_table.item(r, 1)
            names.append(n.text() if n else "")
            values.append(v.text() if v else "")
        spec["names"] = flow_seqify(names)
        spec["values"] = flow_seqify(values)

    def _add_dropdown_option(self) -> None:
        if self.dropdown_table is None:
            return
        r = self.dropdown_table.rowCount()
        self.dropdown_table.insertRow(r)
        self.dropdown_table.setItem(r, 0, qw.QTableWidgetItem("Option"))
        self.dropdown_table.setItem(r, 1, qw.QTableWidgetItem("Value"))
        # commit
        self._dropdown_item_changed(None)

    def _remove_dropdown_option(self) -> None:
        rows = sorted({i.row() for i in self.dropdown_table.selectedItems()}, reverse=True)
        for r in rows:
            self.dropdown_table.removeRow(r)
        self._dropdown_item_changed(None)

    # -------------------------
    # Initializer
    # -------------------------

    def _initialize_clicked(self) -> None:
        if not self._current_model:
            return

        dlg = InitControlsDialog(self.env, self._current_model, self)
        if dlg.exec() != qw.QDialog.DialogCode.Accepted:
            return

        divs = dlg.build_dividers()

        # Replace current working data for this model
        self._working_data[self._current_model] = divs
        self._refresh_tree()
        self.window.status.show("Initialized control panel layout. Review and click Apply to save.", 5000)

    def set_model(self, model_name: str):
        idx = self.model_combo.findText(model_name)
        if idx >= 0 and idx != self.model_combo.currentIndex():
            self.model_combo.setCurrentIndex(idx)
