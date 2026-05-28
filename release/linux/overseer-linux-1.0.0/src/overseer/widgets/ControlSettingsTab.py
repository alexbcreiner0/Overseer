from __future__ import annotations
from dataclasses import fields
from typing import Any, Dict, List, Optional, Tuple, TypedDict, Literal
import os, copy, yaml, re
from collections.abc import Sequence

import logging
logger = logging.getLogger(__name__)

from overseer.tools.loader import load_parameters_class_from_file
from overseer.tools.creation_tools import flow_seqify, FlowSeq, atomic_write
from .common import refresh_models
from .InitControlsDialog import InitControlsDialog
from .HelpFormLayout import HelpFormLayout
from PyQt6 import QtWidgets as qw, QtCore as qc, QtGui as qg

_DIVIDER_RE = re.compile(r"^divider(\d+)$")
_ROW_RE     = re.compile(r"^row(\d+)$")

# change so that there is a field called details which has specific things based on control type
class ControlSpec(TypedDict):
    param_name: str
    control_type: str
    type: str
    scalar_type: str
    range: Sequence[float]
    label: str
    tooltip: str

def is_divider(key: str) -> bool:
    return bool(_DIVIDER_RE.match(key))

def is_row(key: str) -> bool:
    return bool(_ROW_RE.match(key))

class ControlSettingsTab(qw.QWidget):
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

        # when the entry type is changed, the widgets aren't cleared
        #  instead, the control type is edited according to the choice. 
        #  this dict specifies which fields are to be deleted  (all except)
        #  the current type
        self.control_type_specific_fields = {
            "dropdown": {
                "param_name",
                "names_from",
                "values_from",
                "use_names_func",
                "use_vals_func",
                "names",
                "values",
                "change_effect"
            },
            "entry_block": {
                "param_name",
                "type",
                "scalar_type",
                "range",
                "dim",
                "dim_from",
                "change_effect"
            },
            "button": {
                "function",
                "action_type",
            },
            "checkbox": {
                "param_name",
                "change_effect"
            },
        }

        root = qw.QVBoxLayout(self)

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

        left_widget = qw.QWidget()
        left_lay = qw.QVBoxLayout(left_widget)
        left_lay.addWidget(qw.QLabel("Control panel layout"))

        self.tree = qw.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(qw.QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setDragDropMode(qw.QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(qc.Qt.DropAction.MoveAction)
        self.tree.setDropIndicatorShown(True)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        tree_model = self.tree.model()
        tree_model.rowsMoved.connect(lambda *args: self._schedule_tree_sync())
        tree_model.rowsInserted.connect(lambda *args: self._schedule_tree_sync())
        tree_model.rowsRemoved.connect(lambda *args: self._schedule_tree_sync())
        tree_model.layoutChanged.connect(self._schedule_tree_sync)
        tree_model.rowsMoved.connect(self._on_tree_rows_moved)
        left_lay.addWidget(self.tree, 1)

        button_row = qw.QHBoxLayout()
        self.button_add_divider = qw.QPushButton("+ Divider")
        self.button_add_divider.clicked.connect(self._add_divider)
        button_row.addWidget(self.button_add_divider)

        self.button_add_control = qw.QPushButton("+ Control")
        self.button_add_control.clicked.connect(self._add_control)
        button_row.addWidget(self.button_add_control)

        self.button_add_row = qw.QPushButton("+ Row")
        self.button_add_row.clicked.connect(self._add_row)
        button_row.addWidget(self.button_add_row)

        self.button_delete = qw.QPushButton("Delete")
        self.button_delete.clicked.connect(self._delete_selected)
        button_row.addWidget(self.button_delete)

        left_lay.addLayout(button_row)
        splitter.addWidget(left_widget)

        right_widget = qw.QWidget()
        right_lay = qw.QVBoxLayout(right_widget)

        self.editor_stack = qw.QStackedWidget()
        right_lay.addWidget(self.editor_stack, 1)

        self.page_empty = qw.QLabel("Select a divider or control on the left to edit its settings.")
        self.page_empty.setWordWrap(True)
        self.page_empty.setAlignment(qc.Qt.AlignmentFlag.AlignTop | qc.Qt.AlignmentFlag.AlignLeft)
        self.editor_stack.addWidget(self.page_empty)

        self.page_divider = self._build_divider_editor()
        self.editor_stack.addWidget(self.page_divider)

        self.page_control = self._build_control_editor()
        self.editor_stack.addWidget(self.page_control)

        splitter.addWidget(right_widget)
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
                divider_idx, row_idx, control_idx = ref
                control_spec = self._working_data[self._current_model][divider_idx]["rows"][row_idx]["controls"][control_idx]
                self._populate_all_param_combos(control_spec.get("param_name", ""))

    def _build_divider_editor(self) -> qw.QWidget:
        widget = qw.QWidget()
        form = HelpFormLayout(widget)
        form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.divider_title = qw.QLineEdit()
        self.divider_title.textChanged.connect(self._divider_title_changed)

        form.addRow("Divider title:", self.divider_title)

        return widget

    def _add_row(self) -> None:
        if not self._current_model:
            return
        dividers = self._working_data[self._current_model]
        if not dividers:
            dividers.append({"title": "Parameters", "rows": [{"controls": []}]})

        payload = self._selected_payload()
        divider_idx = payload[1] if payload and payload[0] in {"divider", "row", "control"} else 0

        divider = dividers[divider_idx]
        divider.setdefault("rows", [])
        divider["rows"].append({"controls": []})
        self._refresh_tree()

    def _schedule_tree_sync(self) -> None:
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

    def _build_control_group_box(self) -> qw.QWidget:
        group_box = qw.QGroupBox("Control")
        form = HelpFormLayout(group_box)
        form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.param_combos = {}
        self.change_effect_combos = {}

        self.combo_control_type = qw.QComboBox()
        self.combo_control_type.addItems(["entry_block", "dropdown", "checkbox", "button"])
        self.combo_control_type.currentTextChanged.connect(self._control_type_changed)

        self.edit_label = qw.QLineEdit()
        self.edit_label.textChanged.connect(self._control_label_changed)

        self.edit_tooltip = qw.QPlainTextEdit()
        self.edit_tooltip.textChanged.connect(self._control_tooltip_changed)

        form.addRow("Control type:", self.combo_control_type, help_text= "The type of widget.")
        form.addRow("Label:", self.edit_label, help_text= "Accompanying text to identify your widget.")
        form.addRow("Tooltip:", self.edit_tooltip)

        return group_box

    def _new_param_combo(self, control_type: str) -> qw.QComboBox:
        combo = qw.QComboBox()
        combo.setEditable(False)
        combo.currentTextChanged.connect(self._param_name_changed)
        self.param_combos[control_type] = combo
        return combo

    def _new_change_effect_combo(self, control_type: str) -> qw.QComboBox:
        combo = qw.QComboBox()
        combo.addItem("Restart", "restart")
        combo.addItem("Send message", "send_message")
        combo.setEditable(False)
        combo.currentTextChanged.connect(self._change_effect_changed)
        self.change_effect_combos[control_type] = combo
        return combo

    def _active_param_combo(self) -> Optional[qw.QComboBox]:
        ctype = self.combo_control_type.currentText()
        return self.param_combos.get(ctype)

    def _active_change_effect_combo(self) -> Optional[qw.QComboBox]:
        ctype = self.combo_control_type.currentText()
        return self.change_effect_combos.get(ctype)

    def _build_entry_page(self) -> qw.QWidget:
        entry_page = qw.QWidget()
        entry_form = HelpFormLayout(entry_page)
        entry_form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)
        entry_form.setRowWrapPolicy(qw.QFormLayout.RowWrapPolicy.DontWrapRows)
        entry_form.setFieldGrowthPolicy(qw.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._entry_form = entry_form

        self.combo_entry_param_name = self._new_param_combo("entry_block")
        self.combo_entry_change_effect = self._new_change_effect_combo("entry_block")

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

        dim_func_row = qw.QWidget()
        dim_func_row_lay = qw.QHBoxLayout(dim_func_row)
        self.dim_func_check = qw.QCheckBox("Dimension from function:")
        self.dim_func_name = qw.QLineEdit()
        dim_func_row_lay.addWidget(self.dim_func_check)
        dim_func_row_lay.addWidget(self.dim_func_name)

        self.dim_func_safe_default_entry = qw.QLineEdit()

        self.dim_func_row = qw.QWidget()
        dim_func_row_lay = qw.QHBoxLayout(self.dim_func_row)
        dim_func_row_lay.setContentsMargins(0, 0, 0, 0)

        self.dim_func_check = qw.QCheckBox("Dimension from function:")
        self.dim_func_name = qw.QLineEdit()

        dim_func_row_lay.addWidget(self.dim_func_check)
        dim_func_row_lay.addWidget(self.dim_func_name)

        self.dim_func_check.toggled.connect(self._dim_changed)
        self.dim_func_name.textChanged.connect(self._dim_changed)
        self.dim_func_safe_default_entry.textChanged.connect(self._dim_changed)

        self.dim_stack = qw.QStackedWidget()
        self.dim_stack.setSizePolicy(
            qw.QSizePolicy.Policy.Expanding,
            qw.QSizePolicy.Policy.Fixed,
        )

        vec_specific_widget = qw.QWidget()
        vec_specific_form = HelpFormLayout(vec_specific_widget)

        self.vec_dim = qw.QLineEdit()
        self.vec_dim.textChanged.connect(self._dim_changed)

        vec_specific_form.addRow("Dim:", self.vec_dim)
        self.dim_stack.addWidget(vec_specific_widget)

        mat_specific_widget = qw.QWidget()
        mat_specific_form = HelpFormLayout(mat_specific_widget)  

        mat_dim_widget = qw.QWidget()
        mat_dim_widget_lay = qw.QHBoxLayout(mat_dim_widget)
        mat_dim_widget_lay.setContentsMargins(0, 0, 0, 0)

        self.mat_rows = qw.QLineEdit()
        self.mat_rows.textChanged.connect(self._dim_changed)

        self.mat_cols = qw.QLineEdit()
        self.mat_cols.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        self.mat_cols.textChanged.connect(self._dim_changed)

        mat_dim_widget_lay.addWidget(self.mat_rows)
        mat_dim_widget_lay.addWidget(qw.QLabel("x"))
        mat_dim_widget_lay.addWidget(self.mat_cols)

        mat_specific_form.addRow("Dim:", mat_dim_widget)
        self.dim_stack.addWidget(mat_specific_widget)

        entry_form.addRow("Param:", self.combo_entry_param_name, help_text= "The parameter that the widget will effect.")
        entry_form.addRow("Change effect:", self.combo_entry_change_effect, help_text= "Whether the simulation is to restart or send a message when the widget is altered. If you don't know what you are doing, stick to restart.")
        entry_form.addRow("Entry type:", self.combo_entry_kind, help_text= "The type of entry.")
        entry_form.addRow("Scalar type:", self.combo_scalar_type, help_text= "Whether the scalar is an int or a float.")
        entry_form.addRow("Range min:", self.range_min, help_text= "The left-most position of the slider. Only effects the slider - users can still set lower entries manually.")
        entry_form.addRow("Range max:", self.range_max, help_text= "The right-most position of the slider. Only effects the slider - users can still set lower entries manually.")
        entry_form.addRow("", self.dim_func_row, help_text= "When checked, Overseer will look for a function by the name specified in this field in your model's extra_functions.py file, and attempt to call that in order to determine the dimension of your vector/matrix. See documentation for more info.")
        entry_form.addRow("Safe default:", self.dim_func_safe_default_entry, help_text= "ONLY RELEVANT WHEN DIMENSION IS TO BE DETERMINED FROM A FUNCTION. When the dimension is increased, Overseer needs a 'safe-bet' number that it can use to fill in the new entries which appear. This is that.")
        entry_form.addRow("", self.dim_stack, help_text= "The dimension of your matrix or vector.")

        return entry_page

    def _build_dropdown_page(self) -> qw.QWidget:
        drop_page = qw.QWidget()
        drop_page_layout = qw.QVBoxLayout(drop_page)

        drop_param_box = qw.QWidget()
        drop_param_form = HelpFormLayout(drop_param_box)
        drop_param_form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)
        self.combo_dropdown_param_name = self._new_param_combo("dropdown")
        self.combo_dropdown_change_effect = self._new_change_effect_combo("dropdown")
        drop_param_form.addRow("Param:", self.combo_dropdown_param_name, help_text= "The parameter that the widget will effect.")
        drop_param_form.addRow("Change effect:", self.combo_dropdown_change_effect, help_text= "Whether the simulation is to restart or send a message when the widget is altered. If you don't know what you are doing, stick to restart.")
        drop_page_layout.addWidget(drop_param_box)
        top_drop_bar = qw.QWidget()
        top_drop_bar_lay = qw.QHBoxLayout(top_drop_bar)
        top_drop_bar_lay.setSpacing(30)
        self.dropdown_values_from_check = qw.QCheckBox("Values from function: ")
        self.dropdown_names_from_check = qw.QCheckBox("Names from function: ")
        self.dropdown_values_from_entry = qw.QLineEdit()
        self.dropdown_names_from_entry = qw.QLineEdit()
        top_drop_bar_left = qw.QHBoxLayout()
        top_drop_bar_right = qw.QHBoxLayout()
        top_drop_bar_left.setSpacing(0)
        top_drop_bar_right.setSpacing(0)
        top_drop_bar_left.addWidget(self.dropdown_names_from_check)
        top_drop_bar_left.addWidget(self.dropdown_names_from_entry)
        top_drop_bar_right.addWidget(self.dropdown_values_from_check)
        top_drop_bar_right.addWidget(self.dropdown_values_from_entry)
        self.dropdown_table = qw.QTableWidget(0, 2)
        self.dropdown_table.setHorizontalHeaderLabels(["Name", "Value"])
        self.dropdown_table.horizontalHeader().setSectionResizeMode(0, qw.QHeaderView.ResizeMode.Stretch)
        self.dropdown_table.horizontalHeader().setSectionResizeMode(1, qw.QHeaderView.ResizeMode.Stretch)
        self.dropdown_table.itemChanged.connect(self._dropdown_item_changed)
        top_drop_bar_lay.addLayout(top_drop_bar_left)
        top_drop_bar_lay.addLayout(top_drop_bar_right)
        drop_page_layout.addWidget(top_drop_bar)
        drop_page_layout.addWidget(self.dropdown_table, 1)

        self.dropdown_names_from_check.toggled.connect(
            lambda checked: self._set_dropdown_column_mode(col=0, from_function=checked)
        )
        self.dropdown_values_from_check.toggled.connect(
            lambda checked: self._set_dropdown_column_mode(col=1, from_function=checked)
        )
        self.dropdown_values_from_entry.textChanged.connect(self._dropdown_vals_func_changed)
        self.dropdown_names_from_entry.textChanged.connect(self._dropdown_names_func_changed)
        self.dropdown_names_from_check.checkStateChanged.connect(self._dropdown_names_checkbox_changed)
        self.dropdown_values_from_check.checkStateChanged.connect(self._dropdown_vals_checkbox_changed)

        # initialize states
        self._set_dropdown_column_mode(0, self.dropdown_names_from_check.isChecked())
        self._set_dropdown_column_mode(1, self.dropdown_values_from_check.isChecked())

        self.dropdown_widgets = [
            self.dropdown_names_from_check,
            self.dropdown_values_from_check,
            self.dropdown_values_from_entry,
            self.dropdown_names_from_entry,
            self.dropdown_table,
            self.combo_dropdown_change_effect
        ]

        dbtns = qw.QHBoxLayout()
        self.btn_add_option = qw.QPushButton("+ Option")
        self.btn_add_option.clicked.connect(self._add_dropdown_option)
        dbtns.addWidget(self.btn_add_option)
        self.btn_del_option = qw.QPushButton("Remove option")
        self.btn_del_option.clicked.connect(self._remove_dropdown_option)
        dbtns.addWidget(self.btn_del_option)
        dbtns.addStretch(1)
        drop_page_layout.addLayout(dbtns)

        return drop_page

    def _build_checkbox_page(self) -> qw.QWidget:
        check_page = qw.QWidget()
        check_form = HelpFormLayout(check_page)
        check_form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)
        self.combo_checkbox_param_name = self._new_param_combo("checkbox")
        self.combo_checkbox_change_effect = self._new_change_effect_combo("checkbox")
        check_form.addRow("Param:", self.combo_checkbox_param_name, help_text= "The parameter that the widget will effect.")
        check_form.addRow("Change effect:", self.combo_checkbox_change_effect, help_text= "Whether the simulation is to restart or send a message when the widget is altered. If you don't know what you are doing, stick to restart.")
        return check_page

    def _build_button_page(self) -> qw.QWidget:
        button_page = qw.QWidget()
        button_form = HelpFormLayout(button_page)
        button_form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.button_function = qw.QLineEdit()
        self.button_function.textChanged.connect(self._button_function_changed)

        self.button_action_type = qw.QComboBox()
        self.button_action_type.addItem("Replace params", "replace_params")
        self.button_action_type.addItem("Sim event", "sim_event")
        self.button_action_type.currentIndexChanged.connect(self._button_action_type_changed)

        button_form.addRow("Function:", self.button_function, help_text= "The function to be called when the button is pressed. Functions are looked for in a file called extra_functions.py, which you should make inside of your model's simulation directory.")
        button_form.addRow("Action type:", self.button_action_type, help_text= "When replace params is chosen, function will be expected to return a new params dataclass, to load a new set of parameters. When sim event is chosen, the function is expected to return an event, which is pushed to the sim event queue for your simulation to eventually look at and act upon.")
        return button_page

    def _build_control_editor(self) -> qw.QWidget:
        widget = qw.QWidget()
        outer_lay = qw.QVBoxLayout(widget)
        group_box = self._build_control_group_box()
        outer_lay.addWidget(group_box)
        self.control_stack = qw.QStackedWidget()
        outer_lay.addWidget(self.control_stack, 1)

        # build individual stack pages
        entry_page = self._build_entry_page()
        self.control_stack.addWidget(entry_page)
        dropdown_page = self._build_dropdown_page()
        self.control_stack.addWidget(dropdown_page)
        check_page = self._build_checkbox_page()
        self.control_stack.addWidget(check_page)
        button_page = self._build_button_page()
        self.control_stack.addWidget(button_page)

        outer_lay.addStretch(0)
        return widget

    def _block_dropdown_entry_signals(self, val: bool):
        if not getattr(self, "dropdown_widgets"):
            return

        for widget in self.dropdown_widgets:
            widget.blockSignals(val)

    def _set_dropdown_column_mode(self, col: int, from_function: bool) -> None:
        if col == 0:
            entry = self.dropdown_names_from_entry
        elif col == 1:
            entry = self.dropdown_values_from_entry
        else:
            return

        entry.setEnabled(from_function)
        table = self.dropdown_table

        table.blockSignals(True)
        try:
            for row in range(table.rowCount()):
                item = table.item(row, col)

                if item is None:
                    item = qw.QTableWidgetItem("")
                    table.setItem(row, col, item)

                flags = item.flags()

                if from_function:
                    flags &= ~qc.Qt.ItemFlag.ItemIsEditable
                    flags &= ~qc.Qt.ItemFlag.ItemIsEnabled
                else:
                    # Visually enabled + editable
                    flags |= qc.Qt.ItemFlag.ItemIsEnabled
                    flags |= qc.Qt.ItemFlag.ItemIsEditable

                item.setFlags(flags)

        finally:
            table.blockSignals(False)

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
        self._ensure_available_params(model)
        self._refresh_tree()
        self.editor_stack.setCurrentIndex(0)

    def _reload_current_model(self) -> None:
        if not self._current_model:
            return
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
                        row["controls"].append(self._normalize_loaded_spec(pname, spec))

                current["rows"].append(row)

        return dividers

    def _is_sub_panel_spec(self, spec: dict) -> bool:
        ctype = str(spec.get("control_type", ""))
        return ctype.startswith("hsub_panel") or ctype.startswith("vsub_panel")

    def _normalize_loaded_spec(self, yaml_key: str, spec: dict) -> dict:
        """Return an editor-friendly copy without destroying YAML-only sub-panel structure."""
        c = copy.deepcopy(spec)
        c["__yaml_key"] = yaml_key
        ctype = str(c.get("control_type", ""))

        if ctype == "button":
            c.pop("param_name", None)
            return c

        if self._is_sub_panel_spec(c):
            c.pop("param_name", None)
            entries = c.get("entries", {})
            if isinstance(entries, dict):
                c["entries"] = {
                    str(child_key): self._normalize_loaded_spec(str(child_key), child_spec)
                    for child_key, child_spec in entries.items()
                    if isinstance(child_spec, dict)
                }
            else:
                c["entries"] = {}
            return c

        c.setdefault("param_name", yaml_key)
        return c

    def _flowify_recursive_fields(self, spec: dict) -> dict:
        spec2 = copy.deepcopy(spec)
        spec2.pop("__yaml_key", None)
        for k in ("range", "names", "values", "dim"):
            if k in spec2 and isinstance(spec2[k], list):
                spec2[k] = flow_seqify(spec2[k])

        entries = spec2.get("entries")
        if isinstance(entries, dict):
            used_keys: set[str] = set()
            new_entries: Dict[str, Any] = {}
            for idx, child in enumerate(entries.values()):
                if not isinstance(child, dict):
                    continue
                key = self._control_yaml_key(child, idx, used_keys)
                if key:
                    new_entries[key] = self._flowify_recursive_fields(child)
            spec2["entries"] = new_entries

        if spec2.get("control_type") == "button" or self._is_sub_panel_spec(spec2):
            spec2.pop("param_name", None)

        return spec2

    def _tree_label_for_spec(self, spec: dict, fallback: str = "control") -> str:
        ctype = str(spec.get("control_type", ""))
        if self._is_sub_panel_spec(spec):
            orientation = "Horizontal" if ctype.startswith("hsub_panel") else "Vertical"
            label = spec.get("label") or spec.get("name") or fallback
            return f"{orientation} sub-panel: {label}"
        if ctype == "button":
            return str(spec.get("label") or spec.get("name") or spec.get("function") or "button")
        return str(spec.get("param_name") or spec.get("label") or fallback)

    def _add_spec_tree_item(
        self,
        parent: qw.QTreeWidgetItem,
        spec: dict,
        payload: tuple,
        *,
        editable: bool = True,
    ) -> qw.QTreeWidgetItem:
        item = qw.QTreeWidgetItem([self._tree_label_for_spec(spec)])
        flags = item.flags()
        if editable:
            flags |= qc.Qt.ItemFlag.ItemIsDragEnabled
            if self._is_sub_panel_spec(spec):
                flags |= qc.Qt.ItemFlag.ItemIsDropEnabled
        else:
            flags &= ~qc.Qt.ItemFlag.ItemIsDragEnabled
            flags &= ~qc.Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(flags)
        item.setData(0, self.ROLE, payload)
        parent.addChild(item)

        if self._is_sub_panel_spec(spec):
            entries = spec.get("entries", {})
            if isinstance(entries, dict):
                for child_key, child_spec in entries.items():
                    if isinstance(child_spec, dict):
                        self._add_spec_tree_item(
                            item,
                            child_spec,
                            ("readonly_spec", child_key),
                            editable=False,
                        )
            item.setExpanded(True)

        return item

    def _populate_param_combo(self, current: str, combo: Optional[qw.QComboBox] = None) -> None:
        combo = combo or self._active_param_combo()
        if combo is None:
            return

        model = self._current_model
        names = self._available_params.get(model, []) if model else []

        combo.blockSignals(True)
        combo.clear()

        if not names:
            if current:
                combo.addItem(f"(missing) {current}", userData=current)
            combo.blockSignals(False)
            return

        if current and current not in names:
            combo.addItem(f"(missing) {current}", userData=current)

        for n in names:
            combo.addItem(n, userData=n)

        # Select current if possible; otherwise first real param
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)
        else:
            combo.setCurrentIndex(0)

        combo.blockSignals(False)

    def _populate_all_param_combos(self, current: str) -> None:
        for combo in getattr(self, "param_combos", {}).values():
            self._populate_param_combo(current, combo)

    def _param_name_changed(self, txt: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") == "button":
            control_spec.pop("param_name", None)
            return

        combo = self.sender() if isinstance(self.sender(), qw.QComboBox) else self._active_param_combo()
        if combo is None:
            return

        idx = combo.currentIndex()
        val = combo.itemData(idx)
        if isinstance(val, str) and val:
            control_spec["param_name"] = val
        else:
            control_spec["param_name"] = txt.replace("(missing) ", "").strip()

        self._refresh_tree()

    def _change_effect_changed(self, txt: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") == "button":
            control_spec.pop("param_name", None)
            return

        combo = self.sender() if isinstance(self.sender(), qw.QComboBox) else self._active_change_effect_combo()
        if combo is None:
            return

        idx = combo.currentIndex()
        val = combo.itemData(idx)
        if isinstance(val, str) and val:
            control_spec["change_effect"] = val
        else:
            control_spec["change_effect"] = txt.replace("(missing) ", "").strip()

        self._refresh_tree()

    def _control_yaml_key(self, spec: ControlSpec, index: int, used: set[str]) -> str:
        ctype = str(spec.get("control_type", ""))
        if ctype == "button":
            base = str(spec.get("__yaml_key") or spec.get("name") or spec.get("label") or spec.get("function") or f"button{index + 1}").strip()
            base = re.sub(r"\W+", "_", base).strip("_") or f"button{index + 1}"
        elif self._is_sub_panel_spec(spec):
            default = "hsub_panel" if ctype.startswith("hsub_panel") else "vsub_panel"
            base = str(spec.get("__yaml_key") or spec.get("name") or spec.get("label") or f"{default}{index + 1}").strip()
            base = re.sub(r"\W+", "_", base).strip("_") or f"{default}{index + 1}"
        else:
            base = str(spec.get("param_name", "")).strip()

        key = base
        n = 2
        while key in used:
            key = f"{base}_{n}"
            n += 1
        used.add(key)
        return key

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

                used_keys: set[str] = set()
                for idx, spec in enumerate(controls):
                    key = self._control_yaml_key(spec, idx, used_keys)
                    if not key:
                        continue

                    row_dict[key] = self._flowify_recursive_fields(spec)

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
            logger.log(logging.ERROR, "Error writing changes", exc_info= e)
        else:
            self._original_data.clear()
            self._working_data.clear()
            self._ensure_loaded(self._current_model)
            self._refresh_tree()

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
                    if not isinstance(spec, dict):
                        continue
                    self._add_spec_tree_item(row_item, spec, ("control", di, ri, ci), editable=True)

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
            self.page_empty.setText("Select a divider or control on the left to edit its settings.")
            self.editor_stack.setCurrentIndex(0)
            return

        kind = payload[0]

        if kind == "divider":
            _, divider_idx = payload
            div = self._working_data[self._current_model][divider_idx]
            self.divider_title.blockSignals(True)
            self.divider_title.setText(div.get("title", ""))
            self.divider_title.blockSignals(False)
            self.editor_stack.setCurrentWidget(self.page_divider)
            return

        if kind == "control":
            _, divider_idx, row_idx, control_idx = payload
            try:
                spec = self._working_data[self._current_model][divider_idx]["rows"][row_idx]["controls"][control_idx]
            except Exception:
                self.editor_stack.setCurrentIndex(0)
                return
            if isinstance(spec, dict) and self._is_sub_panel_spec(spec):
                self.page_empty.setText(
                    "This is a YAML-only sub-panel container. Its nested entries will be preserved on Apply, "
                    "but this editor does not edit sub-panels yet."
                )
                self.editor_stack.setCurrentIndex(0)
                return
            self._load_control_into_editor(spec)
            self.editor_stack.setCurrentWidget(self.page_control)
            return

        if kind == "readonly_spec":
            self.page_empty.setText(
                "This nested sub-panel entry is shown for reference and will be preserved on Apply. "
                "Nested sub-panel editing is not enabled yet."
            )
            self.editor_stack.setCurrentIndex(0)
            return

        # rows don't have settings yet
        self.page_empty.setText("Select a divider or control on the left to edit its settings.")
        self.editor_stack.setCurrentIndex(0)

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

        new_spec = {
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

    def _current_control_ref(self) -> Optional[Tuple[int, int, int]]:
        payload = self._selected_payload()
        if not payload or payload[0] != "control" or not self._current_model:
            return None
        _, divider_idx, row_idx, control_idx = payload
        return (divider_idx, row_idx, control_idx)

    def _load_control_into_editor(self, spec) -> None:
        ctype = str(spec.get("control_type", "entry_block"))
        if ctype not in {"entry_block", "dropdown", "checkbox", "button"}:
            ctype = "entry_block"

        self.combo_control_type.blockSignals(True)
        self.combo_control_type.setCurrentText(ctype)
        self.combo_control_type.blockSignals(False)

        if ctype == "button":
            label = str(spec.get("name", ""))
        else:
            label = str(spec.get("label", ""))

        current_param = "" if ctype == "button" else str(spec.get("param_name", ""))
        self._populate_all_param_combos(current_param)

        self.edit_label.blockSignals(True)
        self.edit_label.setText(label)
        self.edit_label.blockSignals(False)

        self.edit_tooltip.blockSignals(True)
        self.edit_tooltip.setPlainText(str(spec.get("tooltip", "")))
        self.edit_tooltip.blockSignals(False)

        if ctype == "dropdown":
            self.control_stack.setCurrentIndex(1)
            self._load_dropdown_table(spec)
        elif ctype == "checkbox":
            self.control_stack.setCurrentIndex(2)
        elif ctype == "button":
            self.control_stack.setCurrentIndex(3)
            self._load_button_fields(spec)
        else:
            self.control_stack.setCurrentIndex(0)
            self._load_entry_fields(spec)

    def _load_entry_fields(self, spec) -> None:
        kind = str(spec.get("type", "scalar"))

        self.combo_entry_kind.blockSignals(True)
        if kind in {"scalar", "vector", "matrix"}:
            self.combo_entry_kind.setCurrentText(kind)
        else:
            kind = "scalar"
            self.combo_entry_kind.setCurrentText("scalar")
        self.combo_entry_kind.blockSignals(False)

        st = str(spec.get("scalar_type", "float"))
        self.combo_scalar_type.blockSignals(True)
        self.combo_scalar_type.setCurrentText(st if st in {"int", "float"} else "float")
        self.combo_scalar_type.blockSignals(False)

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

        use_dim_func = spec.get("use_dim_func", False)
        if use_dim_func:
            self.dim_func_check.blockSignals(True)
            self.dim_func_check.setChecked(True)
            self.dim_func_check.blockSignals(False)

        if spec.get("dim_from", None) is not None:
            func_name = spec.get("dim_from")
            self.dim_func_name.blockSignals(True)
            self.dim_func_name.setText(func_name)
            self.dim_func_name.blockSignals(False)

        self.vec_dim.blockSignals(True)
        self.mat_rows.blockSignals(True)
        self.mat_cols.blockSignals(True)
        self.dim_func_safe_default_entry.blockSignals(True)

        if kind == "vector":
            if spec.get("dim") is not None:
                dim = spec.get("dim")
                try:
                    self.vec_dim.setText(str(dim))
                except Exception:
                    self.vec_dim.setText("1" if not use_dim_func else "")
            else:
                self.vec_dim.setText("1" if not use_dim_func else "")
            self.dim_stack.setCurrentIndex(0)

            if spec.get("safe_default") is not None:
                try:
                    safe_default = spec.get("safe_default")
                    self.dim_func_safe_default_entry.setText(str(safe_default))
                except Exception:
                    self.dim_func_safe_default_entry.setText("0.1")
        elif kind == "matrix":
            if spec.get("dim") is not None:
                dim = spec.get("dim")
                try:
                    rows, cols = dim[0], dim[1]
                    self.mat_rows.setText(str(rows))
                    self.mat_cols.setText(str(cols))
                except Exception:
                    rows, cols = 1, 1
                    self.mat_rows.setText("1" if not use_dim_func else "")
                    self.mat_cols.setText("1" if not use_dim_func else "")
            else:
                self.mat_rows.setText("1" if not use_dim_func else "")
                self.mat_cols.setText("1" if not use_dim_func else "")
            self.dim_stack.setCurrentIndex(1)
            if spec.get("safe_default") is not None:
                try:
                    safe_default = spec.get("safe_default")
                    self.dim_func_safe_default_entry.setText(str(safe_default))
                except Exception:
                    self.dim_func_safe_default_entry.setText("0.1")
        else:
            self.dim_stack.setCurrentIndex(0)

        self.vec_dim.blockSignals(False)
        self.mat_rows.blockSignals(False)
        self.mat_cols.blockSignals(False)
        self.dim_func_safe_default_entry.blockSignals(False)

        eform = getattr(self, "_entry_form", None)
        if eform is not None:
            show_scalar = (kind == "scalar")
            show_dim = (kind in {"vector", "matrix"})

            eform.setRowVisible(self.combo_scalar_type, show_scalar)
            eform.setRowVisible(self.range_min, show_scalar)
            eform.setRowVisible(self.range_max, show_scalar)

            eform.setRowVisible(self.dim_func_row, show_dim)
            eform.setRowVisible(self.dim_func_safe_default_entry, show_dim)
            eform.setRowVisible(self.dim_stack, show_dim)
        else:
            self.combo_scalar_type.setVisible(kind == "scalar")
            self.range_min.setVisible(kind == "scalar")
            self.range_max.setVisible(kind == "scalar")
            self.dim_stack.setVisible(kind in {"vector", "matrix"})

    def _load_dropdown_table(self, spec: ControlSpec) -> None:
        use_names_func = spec.get("use_names_func", False)
        use_vals_func = spec.get("use_vals_func", False)

        if use_names_func:
            names_from = spec.get("names_from")
        else:
            names_from = ""

        names = spec.get("names", [])

        if use_vals_func:
            values_from = spec.get("values_from")
        else:
            values_from = ""

        values = list(spec.get("values", []))

        self._block_dropdown_entry_signals(True)

        self.dropdown_table.setRowCount(0)
        for _, (n, v) in enumerate(zip(names, values)):
            r = self.dropdown_table.rowCount()
            self.dropdown_table.insertRow(r)
            self.dropdown_table.setItem(r, 0, qw.QTableWidgetItem(str(n)))
            self.dropdown_table.setItem(r, 1, qw.QTableWidgetItem(str(v)))

        if use_names_func:
            self.dropdown_names_from_check.setChecked(True)
            self.dropdown_names_from_entry.setText(names_from)
            self._set_dropdown_column_mode(0, True)
        else:
            self.dropdown_names_from_check.setChecked(False)
            self.dropdown_names_from_entry.setText("")
            self._set_dropdown_column_mode(0, False)

        if use_vals_func:
            self.dropdown_values_from_check.setChecked(True)
            self.dropdown_values_from_entry.setText(names_from)
            self._set_dropdown_column_mode(1, True)
        else:
            self.dropdown_values_from_check.setChecked(False)
            self.dropdown_values_from_entry.setText("")
            self._set_dropdown_column_mode(1, False)

        self._block_dropdown_entry_signals(False)

    def _control_type_changed(self, ctype: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return

        if ctype not in self.control_type_specific_fields:
            ctype = "entry_block"

        for control_type, fields in self.control_type_specific_fields.items():
            if control_type == ctype:
                continue
            for field_name in fields:
                control_spec.pop(field_name, None)

        control_spec["control_type"] = ctype

        if ctype != "button":
            if not control_spec.get("param_name"):
                names = self._available_params.get(self._current_model, []) if self._current_model else []
                if names:
                    control_spec["param_name"] = names[0]
            self._populate_all_param_combos(str(control_spec.get("param_name", "")))
        else:
            control_spec.pop("param_name", None)

        if ctype == "dropdown":
            control_spec.setdefault("names", flow_seqify(["True", "False"]))
            control_spec.setdefault("values", flow_seqify([True, False]))
            self.control_stack.setCurrentIndex(1)
            self._load_dropdown_table(control_spec)
        elif ctype == "checkbox":
            self.control_stack.setCurrentIndex(2)
        elif ctype == "button":
            control_spec.setdefault("function", "")
            control_spec.setdefault("action_type", "Replace params")
            self.control_stack.setCurrentIndex(3)
            self._load_button_fields(control_spec)
        else:
            control_spec.setdefault("type", "scalar")
            control_spec.setdefault("scalar_type", "float")
            control_spec.setdefault("range", flow_seqify([0.0, 1.0]))
            self.control_stack.setCurrentIndex(0)
            self._load_entry_fields(control_spec)

        self._refresh_tree()

    def _load_button_fields(self, spec: ControlSpec) -> None:
        self.button_function.blockSignals(True)
        self.button_function.setText(str(spec.get("function", "")))
        self.button_function.blockSignals(False)

        action_type = str(spec.get("action_type", "replace_params"))
        self.button_action_type.blockSignals(True)
        if action_type == "replace_params":
            self.button_action_type.setCurrentText("Replace params")
        elif action_type == "sim_event":
            self.button_action_type.setCurrentText("Sim event")
        self.button_action_type.blockSignals(False)

    def _button_function_changed(self, txt: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "button":
            return
        control_spec["function"] = txt
        self._refresh_tree()

    def _button_action_type_changed(self, idx: int) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "button":
            return

        match self.button_action_type.currentText():
            case "Replace params":
                control_spec["action_type"] = "replace_params"
            case "Sim event":
                control_spec["action_type"] = "sim_event"

    def _get_control_spec(self):
        ref = self._current_control_ref()
        if not ref:
            return None
        divider_idx, row_idx, control_idx = ref
        return self._working_data[self._current_model][divider_idx]["rows"][row_idx]["controls"][control_idx]

    def _control_label_changed(self, txt: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return

        if control_spec["control_type"] == "button":
            control_spec["name"] = txt
        else:
            control_spec["label"] = txt

    def _control_tooltip_changed(self) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        control_spec["tooltip"] = self.edit_tooltip.toPlainText()

    def _entry_kind_changed(self, kind: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return

        control_spec["type"] = kind
        if control_spec is None:
            return

        # get rid of the non-relevant fields, set reasonable defaults for new fields before trying to load
        if kind == "scalar":
            control_spec.setdefault("scalar_type", "float")
            control_spec.setdefault("range", flow_seqify([0.0, 1.0]))
            control_spec.pop("dim", None)
        elif kind == "vector":
            control_spec.pop("scalar_type", None)
            control_spec.pop("range", None)
            if not isinstance(control_spec.get("dim", 1), int):
                control_spec["dim"] = 1
            control_spec.setdefault("dim", 1)
        else:  
            control_spec.pop("scalar_type", None)
            control_spec.pop("range", None)
            d = control_spec.get("dim")
            if not (isinstance(d, (list, tuple, FlowSeq)) and len(d) == 2):
                control_spec["dim"] = flow_seqify([1, 1])

        # load whatever replacements exist for the defaults
        self._load_entry_fields(control_spec)

    def _scalar_type_changed(self, txt: str) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        control_spec["scalar_type"] = txt

    def _range_changed(self, _ = None) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("type") != "scalar":
            return
        try:
            r0 = float(self.range_min.text())
            r1 = float(self.range_max.text())
        except ValueError:
            return

        control_spec["range"] = flow_seqify([int(r0), int(r1)]) if control_spec.get("scalar_type") == "int" else flow_seqify([r0, r1])

    def _dim_changed(self, _ = None) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return

        kind = control_spec.get("type")
        if kind == "vector" or kind == "matrix":
            control_spec["use_dim_func"] = self.dim_func_check.isChecked()
            control_spec["dim_from"] = self.dim_func_name.text()

        if kind == "vector":
            try:
                dim = int(self.vec_dim.text())
                control_spec["dim"] = dim
            except ValueError:
                control_spec["dim"] = 1

            try:
                safe_default = float(self.dim_func_safe_default_entry.text())
                control_spec["safe_default"] = safe_default
            except ValueError:
                control_spec["safe_default"] = 0.1

        elif kind == "matrix":
            try:
                dim_rows = int(self.mat_rows.text())
                dim_cols = int(self.mat_cols.text())
                control_spec["dim"] = flow_seqify([dim_rows, dim_cols])
            except ValueError:
                control_spec["dim"] = flow_seqify([1,1])

            try:
                safe_default = float(self.dim_func_safe_default_entry.text())
                control_spec["safe_default"] = safe_default
            except ValueError:
                control_spec["safe_default"] = 0.1

    def _dropdown_item_changed(self, item: qw.QTableWidgetItem) -> None:
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "dropdown":
            return

        names, values = [], []
        for row in range(self.dropdown_table.rowCount()):
            name = self.dropdown_table.item(row, 0)
            val = self.dropdown_table.item(row, 1)
            names.append(name.text() if name else "")
            values.append(val.text() if val else "")
        control_spec["names"] = flow_seqify(names)
        control_spec["values"] = flow_seqify(values)

    def _dropdown_vals_func_changed(self, txt: str):
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "dropdown":
            return
        
        control_spec.setdefault("values_from", txt)

    def _dropdown_names_func_changed(self, txt: str):
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "dropdown":
            return
        if txt == "":
            return

        control_spec.setdefault("names_from", txt)

    def _dropdown_names_checkbox_changed(self, checked: bool):
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "dropdown":
            return

        control_spec["use_names_func"] = self.dropdown_names_from_check.isChecked()
        if checked:
            self._dropdown_names_func_changed(self.dropdown_names_from_entry.text())
        else:
            if "names_from" in control_spec:
                del control_spec["names_from"]

    def _dropdown_vals_checkbox_changed(self, checked: bool):
        control_spec = self._get_control_spec()
        if control_spec is None:
            return
        if control_spec.get("control_type") != "dropdown":
            return

        control_spec["use_vals_func"] = self.dropdown_values_from_check.isChecked()
        if checked:
            self._dropdown_vals_func_changed(self.dropdown_values_from_entry.text())
        else:
            if "names_from" in control_spec:
                del control_spec["names_from"]

    def _add_dropdown_option(self) -> None:
        if self.dropdown_table is None:
            return
        r = self.dropdown_table.rowCount()
        self.dropdown_table.insertRow(r)
        self.dropdown_table.setItem(r, 0, qw.QTableWidgetItem("Option"))
        self.dropdown_table.setItem(r, 1, qw.QTableWidgetItem("Value"))
        self._set_dropdown_column_mode(0, self.dropdown_names_from_check.isChecked())
        self._set_dropdown_column_mode(1, self.dropdown_values_from_check.isChecked())
        # commit
        self._dropdown_item_changed(None)

    def _remove_dropdown_option(self) -> None:
        rows = sorted({i.row() for i in self.dropdown_table.selectedItems()}, reverse=True)
        for r in rows:
            self.dropdown_table.removeRow(r)
        self._dropdown_item_changed(None)

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
