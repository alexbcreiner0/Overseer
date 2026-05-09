from __future__ import annotations
from pathlib import Path
import os, copy
import yaml
from .common import make_shortname, replace_key_preserve_order, refresh_models
from overseer.tools.creation_tools import flow_seqify, atomic_write
import logging
from .RowStackWidgets import *
from .HelpFormLayout import HelpFormLayout
from matplotlib import colormaps
import re

from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc,
    QtGui as qg
)

logger = logging.getLogger(__name__)

def list_subdirs(path):
    return [
            p.name
            for p in Path(path).iterdir()
            if p.is_dir()
        ]

def _safe_load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}

class PlotSettingsTab(qw.QWidget):
    ROLE = qc.Qt.ItemDataRole.UserRole  # store payload tuples here

    def __init__(self, env, model= None, parent=None):
        super().__init__(parent)

        self.env = env

        # Authoritative directory of info for each panel/plot type.
        self.plot_dir = {
            "Curve": {
                "build": self._build_curve_panel,
                "load": self._load_curve_info,
                "save": self._get_new_curve_data,
                "stack_idx": 1,
            },
            "Histogram": {
                "build": self._build_hist_panel,
                "load": self._load_hist_info,
                "save": self._get_new_hist_data,
                "stack_idx": 2,
                "yaml_name": "hist"
            },
            "Scatter": {
                "build": self._build_scatter_panel,
                "load": self._load_scatter_info,
                "save": self._get_new_scatter_data,
                "stack_idx": 3,
                "yaml_name": "scatter"
            },
            "Heatmap": {
                "build": self._build_heatmap_panel,
                "load": self._load_heatmap_info,
                "save": self._get_new_heatmap_data,
                "stack_idx": 4,
                "yaml_name": "heatmap"
            },
            "Pie Chart": {
                "build": self._build_pie_panel,
                "load": self._load_pie_info,
                "save": self._get_new_pie_data,
                "stack_idx": 5,
                "yaml_name": "pie"
            },
            "Vector Field": {
                "build": self._build_field_panel,
                "load": self._load_field_info,
                "save": self._get_new_field_data,
                "stack_idx": 6,
                "yaml_name": "vector"
            },
            "Discrete Graph": {
                "build": self._build_dgraph_panel,
                "load": self._load_dgraph_info,
                "save": self._get_new_dgraph_data,
                "stack_idx": 7,
                "yaml_name": "discrete_graph"
            },
            "Surface": {
                "build": self._build_surface_panel,
                "load": self._load_surface_info,
                "save": self._get_new_surface_data,
                "stack_idx": 8,
                "yaml_name": "surface"
            }
        }

        root = qw.QVBoxLayout(self)
        self.window = self.window()

        top = qw.QHBoxLayout()
        top.addWidget(qw.QLabel("Model:"))
        self.model_combo = qw.QComboBox()
        self.model_combo.setMinimumWidth(260)
        top.addWidget(self.model_combo, 1)

        self.reload_btn = qw.QPushButton("Reload")
        top.addWidget(self.reload_btn, 0)
        root.addLayout(top)


        splitter = qw.QSplitter(qc.Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # ========= Left column: Category/Plot Tree =========
        tree_panel = qw.QWidget()
        tree_layout = qw.QVBoxLayout(tree_panel)
        tree_layout.addWidget(qw.QLabel("Categories / Plots"))

        self.tree = qw.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(qw.QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setDragDropMode(qw.QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(qc.Qt.DropAction.MoveAction)
        self.tree.setDropIndicatorShown(True)
        self.tree.model().rowsMoved.connect(self._on_tree_rows_moved)
        self.tree.setExpandsOnDoubleClick(True)
        tree_layout.addWidget(self.tree, 1)

        btns = qw.QVBoxLayout()
        btns.setContentsMargins(0,0,0,0)
        btns_top = qw.QHBoxLayout()
        btns_bot = qw.QHBoxLayout()
        self.add_cat_btn = qw.QPushButton("+ Category")
        self.add_plot_btn = qw.QPushButton("+ Plot")
        self.del_cat_btn = qw.QPushButton("Delete")

        self.dup_plot_btn = qw.QPushButton("Duplicate in")
        self.dup_plot_dropdown = qw.QComboBox()

        self.add_cat_btn.clicked.connect(self._on_add_cat)
        self.add_plot_btn.clicked.connect(self._on_add_plot)
        self.del_cat_btn.clicked.connect(self._on_del_clicked)
        self.dup_plot_btn.clicked.connect(self._on_dup_plot_clicked)

        btns_top.addWidget(self.add_cat_btn)
        btns_top.addWidget(self.add_plot_btn)
        btns_top.addWidget(self.del_cat_btn)

        btns_bot.addWidget(self.dup_plot_btn)
        btns_bot.addWidget(self.dup_plot_dropdown, 1)
        btns.addLayout(btns_top)
        btns.addLayout(btns_bot)
        tree_layout.addLayout(btns)

        splitter.addWidget(tree_panel)

        editor_panel = qw.QWidget()
        editor_layout = qw.QVBoxLayout(editor_panel)

        self.form = HelpFormLayout()
        self.form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

        self.lbl_internal_name = qw.QLabel()
        self.name_edit = qw.QLineEdit()
        self.toggled_check = qw.QCheckBox("Initially toggled")
        self.name_edit.textChanged.connect(self._update_internal_name)

        self.form.addRow("Name:", self.name_edit, help_text= "The name which appears as the toggle checkbox.")
        self.form.addRow("Internal Name:", self.lbl_internal_name, help_text= "The name in the yaml file. Not really important.")
        self.form.addRow("", self.toggled_check, help_text= "Whether or not the plot is toggled by default.")

        self.plot_type_combo = qw.QComboBox()
        self.plot_type_combo.addItems(list(self.plot_dir.keys()))
        self.form.addRow("Plot type:", self.plot_type_combo)

        editor_layout.addLayout(self.form)

        self.field_widgets = [
            self.name_edit,
            self.toggled_check
        ]

        self.type_stack = qw.QStackedWidget()
        self.type_stack.addWidget(self._build_cat_panel())
        for name in self.plot_dir:
            build_func = self.plot_dir[name]["build"]
            self.type_stack.addWidget(build_func())
        editor_layout.addWidget(self.type_stack, 1)

        action_row = qw.QHBoxLayout()
        action_row.addStretch(1)
        self.save_changes_btn = qw.QPushButton("Save Changes")
        self.save_changes_btn.setVisible(False)
        action_row.addWidget(self.save_changes_btn)
        self.save_changes_btn.clicked.connect(self._save_changes)
        editor_layout.addLayout(action_row)

        splitter.addWidget(editor_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # --- state ---
        self._current_model: str | None = None
        self._plotting_data: dict = {}

        self._loading_editor: bool = False

        self.reload_btn.clicked.connect(self.reload_current_model)
        self.tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self.plot_type_combo.currentTextChanged.connect(self._on_plot_type_changed)

        self._refresh_models()
        self._current_model = self.model_combo.currentText().strip() or None
        if model is not None:
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            try:
                self.model_combo.setCurrentIndex(models.index(model))
            except ValueError:
                pass
            self._current_model = model

        self._working_plot_data = {}
        self._original_plot_data = {}
        if not self._current_model:
            return
        try:
            with open(self.env.models_dir / self._current_model / "data" / "plotting_data.yml", "r") as f:
                data = yaml.safe_load(f) or {}
            self._working_plot_data[self._current_model] = copy.deepcopy(data)
            self._original_plot_data[self._current_model] = copy.deepcopy(data)
        except FileNotFoundError as e:
            self.window.status.show("plotting_data.yml not found. Creating one automatically.")
            try:
                with open(self.env.models_dir / self._current_model / "data" / "plotting_data.yml", "w") as f:
                    pass
            except FileNotFoundError as e:
                self.window.status.show(f"Error opening the data folder of {self._current_model}. Have you ran the new model creation wizard yet?")
            self._original_plot_data[self._current_model] = {}
            self._working_plot_data[self._current_model] = {}
        except Exception as e:
            self.window.status.show(f"Error opening plotting_data.yml: {e}")
            self._original_plot_data[self._current_model] = {}
            self._working_plot_data[self._current_model] = {}

        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

        self._wire_autosave_signals()
        self._refresh_tree()

        # self.name_edit.returnPressed.connect(self._commit_plot_rename)  # keep textChanged autosave
        # self._cat_rename_commit_requested = False
        # self._pending_cat_key = None
        # self.name_edit.returnPressed.connect(self._commit_cat_rename)

    def _make_unique_internal_name(self, base_name: str, existing_names: list, current_name: str | None = None) -> str:
        name = make_shortname(base_name).strip()
        if not name: return ""

        existing = set(existing_names)
        if current_name:
            existing.discard(current_name)

        if name not in existing:
            return name

        match = re.match(r"^(.*?)(\d+)?$", name)
        stem = match.group(1) if match else name
        suffix = match.group(2) if match else None

        start = int(suffix) + 1 if suffix else 1
        i = start
        while f"{stem}{i}" in existing:
            i += 1

        return f"{stem}{i}"

    def _update_internal_name(self, text):
        name = make_shortname(text)
        current_sel = self.tree.currentItem()
        if current_sel is None:
            self.lbl_internal_name.setText(make_shortname(text))
            return

        data = current_sel.data(0, self.ROLE)
        if data[0] == "plot":
            cat = data[1]
            cat_data = self._working_plot_data[self._current_model][cat]
            current_plot_key = data[2]
            plots = list(cat_data["plots"].keys())

            name = self._make_unique_internal_name(text, plots, current_name= current_plot_key)
        else:
            categories = list(self._working_plot_data[self._current_model].keys())
            current_cat_key = data[1]

            name = self._make_unique_internal_name(text, categories, current_name= current_cat_key)

        self.lbl_internal_name.setText(name)
        return name

    def _block_editor_signals(self, block: bool) -> None:
            for w in self.field_widgets:
                try:
                    w.blockSignals(block)
                except Exception:
                    pass

    def _wire_autosave_signals(self) -> None:
        for widget in self.field_widgets:
            if isinstance(widget, (qw.QLineEdit, ColorLineEdit)):
                widget.textEdited.connect(self._save_changes)
            elif isinstance(widget, qw.QTextEdit):
                widget.textChanged.connect(self._save_changes)
            elif isinstance(widget, qw.QCheckBox):
                widget.checkStateChanged.connect(self._save_changes)
            elif isinstance(widget, qw.QDoubleSpinBox) or isinstance(widget, qw.QSpinBox):
                widget.valueChanged.connect(self._save_changes)
            elif isinstance(widget, qw.QComboBox):
                widget.currentIndexChanged.connect(self._save_changes)
            elif isinstance(widget, DynamicRowStack):
                widget.changed.connect(self._save_changes)
            else:
                print(f"We missed something: {type(widget)=}")

    def _on_plot_type_changed(self, plot_type: str) -> None:
        # stack_idx = {0: 1, 1: 2, 2: 3, 3: 4}.get(idx, 1)
        self.type_stack.setCurrentIndex(self.plot_dir[plot_type]["stack_idx"])
        self._save_changes()

    def _restore_cursor_pos(self, w, cursor_pos):
        if w not in self.field_widgets and w is not self.name_edit:
            return

        if not isinstance(w, (qw.QLineEdit, qw.QTextEdit)):
            return

        w.setFocus()
        if isinstance(w, qw.QLineEdit) and cursor_pos != -1:
            pos = min(len(w.text()), cursor_pos)
            w.setCursorPosition(pos)

        elif isinstance(w, qw.QTextEdit):
            if cursor_pos != -1:
                cur = w.textCursor()
                pos = min(len(w.toPlainText()), cursor_pos)
                cur.setPosition(pos)
                w.setTextCursor(cur)

    def _save_changes(self):
        if self._loading_editor:
            return
        if not self._current_model:
            return
        item = self.tree.currentItem()
        if item is None:
            return
        data = item.data(0, self.ROLE)
        if not data:
            return

        res = self._get_new_data()
        if not res:
            return
        inter_name, new_data = res
        inter_name = (inter_name or "").strip()
        if not inter_name:
            return

        w = self.focusWidget()

        cursor_pos = -1
        if isinstance(w, qw.QLineEdit):
            cursor_pos = w.cursorPosition()
        elif isinstance(w, qw.QTextEdit):
            cursor_pos = w.textCursor().position()

        if data[0] == "category":
            old_cat_name = data[1]
            cats = self._working_plot_data[self._current_model]

            old_cat_name = data[1]

            model_dict = self._working_plot_data[self._current_model]

            # Preserve plots + metadata order
            replace_key_preserve_order(model_dict, old_cat_name, inter_name, new_data)

            self._refresh_tree()
            self._select_cat(inter_name)
            self._restore_cursor_pos(w, cursor_pos)

            return

        old_cat_name = data[1]
        old_plot_name = data[2]
        plots_dict = self._working_plot_data[self._current_model][old_cat_name]["plots"]

        # always update the existing plot's data under its current key
        plots_dict[old_plot_name] = new_data

        # update displayed text live (checkbox_name)
        display = (new_data or {}).get("checkbox_name") or old_plot_name
        if item.text(0) != display:
            item.setText(0, display)

        if inter_name == old_plot_name:
            plots_dict[old_plot_name] = new_data

            display = (new_data or {}).get("checkbox_name") or old_plot_name
            if item.text(0) != display:
                item.setText(0, display)
            return

        replace_key_preserve_order(plots_dict, old_plot_name, inter_name, new_data)
        self._refresh_tree()
        self._select_plot(old_cat_name, inter_name)
        self._restore_cursor_pos(w, cursor_pos)

    def _on_add_cat(self):
        self._working_plot_data[self._current_model]["new_category"] = {
            "name": "New Category",
            "tooltip": None,
            "plots": {}
        }
        self._refresh_tree()
        self._select_cat("new_category")

    def _on_dup_plot_clicked(self) -> None:
        item = self.tree.currentItem()
        if not item:
            return

        payload = item.data(0, self.ROLE)
        if not payload or payload[0] != "plot":
            return

        _, src_cat, src_plot = payload
        target_cat = self.dup_plot_dropdown.currentData()
        if not target_cat:
            return

        model = self._current_model
        model_dict = self._working_plot_data.get(model)
        if not model_dict:
            return

        src_plots = model_dict[src_cat]["plots"]
        if src_plot not in src_plots:
            return

        new_plot = copy.deepcopy(src_plots[src_plot])

        base = src_plot
        plots_in_target = model_dict[target_cat]["plots"]

        if base not in plots_in_target:
            new_key = base
        else:
            i = 2
            while f"{base}_{i}" in plots_in_target:
                i += 1
            new_key = f"{base}_{i}"

        if "checkbox_name" in new_plot:
            new_plot["checkbox_name"] = f'{new_plot["checkbox_name"]}'

        plots_in_target[new_key] = new_plot

        self._refresh_tree()
        self._select_plot(target_cat, new_key)

    def _refresh_dup_targets(self) -> None:
        self.dup_plot_dropdown.blockSignals(True)
        self.dup_plot_dropdown.clear()

        # No model or no data → disable
        if not self._current_model:
            self.dup_plot_dropdown.setEnabled(False)
            self.dup_plot_btn.setEnabled(False)
            self.dup_plot_dropdown.blockSignals(False)
            return

        item = self.tree.currentItem()
        if not item:
            self.dup_plot_dropdown.setEnabled(False)
            self.dup_plot_btn.setEnabled(False)
            self.dup_plot_dropdown.blockSignals(False)
            return

        payload = item.data(0, self.ROLE)
        if not payload or payload[0] != "plot":
            # Only meaningful for plots
            self.dup_plot_dropdown.setEnabled(False)
            self.dup_plot_btn.setEnabled(False)
            self.dup_plot_dropdown.blockSignals(False)
            return

        _, src_cat, _ = payload

        categories = self._working_plot_data.get(self._current_model, {})
        for cat_key, cat in categories.items():
            display = cat.get("name") or cat_key
            self.dup_plot_dropdown.addItem(display, cat_key)

        enabled = self.dup_plot_dropdown.count() > 0
        self.dup_plot_dropdown.setEnabled(enabled)
        self.dup_plot_btn.setEnabled(enabled)

        self.dup_plot_dropdown.blockSignals(False)

    def _on_add_plot(self):
        current_sel = self.tree.currentItem()
        if current_sel is None:
            self.window.status.show("Please first select/create a category which the plot will belong to.", 4000)
            return
        data = current_sel.data(0, self.ROLE)
        if data[0] == "category":
            cat_name = data[1]
        else:
            parent_item = current_sel.parent()
            if parent_item is None:
                self.window.status.show("Error: Selected plot doesn't belong to a category? Is this even possible?", 4000)
                return
            par_data = parent_item.data(0, self.ROLE)
            cat_name = par_data[1]
        self._working_plot_data[self._current_model][cat_name]["plots"]["new_plot"] = {
            "checkbox_name": "New Plot",
            "labels": [""],
        }
        self._refresh_tree()
        self._select_plot(cat_name, "new_plot")

    def _select_cat(self, category_name):
        for i in range(self.tree.topLevelItemCount()):
            category_item = self.tree.topLevelItem(i)
            data = category_item.data(0, self.ROLE)

            if data[1] != category_name:
                continue

            self.tree.setCurrentItem(category_item)

    def _select_plot(self, category_name, plot_name):
        for i in range(self.tree.topLevelItemCount()):
            category_item = self.tree.topLevelItem(i)
            data = category_item.data(0, self.ROLE)

            if data[1] != category_name:
                continue

            self.tree.expandItem(category_item)

            for j in range(category_item.childCount()):
                plot_item = category_item.child(j)
                plot_payload = plot_item.data(0, self.ROLE)

                if plot_payload[2] == plot_name:
                    self.tree.setCurrentItem(plot_item)
                    return

    def _on_del_clicked(self):
        data = self.tree.currentItem().data(0, self.ROLE)
        if data[0] == "plot":
            cat_name, plot_name = data[1], data[2]
            del self._working_plot_data[self._current_model][cat_name]["plots"][plot_name]
        if data[0] == "category":
            cat_name = data[1]
            del self._working_plot_data[self._current_model][cat_name]
        self._refresh_tree()

    # plot-type specific stuff
    # To add or edit a plot type, it should (usually) only ever be necessary to 
    #   1. Create (or edit) the _build_<plot_type>_panel method. Don't forget to maintain self.field_widgets
    #   2. Create (or edit) the _load_<plot_type>_info method.
    #   3. Create (or edit) the _get_new_<plot_type>_data method.
    #   4. If a new plot type, add relevant info to the self.plot_dir dictionary
    # As long as widgets are of an already recognized type, everything else should be handled automatically!
    def _build_cat_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = qw.QVBoxLayout(w)

        form_widget = qw.QWidget()
        form_layout = HelpFormLayout(form_widget)

        self.cat_title = qw.QLineEdit()
        self.x_label = qw.QLineEdit()
        self.y_label = qw.QLineEdit()
        self.tooltip = qw.QTextEdit()

        
        checkbox_grid = qw.QWidget()
        checkbox_grid_layout = qw.QHBoxLayout(checkbox_grid)
        self.is_3d = qw.QCheckBox("3D Plot")
        self.axis_visible = qw.QCheckBox("Show Axis")
        self.grid_visible = qw.QCheckBox("Show Grid")
        self.ticks_visible = qw.QCheckBox("Show Ticks")
        self.frame_visible = qw.QCheckBox("Show Frame")

        checkbox_grid_layout.addWidget(self.axis_visible)
        checkbox_grid_layout.addWidget(self.grid_visible)
        checkbox_grid_layout.addWidget(self.ticks_visible)
        checkbox_grid_layout.addWidget(self.frame_visible)
        checkbox_grid_layout.addWidget(self.is_3d)

        self.hint = qw.QLabel(
            "Hint: The only necessary field here is the title. \n"
       "All others can be left blank. x-axis defaults to 'Time [s]'. \n"
            "The other fields default to nothing."
        )
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("opacity: 0.85;")

        form_layout.addRow("Title: ", self.cat_title)
        form_layout.addRow("x-Axis Label: ", self.x_label)
        form_layout.addRow("y-Axis Label: ", self.y_label)
        form_layout.addRow("Options: ", checkbox_grid)
        form_layout.addRow("Tooltip Info: ", self.tooltip)

        layout.addWidget(form_widget, stretch= 1)
        layout.addWidget(self.hint, stretch= 0)

        self.field_widgets += [
            self.cat_title, self.x_label, self.y_label, self.tooltip,
            self.is_3d, self.axis_visible, self.grid_visible, self.ticks_visible,
            self.frame_visible, 
        ]

        return w

    def _load_category_info(self, cat_key):
        self.form.setRowVisible(self.toggled_check, False)
        self.form.setRowVisible(self.plot_type_combo, False)

        name = self._working_plot_data[self._current_model][cat_key].get("name", "")
        title = self._working_plot_data[self._current_model][cat_key].get("title", "")
        x_label = self._working_plot_data[self._current_model][cat_key].get("x_label", "")
        y_label = self._working_plot_data[self._current_model][cat_key].get("y_label", "")
        is_3d = self._working_plot_data[self._current_model][cat_key].get("projection", "")
        axis_vis = self._working_plot_data[self._current_model][cat_key].get("axis_visible", True)
        grid_vis = self._working_plot_data[self._current_model][cat_key].get("grid_visible", True)
        ticks_vis = self._working_plot_data[self._current_model][cat_key].get("ticks_visible", True)
        frame_vis = self._working_plot_data[self._current_model][cat_key].get("frame_visible", True)

        tooltip = self._working_plot_data[self._current_model][cat_key].get("tooltip", "")

        self._loading_editor = True
        self._block_editor_signals(True)
        try:
            self.name_edit.setText(name)
            self.lbl_internal_name.setText(cat_key)
            self.cat_title.setText(title)
            self.x_label.setText(x_label)
            self.y_label.setText(y_label)
            self.is_3d.setChecked(True if is_3d == "3d" else False)
            self.axis_visible.setChecked(axis_vis)
            self.grid_visible.setChecked(grid_vis)
            self.ticks_visible.setChecked(ticks_vis)
            self.frame_visible.setChecked(frame_vis)
            self.tooltip.setText(tooltip)
            self.type_stack.setCurrentIndex(0)
        finally:
            self._block_editor_signals(False)
            self._loading_editor = False

    def _get_new_cat_data(self, new_data):
        new_data["name"] = self.name_edit.text()
        if self.cat_title.text():
            new_data["title"] = self.cat_title.text()
        if self.x_label.text():
            new_data["x_label"] = self.x_label.text()
        if self.y_label.text():
            new_data["y_label"] = self.y_label.text()
        new_data["projection"] = "3d" if self.is_3d.isChecked() else "2d"
        new_data["axis_visible"] = self.axis_visible.isChecked()
        new_data["grid_visible"] = self.grid_visible.isChecked()
        new_data["ticks_visible"] = self.ticks_visible.isChecked()
        new_data["frame_visible"] = self.frame_visible.isChecked()
        if self.tooltip.toPlainText():
            new_data["tooltip"] = self.tooltip.toPlainText()

    def _build_curve_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.curve_traj_key = qw.QLineEdit()
        self.curve_traj_key_x = qw.QLineEdit()

        self.curve_linestyle = qw.QComboBox()
        self.curve_linestyle.addItem("Solid", "solid")
        self.curve_linestyle.addItem("Dashed", "dashed")
        self.curve_linestyle.addItem("Dotted", "dotted")
        self.curve_linewidth = qw.QDoubleSpinBox()
        self.curve_linewidth.setRange(0.5, 3.0)
        self.curve_linewidth.setValue(1.5)
        self.curve_linewidth.setDecimals(1)
        self.curve_linewidth.setSingleStep(0.1)
        self.curve_linewidth.setProperty("default_value", 1.5)

        self.curve_marker_and_color = LabelColorRow(indep= True, extra_picker= True)
        self.curve_markersize = qw.QDoubleSpinBox()
        self.curve_label_template = qw.QCheckBox("Use label template")
        label_template_helptext = "If this is checked, you only need to fill in a single label for all of your curves, in the form 'Quantity {i}'. The {i} here will be replaced with a number based on the number of curves in the vector trajectory. Colors will also be chosen automatically, but you can create additional series and fill in just the colors to manually specificy colors for an initial segment of curves. Useful if the number of quantities in your vector trajectory is variable."
        self.curve_markersize.setRange(1.0, 10.0)
        self.curve_markersize.setSingleStep(1.0)
        self.curve_markersize.setValue(6.0)
        self.curve_markersize.setDecimals(1)
        self.curve_markersize.setProperty("default_value", 6.0)

        # self.curve_series_editor = LabelColorListEditor()
        self.curve_series_editor = DynamicRowStack[LabelColor](
            row_widget= LabelColorRow,
            make_row_kwargs= label_color_make_kwargs,
            get_row_data= label_color_get_data,
            connect_row_signals= label_color_connect_signals,
            add_button_text= "+ Add series",
            default_item= ("", "")
        )
        # autosave wiring is done in _wire_autosave_signals

        layout.addRow("Trajectory Key*:", self.curve_traj_key, help_text= "The key for the stuff you're plotting")
        layout.addRow("Trajectory Key for x-Axis:", self.curve_traj_key_x, help_text= "By default, will use your 't' array for the x-axis, but you can deviate from that using this field.")
        layout.addRow("Line Style:", self.curve_linestyle)
        layout.addRow("Line Width:", self.curve_linewidth)
        layout.addRow("Marker Type/Color/Edgecolor:", self.curve_marker_and_color)
        layout.addRow("Marker Size:", self.curve_markersize)
        layout.addRow("", self.curve_label_template, help_text= label_template_helptext)
        layout.addRow("Curves (label + color):", self.curve_series_editor)
        # layout.addRow("", self.curve_tip1)

        self.field_widgets += [
            self.curve_traj_key, self.curve_traj_key_x, self.curve_linestyle, self.curve_marker_and_color.label_edit,
            self.curve_marker_and_color.color_edit, self.curve_marker_and_color.color_edit2, self.curve_linewidth,

            self.curve_markersize, self.curve_series_editor, self.curve_label_template
        ]

        return w

    def _load_curve_info(self, plot):
        self.curve_traj_key.setText(plot.get("traj_key", "") or "")
        self.curve_traj_key_x.setText(plot.get("traj_key_x", "") or "")
        val = (plot.get("linestyle") or "solid").strip().lower()
        idx = self.curve_linestyle.findData(val)
        if idx >= 0:
            self.curve_linestyle.setCurrentIndex(idx)
        else:
            self.curve_linestyle.setCurrentIndex(self.curve_linestyle.findData("solid"))
        self.curve_linewidth.setValue(plot.get("linewidth", 1.5))
        self.curve_markersize.setValue(plot.get("markersize", 6.0))
        self.curve_marker_and_color.label_edit.setText(plot.get("marker", "") or "")
        self.curve_marker_and_color.color_edit.set_hex(plot.get("markerfacecolor", "") or "")
        self.curve_marker_and_color.color_edit2.set_hex(plot.get("markeredgecolor", "") or "")
        template_mode = True if plot.get("label_template") else False
        self.curve_label_template.setChecked(template_mode)
        colors = plot.get("colors", []) or []
        if template_mode:
            labels = [""]*len(colors)
            labels[0] = plot.get("label_template")
        else:
            labels = plot.get("labels", []) or []
        colors = plot.get("colors", []) or []
        pairs = list(zip(labels, colors))
        self.curve_series_editor.set_items(pairs)

    def _get_new_curve_data(self, new_data):
        new_data["linestyle"] = (self.curve_linestyle.currentData() or "solid")
        if self.curve_marker_and_color.label_edit.text().strip():
            new_data["marker"] = (self.curve_marker_and_color.label_edit.text().strip() or None)
            new_data["markerfacecolor"] = (self.curve_marker_and_color.color_edit.text().strip() or None)
            new_data["markeredgecolor"] = (self.curve_marker_and_color.color_edit2.text().strip() or None)
        pairs = self.curve_series_editor.get_items()
        try:
            labels, colors = zip(*pairs) # unzipping magic
        except ValueError:
            labels, colors = [], []
           
        new_data["linewidth"] = self.curve_linewidth.value()
        new_data["markersize"] = self.curve_markersize.value()
        if self.curve_label_template.isChecked():
            new_data["label_template"] = labels[0]
            if new_data.get("labels"):
                del new_data["labels"]
        else:
            new_data["labels"] = labels
        new_data["colors"] = colors
        new_data["traj_key"] = self.curve_traj_key.text()
        if self.curve_traj_key_x.text().strip():
            new_data["traj_key_x"] = self.curve_traj_key_x.text()
        if self.name_edit.text(): new_data["toggled"] = self.toggled_check.isChecked()

    def _build_heatmap_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        overall_layout = qw.QVBoxLayout(w)
        form_widget = qw.QWidget()
        form_layout = HelpFormLayout(form_widget)

        self.heatmap_traj_key = qw.QLineEdit()
        self.heatmap_type = qw.QComboBox()
        self.heatmap_type.addItem("Discrete", "discrete")
        self.heatmap_type.addItem("Continuous", "continuous")

        self.heatmap_options = qw.QWidget()
        self.heatmap_options_lay = qw.QHBoxLayout(self.heatmap_options)
        
        self.heatmap_colorbar = qw.QCheckBox("Display Color Bar")
        self.heatmap_colorbar_labels = qw.QCheckBox("Color Bar Labels")

        self.heatmap_options_lay.addWidget(self.heatmap_colorbar)
        self.heatmap_options_lay.addWidget(self.heatmap_colorbar_labels)
        self.heatmap_aspect = qw.QComboBox()
        self.heatmap_aspect.addItem("Equal", "equal")
        self.heatmap_aspect.addItem("Auto", "auto")
        interp_options = [
            'none', 'auto', 'nearest', 'bilinear',
            'bicubic', 'spline16', 'spline36', 'hanning', 'hamming', 'hermite',
            'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel', 'mitchell',
            'sinc', 'lanczos', 'blackman'
        ]
        self.heatmap_interp = qw.QComboBox()
        self.heatmap_interp.addItems(interp_options)
        self.heatmap_origin = qw.QComboBox()
        self.heatmap_origin.addItem("Upper", "upper")
        self.heatmap_origin.addItem("Lower", "lower")

        disc_widget = qw.QWidget()
        cts_widget = qw.QWidget()
        disc_layout = HelpFormLayout(disc_widget)

        self.heatmap_disc_cell_coloring = ValueColorLabelRow(indep= True)
        self.heatmap_disc_cell_coloring.value_edit.setPlaceholderText("Values")
        self.heatmap_disc_cell_coloring.color_edit.setPlaceholderText("Associated Colors")
        self.heatmap_disc_cell_coloring.label_edit.setPlaceholderText("Labels")

        self.heatmap_marker_editor = DynamicRowStack[OverlayMarkerLabel](
            row_widget= OverlayMarkerRow,
            make_row_kwargs= overlay_marker_make_kwargs,
            get_row_data= overlay_marker_get_data,
            connect_row_signals= overlay_marker_connect_signals,
            add_button_text= "+ Add marker",
            default_item= ("", "", "", "", "", "")
        )
        disc_layout.addRow("Cell Coloring: ", self.heatmap_disc_cell_coloring)
        disc_layout.addRow("Cell Markers: ", self.heatmap_marker_editor)


        self.heatmap_type_stack = qw.QStackedWidget()
        self.heatmap_type_stack.addWidget(disc_widget)
        self.heatmap_type_stack.addWidget(cts_widget)

        self.heatmap_type.currentIndexChanged.connect(self._on_heatmap_type_changed)

        form_layout.addRow("Trajectory Key: ", self.heatmap_traj_key)
        form_layout.addRow("", self.heatmap_options)
        form_layout.addRow("Aspect Ratio: ", self.heatmap_aspect)
        form_layout.addRow("Interpolation: ", self.heatmap_interp)
        form_layout.addRow("Origin: ", self.heatmap_origin)
        form_layout.addRow("Type: ", self.heatmap_type)

        overall_layout.addWidget(form_widget, 1)
        overall_layout.addWidget(self.heatmap_type_stack, 1)

        self.field_widgets += [
            self.heatmap_traj_key, self.heatmap_type, self.heatmap_colorbar,
            self.heatmap_colorbar_labels, self.heatmap_aspect, self.heatmap_interp, self.heatmap_origin,
            self.heatmap_disc_cell_coloring.value_edit, self.heatmap_disc_cell_coloring.color_edit, 
            self.heatmap_disc_cell_coloring.label_edit, self.heatmap_marker_editor,
        ]

        return w

    def _on_heatmap_type_changed(self, idx: int) -> None:
        # stack_idx = {0: 1, 1: 2}.get(idx, 1)
        self.heatmap_type_stack.setCurrentIndex(idx)
        self._save_changes()

    def _load_heatmap_info(self, plot):
        values = plot.get("values", "") or ""
        colors = plot.get("colors", "") or ""
        labels = plot.get("labels", "") or ""

        self.heatmap_traj_key.setText(plot.get("traj_key", "") or "")
        self.heatmap_colorbar.setChecked(plot.get("colorbar", False))

        val = plot.get("discrete", False)
        if val:
            self.heatmap_type.setCurrentIndex(0)
        else:
            self.heatmap_type.setCurrentIndex(1)

        val = plot.get("aspect", "equal")
        idx = self.heatmap_aspect.findText(val)
        if idx >= 0:
            self.heatmap_aspect.setCurrentIndex(idx)
        else:
            self.heatmap_aspect.setCurrentIndex(self.heatmap_aspect.findData("equal"))

        val = plot.get("interpolation", "nearest")
        idx = self.heatmap_interp.findText(val)
        if idx >= 0:
            self.heatmap_interp.setCurrentIndex(idx)
        else:
            self.heatmap_interp.setCurrentIndex(self.heatmap_interp.findText("nearest"))

        val = plot.get("origin", "lower")
        idx = self.heatmap_origin.findData(val)
        if idx >= 0:
            self.heatmap_origin.setCurrentIndex(idx)
        else:
            self.heatmap_origin.setCurrentIndex(self.heatmap_origin.findData("lower"))

        self.heatmap_disc_cell_coloring.value_edit.setText(values)
        self.heatmap_disc_cell_coloring.color_edit.setText(colors)
        self.heatmap_disc_cell_coloring.label_edit.setText(labels)

        overlay = plot.get("overlay_markers", {}) or {}
        if overlay:
            codes = overlay.get("codes", []) or []
            sizes = overlay.get("sizes", []) or []
            labels = overlay.get("labels", []) or []
            markers = overlay.get("markers", []) or []
            colors = overlay.get("colors", []) or []
            edgecolors = overlay.get("edgecolors", []) or []

            sex = list(zip(codes, sizes, labels, markers, colors, edgecolors))
            self.heatmap_marker_editor.set_items(sex)

    def _get_new_heatmap_data(self, new_data):
        new_data["traj_key"] = self.heatmap_traj_key.text()
        new_data["discrete"] = True if self.heatmap_type.currentText() == "Discrete" else False
        new_data["colorbar"] = self.heatmap_colorbar.isChecked()

        if self.heatmap_disc_cell_coloring.value_edit.text():
            new_data["values"] = self.heatmap_disc_cell_coloring.value_edit.text()
        if self.heatmap_disc_cell_coloring.color_edit.text():
            new_data["colors"] = self.heatmap_disc_cell_coloring.color_edit.text()
        if self.heatmap_disc_cell_coloring.label_edit.text():
            new_data["labels"] = self.heatmap_disc_cell_coloring.label_edit.text()

        pairs = self.heatmap_marker_editor.get_items()
        try:
            codes, sizes, labels, markers, colors, edgecolors = zip(*pairs) # unzipping magic
        except ValueError:
            codes, sizes, labels, markers, colors, edgecolors = [], [], [], [], [], []

        if len(codes) > 0:
            new_data["overlay_markers"] = {"codes": codes}
            if sizes: new_data["overlay_markers"]["sizes"] = sizes
            if labels: new_data["overlay_markers"]["labels"] = labels
            if markers: new_data["overlay_markers"]["markers"] = markers
            if colors: new_data["overlay_markers"]["colors"] = colors
            if edgecolors: new_data["overlay_markers"]["edgecolors"] = colors

    def _build_hist_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.hist_data = qw.QLineEdit()
        self.hist_bins = qw.QLineEdit()
        self.hist_weights = qw.QLineEdit()

        self.hist_density = qw.QCheckBox("Density (normalize)")
        self.hist_label_color_edgecolor = LabelColorRow(indep= True, extra_picker= True)
        label_template_helptext = "If this is checked, you only need to fill in a single label for all of your curves, in the form 'Quantity {i}'. The {i} here will be replaced with a number based on the number of curves in the vector trajectory. Colors will also be chosen automatically, but you can create additional series and fill in just the colors to manually specificy colors for an initial segment of curves. Useful if the number of quantities in your vector trajectory is variable."
        self.hist_label_template = qw.QCheckBox("Use label template")
        self.hist_series_editor = DynamicRowStack[LabelColorColor](
            row_widget= LabelColorRow,
            make_row_kwargs= label_color_color_make_kwargs,
            get_row_data= label_color_color_get_data,
            connect_row_signals= label_color_color_connect_signals,
            add_button_text= "+ Add series",
            default_item= ("", "", "")
        )

        self.hist_type = qw.QComboBox()
        self.hist_type.addItems(["bar", "barstacked", "step", "stepfilled"])

        self.hist_align = qw.QComboBox()
        self.hist_align.addItems(["left", "mid", "right"])
        self.hist_cmap = qw.QComboBox()
        self.hist_cmap.addItem("None")
        self.hist_cmap.addItems(list(colormaps))

        self.hist_tip = qw.QLabel("Tips: Data key is the only required field.")
        self.hist_tip2 = qw.QLabel("    If your bins are very thin, try setting edge color to 'face' to have outlines match the inside color.")

        layout.addRow("Data Key*:", self.hist_data)
        layout.addRow("Bins Key:", self.hist_bins)
        layout.addRow("Weights Key:", self.hist_weights)
        layout.addRow("", self.hist_density)
        layout.addRow("Type:", self.hist_type)
        layout.addRow("Alignment:", self.hist_align)
        # layout.addRow("Label/Color/Edgecolor:", self.hist_label_color_edgecolor)
        layout.addRow("", self.hist_label_template, help_text= label_template_helptext) 
        layout.addRow("Label/Color/Edgecolor:", self.hist_series_editor)
        layout.addRow("Gradient:", self.hist_cmap)
        layout.addRow("", self.hist_tip)
        layout.addRow("", self.hist_tip2)

        self.field_widgets += [
            self.hist_data, self.hist_bins, self.hist_weights, self.hist_density,
            self.hist_label_color_edgecolor.label_edit, self.hist_label_color_edgecolor.color_edit, self.hist_label_color_edgecolor.color_edit2,
            self.hist_type, self.hist_align, self.hist_cmap, self.hist_label_template, self.hist_series_editor
        ]

        return w

    def _load_hist_info(self, plot):
        self.hist_data.setText(plot.get("dist", "") or "")
        self.hist_bins.setText(plot.get("bins", ""))  # your row data type (tuple, dict, dataclass, etc.)) or "")
        self.hist_weights.setText(plot.get("weights", "") or "")
        self.hist_density.setChecked(plot.get("density", False) or False)
        val = (plot.get("histtype") or "bar").strip().lower()
        idx = self.hist_type.findText(val)
        if idx >= 0:
            self.hist_type.setCurrentIndex(idx)
        else:
            self.hist_type.setCurrentIndex(self.hist_type.findText("bar"))

        val = (plot.get("align") or "mid").strip().lower()
        idx = self.hist_align.findText(val)
        if idx >= 0:
            self.hist_align.setCurrentIndex(idx)
        else:
            self.hist_align.setCurrentIndex(self.hist_align.findText("bar"))

        val = (plot.get("gradient") or "None").strip()
        idx = self.hist_cmap.findText(val)
        if idx >= 0:
            self.hist_cmap.setCurrentIndex(idx)
        else:
            self.hist_cmap.setCurrentIndex(self.hist_cmap.findText("bar"))

        template_mode = True if plot.get("label_template") else False
        self.hist_label_template.setChecked(template_mode)

        old_label = plot.get("label")
        old_color = plot.get("color")
        old_edgecolor = plot.get("edgecolor")

        if old_color:
            colors = [old_color]
        else:
            colors = plot.get("colors", [])

        if old_edgecolor:
            edgecolors = [old_edgecolor]
        else:
            edgecolors = plot.get("edgecolors", [""]*len(colors))

        if template_mode:
            labels = [""]*len(colors)
            labels[0] = plot.get("label_template")
        elif old_label:
            labels = [old_label]
        else:
            labels = plot.get("labels", []) or []


        triples = list(zip(labels, colors, edgecolors))
        self.hist_series_editor.set_items(triples)

        # self.hist_label_color_edgecolor.label_edit.setText(plot.get("label", "") or "")
        # self.hist_label_color_edgecolor.color_edit.set_hex(plot.get("color", "") or "")
        # self.hist_label_color_edgecolor.color_edit2.set_hex(plot.get("edgecolor", "") or "")

    def _get_new_hist_data(self, new_data):
        new_data["dist"] = self.hist_data.text()
        try:
            bins = int(self.hist_bins.text())
        except ValueError:
            bins = self.hist_bins.text()
        if bins:
            new_data["bins"] = bins
        if self.hist_weights.text().strip():
            new_data["weights"] = self.hist_weights.text().strip()
        new_data["density"] = bool(self.hist_density.isChecked())

        triplets = self.hist_series_editor.get_items()
        try:
            labels, colors, edgecolors = zip(*triplets) # unzipping magic
        except ValueError:
            labels, colors, edgecolors = [], [], []

        gradient = self.hist_cmap.currentText()
        new_data["gradient"] = gradient

        if self.hist_label_template.isChecked():
            new_data["label_template"] = labels[0]
            if new_data.get("labels"):
                del new_data["labels"]
        else:
            new_data["labels"] = labels

        new_data["colors"] = colors
        new_data["edgecolors"] = edgecolors

        if self.hist_label_color_edgecolor.label_edit.text().strip():
            new_data["label"] = self.hist_label_color_edgecolor.label_edit.text().strip()
        # if self.hist_label_color_edgecolor.color_edit.text().strip():
        #     new_data["color"] = self.hist_label_color_edgecolor.color_edit.text().strip()
        # if self.hist_label_color_edgecolor.color_edit2.text().strip():
        #     new_data["edgecolor"] = self.hist_label_color_edgecolor.color_edit2.text().strip()
        histtype = self.hist_type.currentText()
        new_data["histtype"] = histtype
        align = self.hist_align.currentText()
        new_data["align"] = align

    def _build_scatter_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.scatter_traj_key_x = qw.QLineEdit()
        self.scatter_traj_key_y = qw.QLineEdit()
        self.scatter_label_color = LabelColorRow(indep= True)
        self.scatter_marker = qw.QLineEdit()

        layout.addRow("x-Axis Key*:", self.scatter_traj_key_x)
        layout.addRow("y-Axis Key*:", self.scatter_traj_key_y)
        layout.addRow("Label/Color:", self.scatter_label_color)
        layout.addRow("Marker:", self.scatter_marker)

        self.field_widgets += [
            self.scatter_traj_key_x, self.scatter_traj_key_y, self.scatter_label_color.label_edit,
            self.scatter_label_color.color_edit, self.scatter_marker
        ]

        return w

    def _load_scatter_info(self, plot):
        self.scatter_traj_key_x.setText(plot.get("traj_key_x", "") or "")
        self.scatter_traj_key_y.setText(plot.get("traj_key_y", "") or "")
        try:
            label = plot.get("labels", "")[0]
        except Exception:
            label = ""
        self.scatter_label_color.label_edit.setText(label)
        self.scatter_label_color.color_edit.set_hex(plot.get("color", "") or "")
        self.scatter_marker.setText(plot.get("marker", "") or "")

    def _get_new_scatter_data(self, new_data):
        new_data["traj_key_x"] = self.scatter_traj_key_x.text()
        new_data["traj_key_y"] = self.scatter_traj_key_y.text()
        new_data["labels"] = [self.scatter_label_color.label_edit.text()]
        new_data["color"] = self.scatter_label_color.color_edit.text()
        new_data["marker"] = self.scatter_marker.text()

    def _build_pie_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.pie_data = qw.QLineEdit()
        self.pie_values = qw.QLineEdit()
        self.pie_colors = qw.QLineEdit()
        self.pie_labels = qw.QLineEdit()

        layout.addRow("Data Key: ", self.pie_data)
        layout.addRow("Color Mapping Key: ", self.pie_colors)
        layout.addRow("Label Mapping Key: ", self.pie_labels)

        self.field_widgets += [
            self.pie_data, self.pie_colors, self.pie_labels
        ]

        return w

    def _load_pie_info(self, plot):
        self.pie_data.setText(plot.get("traj_key", "") or "")
        self.pie_colors.setText(plot.get("color_map", "") or "")
        self.pie_labels.setText(plot.get("label_map", "") or "")

    def _get_new_pie_data(self, new_data):
        new_data["traj_key"] = self.pie_data.text().strip()

        new_data["color_map"] = self.pie_colors.text()
        new_data["label_map"] = self.pie_labels.text()

    def _build_field_panel(self) -> qw.QWidget():
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.quiver_traj_key_U = qw.QLineEdit()
        self.quiver_traj_key_V = qw.QLineEdit()
        self.quiver_traj_key_W = qw.QLineEdit()
        self.quiver_traj_key_X = qw.QLineEdit()
        self.quiver_traj_key_Y = qw.QLineEdit()
        self.quiver_traj_key_Z = qw.QLineEdit()
        self.quiver_traj_key_C = qw.QLineEdit()

        self.quiver_cmap = qw.QComboBox()
        self.quiver_cmap.addItem("None")
        self.quiver_cmap.addItems(list(colormaps))

        self.quiver_display_cbar = qw.QCheckBox("Display Colorbar: ")

        layout.addRow("U Key*: ", self.quiver_traj_key_U, help_text= "X-coord vector directions")
        layout.addRow("V Key*: ", self.quiver_traj_key_V, help_text= "Y-coord vector directions")
        layout.addRow("W Key*: ", self.quiver_traj_key_W, help_text= "Z-coord vector directions (only required if your field is 3D)")
        layout.addRow("X Key: ", self.quiver_traj_key_X, help_text= "X-coord vector locations")
        layout.addRow("Y Key: ", self.quiver_traj_key_Y, help_text= "Y-coord vector locations")
        layout.addRow("Z Key: ", self.quiver_traj_key_Z, help_text= "Z-coord vector locations")
        layout.addRow("Color Map: ", self.quiver_cmap, help_text= "Color map for vectors")
        layout.addRow("Color Magnitudes Key: ", self.quiver_traj_key_C, help_text= "Magnitudes for coloring. If not specified, the Euclidean norm will be used to interpret color magnitudes.")
        layout.addRow("", self.quiver_display_cbar)
        
        self.field_widgets += [
            self.quiver_traj_key_U, self.quiver_traj_key_V, self.quiver_traj_key_X,
            self.quiver_traj_key_Y, self.quiver_cmap, self.quiver_traj_key_C,
            self.quiver_display_cbar, self.quiver_traj_key_W, self.quiver_traj_key_Z
        ]
        
        return w

    def _load_field_info(self, plot):
        self.quiver_traj_key_U.setText(plot.get("traj_key_U", ""))
        self.quiver_traj_key_V.setText(plot.get("traj_key_V", ""))
        self.quiver_traj_key_W.setText(plot.get("traj_key_W", ""))

        self.quiver_traj_key_X.setText(plot.get("traj_key_X", ""))
        self.quiver_traj_key_Y.setText(plot.get("traj_key_Y", ""))
        self.quiver_traj_key_Z.setText(plot.get("traj_key_Z", ""))

        val = plot.get("cmap", "None")
        idx = self.quiver_cmap.findText(val)
        if idx >= 0:
            self.quiver_cmap.setCurrentIndex(idx)
        else:
            self.quiver_cmap.setCurrentIndex(self.quiver_cmap.findText("None"))

        self.quiver_traj_key_C.setText(plot.get("traj_key_C", ""))
        self.quiver_display_cbar.setChecked(plot.get("colorbar", False))

    def _get_new_field_data(self, new_data):
        if self.quiver_traj_key_X.text() != "" and self.quiver_traj_key_Y.text() != "":
            new_data["traj_key_X"] = self.quiver_traj_key_X.text()
            new_data["traj_key_Y"] = self.quiver_traj_key_Y.text()
            if self.quiver_traj_key_Z.text():
                new_data["traj_key_Z"] = self.quiver_traj_key_Z.text()

        new_data["traj_key_U"] = self.quiver_traj_key_U.text()
        new_data["traj_key_V"] = self.quiver_traj_key_V.text()
        new_data["traj_key_W"] = self.quiver_traj_key_W.text()

        cmap = self.quiver_cmap.currentText()
        new_data["cmap"] = cmap

        traj_key_C = self.quiver_traj_key_C.text()
        if traj_key_C:
            new_data["traj_key_C"] = traj_key_C

        new_data["colorbar"] = self.quiver_display_cbar.isChecked()

    def _build_dgraph_panel(self) -> qw.QWidget:
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.dgraph_traj_key = qw.QLineEdit()
        self.dgraph_type = qw.QCheckBox("Directed Graph")

        self.dgraph_node_size = qw.QSpinBox()
        self.dgraph_node_size.setRange(200, 600)
        self.dgraph_node_size.setValue(300)
        self.dgraph_node_size.setSingleStep(10)
        self.dgraph_node_size.setProperty("default_value", 300)

        self.dgraph_color_series_editor = DynamicRowStack[Color](
            row_widget= ColorRow,
            make_row_kwargs= just_color_make_kwargs,
            get_row_data= just_color_get_data,
            connect_row_signals= just_color_connect_signals,
            add_button_text= "+ Add color",
            default_item= ("",)
        )

        layout.addRow("Adj. Matrix Key*:", self.dgraph_traj_key, help_text= "Key for the adjacency matrix.")
        layout.addRow("", self.dgraph_type, help_text= "Check box if graph is directed to draw edges with tips, e.g. '->'")
        layout.addRow("Node size:", self.dgraph_node_size, help_text= "How big the nodes are.")
        layout.addRow("Node colors:", self.dgraph_color_series_editor, help_text= "If left blank, colors will be automatically chosen. However, you can choose the first however many colors manually (if more colors are needed, these will be generated automatically in the same way).")

        self.field_widgets += [
            self.dgraph_traj_key, self.dgraph_type, self.dgraph_node_size, self.dgraph_color_series_editor
        ]

        return w

    def _load_dgraph_info(self, plot):
        self.dgraph_traj_key.setText(plot.get("traj_key", "") or "")
        self.dgraph_type.setChecked(plot.get("directed", False))
        node_size = plot.get("node_size", 300)
        try:
            node_size = int(node_size)
        except ValueError:
            node_size = 300
        self.dgraph_node_size.setValue(node_size)
        colors = plot.get("colors", []) or []
        tups = [(color,) for color in colors]
        self.dgraph_color_series_editor.set_items(tups)

    def _get_new_dgraph_data(self, new_data):
        new_data["traj_key"] = self.dgraph_traj_key.text()
        new_data["directed"] = self.dgraph_type.isChecked()
        new_data["node_size"] = self.dgraph_node_size.value()
        tups = self.dgraph_color_series_editor.get_items()
        colors = [tup[0] for tup in tups]

        new_data["colors"] = colors

    def _build_surface_panel(self) -> qw.QWidget():
        w = qw.QWidget()
        layout = HelpFormLayout(w)

        self.surface_traj_key_x = qw.QLineEdit()
        self.surface_traj_key_y = qw.QLineEdit()
        self.surface_traj_key_z = qw.QLineEdit()

        self.surface_rcount = qw.QSpinBox()
        self.surface_rcount.setRange(10, 90)
        self.surface_rcount.setValue(50)
        self.surface_rcount.setProperty("default_value", 50)

        self.surface_cmap = qw.QComboBox()
        self.surface_cmap.addItem("None")
        self.surface_cmap.addItems(list(colormaps))

        self.surface_display_cbar = qw.QCheckBox("Display Colorbar: ")

        layout.addRow("X Key:", self.surface_traj_key_x)
        layout.addRow("Y Key:", self.surface_traj_key_y)
        layout.addRow("Z Key:", self.surface_traj_key_z)
        layout.addRow("Color map:", self.surface_cmap)
        layout.addRow("", self.surface_display_cbar)

        self.field_widgets += [
            self.surface_traj_key_x, self.surface_traj_key_y, self.surface_traj_key_z,
            self.surface_cmap, self.surface_display_cbar, self.surface_rcount,
        ]

        return w

    def _load_surface_info(self, plot):
        self.surface_traj_key_x.setText(plot.get("traj_key_X", "") or "")
        self.surface_traj_key_y.setText(plot.get("traj_key_Y", "") or "")
        self.surface_traj_key_z.setText(plot.get("traj_key_Z", "") or "")

        val = (plot.get("cmap") or "None").strip()
        idx = self.surface_cmap.findText(val)
        if idx >= 0:
            self.surface_cmap.setCurrentIndex(idx)
        else:
            self.surface_cmap.setCurrentIndex(self.surface_cmap.findText("bar"))

        self.surface_display_cbar.setChecked(plot.get("colorbar", False) or False)

    def _get_new_surface_data(self, new_data):
        new_data["traj_key_X"] = self.surface_traj_key_x.text().strip()
        new_data["traj_key_Y"] = self.surface_traj_key_y.text().strip()
        new_data["traj_key_Z"] = self.surface_traj_key_z.text().strip()

        cmap = self.surface_cmap.currentText()
        new_data["cmap"] = cmap

        new_data["colorbar"] = self.surface_display_cbar.isChecked()

    def _refresh_models(self) -> None:
        models = refresh_models(self.env)
        self.model_combo.clear()
        self.model_combo.addItems(models)

    def reload_current_model(self) -> None:
        if not self._current_model:
            return
        self._get_new_plotting_data(self._current_model)
        self._refresh_tree()
        self._refresh_dup_targets()

    def _on_model_changed(self) -> None:
        self._current_model = self.model_combo.currentText().strip() or None
        if not self._current_model:
            return
        if self._current_model not in self._original_plot_data:
            self._get_new_plotting_data(self._current_model)
        self._refresh_tree()
        self._refresh_dup_targets()

    def _get_new_plotting_data(self, model: str) -> None:
        try:
            with open(self.env.models_dir / model / "data" / "plotting_data.yml", "r") as f:
                data = yaml.safe_load(f) or {}
            self._original_plot_data[self._current_model] = copy.deepcopy(data)
            self._working_plot_data[self._current_model] = copy.deepcopy(data)
        except FileNotFoundError as e:
            self.window.status.show("plotting_data.yml not found. Creating one automatically.")
            try:
                with open(self.env.models_dir / model / "data" / "plotting_data.yml", "w") as f:
                    pass
            except FileNotFoundError as e:
                self.window.status.show(f"Error opening the data folder of {self._current_model}. Have you ran the new model creation wizard yet?")
            self._original_plot_data[self._current_model] = {}
            self._working_plot_data[self._current_model] = {}
            return
        except Exception as e:
            self.window.status.show(f"Error opening plotting_data.yml: {e}")
            self._original_plot_data[self._current_model] = {}
            self._working_plot_data[self._current_model] = {}
            return

    def _refresh_tree(self) -> None:
        selected = self._selected_payload()

        self.tree.blockSignals(True)
        self.tree.clear()

        for cat_key, cat in (self._working_plot_data[self._current_model] or {}).items():
            cat_display = (cat or {}).get("name") or cat_key
            cat_item = qw.QTreeWidgetItem([cat_display])
            cat_item.setFlags(cat_item.flags()
                              | qc.Qt.ItemFlag.ItemIsDragEnabled
                              | qc.Qt.ItemFlag.ItemIsDropEnabled)
            cat_item.setData(0, self.ROLE, ("category", cat_key))
            self.tree.addTopLevelItem(cat_item)

            plots = (cat or {}).get("plots") or {}
            for plot_key, plot_spec in plots.items():
                plot_display = (plot_spec or {}).get("checkbox_name") or plot_key
                plot_item = qw.QTreeWidgetItem([plot_display])
                plot_item.setFlags(plot_item.flags()
                                   | qc.Qt.ItemFlag.ItemIsDragEnabled)
                plot_item.setData(0, self.ROLE, ("plot", cat_key, plot_key))
                cat_item.addChild(plot_item)

            cat_item.setExpanded(True)

        self.tree.blockSignals(False)

        # restore selection if possible
        if selected:
            found = self._select_payload(selected)
            if found:
                return

        # else select first plot if exists, else first category
        if self.tree.topLevelItemCount() > 0:
            first_cat = self.tree.topLevelItem(0)
            if first_cat.childCount() > 0:
                self.tree.setCurrentItem(first_cat.child(0))
            else:
                self.tree.setCurrentItem(first_cat)
        else:
            self._clear_editor()

        self._refresh_dup_targets()

    def _on_tree_rows_moved(self, *args) -> None:
        try:
            self._rebuild_plot_data_from_tree()
        except Exception as e:
            return
        self._refresh_tree()

    def _rebuild_plot_data_from_tree(self) -> None:
        model = self._current_model
        if not model:
            return

        old_data = self._working_plot_data.get(model, {})
        new_data = {}

        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_payload = cat_item.data(0, self.ROLE)
            if not cat_payload or cat_payload[0] != "category":
                continue

            _, cat_key = cat_payload
            old_cat = old_data.get(cat_key, {})
            new_cat = {}

            # preserve category metadata
            for k in ("name", "title", "tooltip", "x_label",
                      "y_label", "projection", "axis_visible",
                      "grid_visible", "ticks_visible", "frame_visible"
                      ):
                if k in old_cat:
                    new_cat[k] = old_cat[k]

            new_cat["plots"] = {}

            for j in range(cat_item.childCount()):
                plot_item = cat_item.child(j)
                plot_payload = plot_item.data(0, self.ROLE)
                if not plot_payload or plot_payload[0] != "plot":
                    continue

                _, old_cat_key, plot_key = plot_payload
                try:
                    new_cat["plots"][plot_key] = copy.deepcopy(
                        old_data[old_cat_key]["plots"][plot_key]
                    )
                except KeyError:
                    pass

            new_data[cat_key] = new_cat

        self._working_plot_data[model] = new_data

    def _selected_payload(self):
        it = self.tree.currentItem()
        return it.data(0, self.ROLE) if it else None

    def _select_payload(self, payload) -> bool:
        """Find and select a node matching payload."""
        kind = payload[0]
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            cat_payload = cat_item.data(0, self.ROLE)
            if not cat_payload:
                continue

            if kind == "category" and cat_payload == payload:
                self.tree.setCurrentItem(cat_item)
                return True

            # search children for plot
            for j in range(cat_item.childCount()):
                ch = cat_item.child(j)
                if ch.data(0, self.ROLE) == payload:
                    self.tree.setCurrentItem(ch)
                    return True
        return False

    def _on_tree_selection_changed(self, current, previous) -> None:
        if not current:
            self._clear_editor()
            return

        payload = current.data(0, self.ROLE)
        if not payload:
            self._clear_editor()
            return

        if payload[0] == "category":
            self._clear_editor()
            self._load_category_info(payload[1])
            return

        _, cat_key, plot_key = payload
        # plot
        self.form.setRowVisible(self.toggled_check, True)
        self.form.setRowVisible(self.plot_type_combo, True)
        cat = self._working_plot_data[self._current_model].get(cat_key, {}) if self._working_plot_data[self._current_model] else {}
        plot = ((cat or {}).get("plots") or {}).get(plot_key, {}) or {}

        self._loading_editor = True
        self._block_editor_signals(True)
        try:
            self._load_plot_into_editor(plot_key, plot)
        finally:
            self._block_editor_signals(False)
            self._loading_editor = False

        self._refresh_dup_targets()

    def _clear_editor(self) -> None:
        self._loading_editor = True

        self._block_editor_signals(True)

        try:
            for widget in self.field_widgets:
                default = widget.property("default_value")
                if isinstance(widget, (qw.QLineEdit, qw.QTextEdit, ColorLineEdit)):
                    if default is not None:
                        widget.setText(default)
                    else:
                        widget.clear()
                elif isinstance(widget, qw.QCheckBox):
                    if default is not None:
                        widget.setChecked(default)
                    else:
                        widget.setChecked(False)
                elif isinstance(widget, qw.QDoubleSpinBox):
                    if default is not None:
                        widget.setValue(default)
                elif isinstance(widget, qw.QComboBox):
                    if default is not None:
                        widget.setCurrentIndex(default)
                    else:
                        try:
                            widget.setCurrentIndex(0)
                        except IndexError:
                            continue
                elif isinstance(widget, DynamicRowStack):
                    widget.set_items([])
                else:
                    print(f"We missed something: {type(widget)=}")
        finally:
            self._block_editor_signals(True)

        self.plot_type_combo.setCurrentText("Curve")
        self.type_stack.setCurrentIndex(1)

        self._block_editor_signals(False)
        self._loading_editor = False

    def _get_name_from_plot_data(self, special):
        for name in self.plot_dir:
            if self.plot_dir[name].get("yaml_name", "") == special:
                return name
        return ""

    def _load_plot_into_editor(self, plot_key: str, plot: dict) -> None:
        self.lbl_internal_name.setText(plot_key)
        self.name_edit.setText(plot.get("checkbox_name", "") or "")
        self.toggled_check.setChecked(bool(plot.get("toggled", False)))

        special = (plot.get("special") or "curve").strip().lower()
        # only curves aren't special
        if special == "curve":
            self.plot_type_combo.setCurrentText("Curve")
            self.type_stack.setCurrentIndex(1)
        else:
            name = self._get_name_from_plot_data(special)
            if name == "": return
            idx = self.plot_dir[name]["stack_idx"]
            self.plot_type_combo.setCurrentText(name)
            self.type_stack.setCurrentIndex(idx)

        plot_type = self.plot_type_combo.currentText()
        loading_func = self.plot_dir.get(plot_type, {}).get("load", None)
        if loading_func is None:
            print(f"No loading function found for {plot_type}.")
            return

        loading_func(plot)

    def _get_name_from_type_stack_idx(self, idx: int):
        """ Helper function which retrieves the name of a plot type from the type_stack index. """
        for name in self.plot_dir:
            if self.plot_dir[name]["stack_idx"] == idx:
                return name
        return ""

    def _get_new_data(self):
        item = self.tree.currentItem()
        data = item.data(0, self.ROLE)
        new_data = {}

        # for some reason the internal name label is always 1 character behind what it should
        # be here if the user was editing the name entry. the lazy fix is to just call the 
        # name update here again, which is why this is here.
        raw_text = self.name_edit.text()
        inter_name = self._update_internal_name(raw_text)

        if data[0] == "category":
            old_dict = self._working_plot_data[self._current_model][data[1]]
            self._get_new_cat_data(new_data)
            new_data["plots"] = old_dict["plots"]
            return inter_name, new_data

        data_type = self._get_name_from_type_stack_idx(self.type_stack.currentIndex())
        if data_type == "":
            return

        if self.plot_dir[data_type].get("yaml_name", ""):
            new_data["special"] = self.plot_dir[data_type]["yaml_name"]
        if self.name_edit.text(): new_data["checkbox_name"] = self.name_edit.text()
        if self.name_edit.text(): new_data["toggled"] = self.toggled_check.isChecked()

        save_func = self.plot_dir[data_type]["save"]
        save_func(new_data)
        return inter_name, new_data

    def on_apply_clicked(self) -> None:
        self._rebuild_plot_data_from_tree()
        flow_seqify(self._working_plot_data)
        flow_seqify(self._original_plot_data)

        try:
            for model, _ in self._original_plot_data.items():
                path = self.env.models_dir / model / "data" / "plotting_data.yml"
                model_dict = self._working_plot_data[model]
                atomic_write(path, model_dict)
        except Exception as e:
            self.window.status.show(f"Error writing changes: {e}", 8000)
            logger.log(logging.ERROR, "Error writing changes", exc_info= e)
        else:
            for model, _ in self._original_plot_data.items():
                new_dict = self._working_plot_data[model]
                self._original_plot_data[model] = copy.deepcopy(new_dict)
            
    def set_model(self, model_name: str):
        idx = self.model_combo.findText(model_name)
        if idx >= 0 and idx != self.model_combo.currentIndex():
            self.model_combo.setCurrentIndex(idx)
