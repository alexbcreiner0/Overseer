from __future__ import annotations
from PyQt6 import (
    QtWidgets as qw,
QtGui as qg,
    QtCore as qc
)
from typing import Any, Callable, Generic, Optional, Type, TypeVar, Any

T = TypeVar("T")
Color = tuple[str]
LabelColor = tuple[str, str]
LabelColorColor = tuple[str, str, str]
# value, size, label
# marker, color, color
OverlayMarkerLabel = tuple[Any, str, str | None, str, str | None, str | None]

class DynamicRowStack(qw.QWidget, Generic[T]):
    changed = qc.pyqtSignal()

    def __init__(
        self,
        parent=None,
        *,
        row_widget: Type[qw.QWidget],
        make_row_kwargs: Callable[[T], dict[str, Any]],
        get_row_data: Callable[[qw.QWidget], T],
        connect_row_signals: Callable[[qw.QWidget, Callable[[], None]], None],
        add_button_text: str = "+ Add row",
        default_item: Optional[T] = None,
    ):
        super().__init__(parent)
        self._row_widget = row_widget
        self._make_row_kwargs = make_row_kwargs
        self._get_row_data = get_row_data
        self._connect_row_signals = connect_row_signals
        self._default_item = default_item

        root = qw.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.rows_layout = qw.QVBoxLayout()
        self.rows_layout.setSpacing(6)
        root.addLayout(self.rows_layout)

        btn_row = qw.QHBoxLayout()
        self.add_btn = qw.QPushButton("+ Add series")
        btn_row.addWidget(self.add_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.add_btn.clicked.connect(self.add_row)
        root.addStretch(1)

    def clear_rows(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _emit_changed(self, *args) -> None:
        # Emit a single 'changed' signal for any modification, unless we're in a load
        if self.signalsBlocked():
            return
        self.changed.emit()

    def add_row(self, item: Optional[T] = None) -> None:
        if item is None:
            item = self._default_item

        kwargs = self._make_row_kwargs(item) if item is not None else {}
        row = self._row_widget(**kwargs)

        row.removed.connect(lambda _=None, r= row: self._remove_row(r))

        self._connect_row_signals(row, self._emit_changed)
        self.rows_layout.addWidget(row)
        self._emit_changed()

    def _remove_row(self, row_widget: Type[qw.QWidget]) -> None:
        row_widget.setParent(None)
        row_widget.deleteLater()
        self._emit_changed()

    def set_items(self, items: list[T]) -> None:
        self.blockSignals(True)
        try:
            self.clear_rows()
            if not items:
                self.add_row(self._default_item)
            else:
                for item in items:
                    self.add_row(item)
        finally:
            self.blockSignals(False)
        self._emit_changed()

    def get_items(self) -> list[T]:
        items: list[T] = []
        for i in range(self.rows_layout.count()):
            w = self.rows_layout.itemAt(i).widget()
            if w is None:
                continue
            items.append(self._get_row_data(w))
        return items

def label_color_make_kwargs(item: LabelColor) -> dict[str, Any]:
    if not isinstance(item, tuple):
        return {"label": "", "color": ""}
    else:
        label, color = item
        return {"label": label, "color": color}

def just_color_make_kwargs(item: Color) -> dict[str, Any]:
    if not isinstance(item, tuple):
        return {"color": ""}
    else:
        color, = item
        return {"color": color}

def label_color_color_make_kwargs(item: LabelColorColor) -> dict[str, Any]:
    if not isinstance(item, tuple):
        return {"label": "", "color": "", "color2": None, "extra_picker": True}
    else:
        label, color, color2 = item
        return {"label": label, "color": color, "color2": color2, "extra_picker": True}

def overlay_marker_make_kwargs(item: OverlayMarkerLabel) -> dict[str, Any]:
    if not isinstance(item, tuple):
        return {
            "value": "", "size": "", "label": "",
            "marker": "", "color": "", "edgecolor": "",
        }
    else:
        value, size, label, marker, color, edge_color = item
        return {
            "value": value, "size": size, "label": label,
            "marker": marker, "color": color, "edgecolor": edge_color,
        }

# this probably shouldn't be generic
def just_color_get_data(row: qw.QWidget) -> Color:
    return row.get_color()

def label_color_get_data(row: qw.QWidget) -> LabelColor:
    return row.get_pair()

def label_color_color_get_data(row: qw.QWidget) -> LabelColorColor:
    return row.get_triple()

def overlay_marker_get_data(row: qw.QWidget) -> OverlayMarkerLabel:
    return row.get_data()

def just_color_connect_signals(row: qw.QWidget, changed_cb: Callable[[], None]) -> None:
    row.color_edit.textChanged.connect(changed_cb)

def label_color_connect_signals(row: qw.QWidget, changed_cb: Callable[[], None]) -> None:
    row.label_edit.textChanged.connect(changed_cb)
    row.color_edit.textChanged.connect(changed_cb)

def label_color_color_connect_signals(row: qw.QWidget, changed_cb: Callable[[], None]) -> None:
    row.label_edit.textChanged.connect(changed_cb)
    row.color_edit.textChanged.connect(changed_cb)
    row.color_edit2.textChanged.connect(changed_cb)

def overlay_marker_connect_signals(row: qw.QWidget, changed_cb: Callable[[], None]) -> None:
    row.value_edit.textChanged.connect(changed_cb)
    row.size_edit.textChanged.connect(changed_cb)
    row.label_edit.textChanged.connect(changed_cb)
    row.marker_edit.textChanged.connect(changed_cb)
    row.color_edit.textChanged.connect(changed_cb)
    row.edge_color_edit.textChanged.connect(changed_cb)

class ColorLineEdit(qw.QLineEdit):
    def set_hex(self, hex_color: str) -> None:
        hex_color = (hex_color or "").strip()
        self.setText(hex_color)
        self._update_swatch()

    def _update_swatch(self) -> None:
        txt = self.text().strip()
        c = qg.QColor(txt)
        if c.isValid():
            self.setStyleSheet(f"QLineEdit {{ background-color: {c.name()}; }}")
        else:
            self.setStyleSheet("")

class OverlayMarkerRow(qw.QWidget):
    removed = qc.pyqtSignal(object)

    def __init__(self, value= "", size= "", label= "", marker= "", color= "", edgecolor= "",  parent= None):
        super().__init__(parent)
        overall_lay = qw.QVBoxLayout(self)
        overall_lay.setContentsMargins(0,0,0,0)
        top_widget = qw.QWidget()
        bot_widget = qw.QWidget()
        top_lay = qw.QHBoxLayout(top_widget)
        bot_lay = qw.QHBoxLayout(bot_widget)
        top_lay.setContentsMargins(0,0,0,0)
        bot_lay.setContentsMargins(0,0,0,0)

        self.value_edit = qw.QLineEdit(str(value))
        self.value_edit.setPlaceholderText("Cell Value")

        self.size_edit = qw.QLineEdit(str(size))
        self.size_edit.setPlaceholderText("Marker Size")

        self.label_edit = qw.QLineEdit(label)
        self.label_edit.setPlaceholderText("Legend Label")

        self.marker_edit = qw.QLineEdit(marker)
        self.marker_edit.setPlaceholderText("Marker (e.g. ^)")

        self.color_edit = ColorLineEdit(color)
        self.color_edit.setPlaceholderText("#RRGGBB")
        self.color_edit.setMaximumWidth(120)
        self.color_edit.set_hex(color)

        self.edge_color_edit = ColorLineEdit(edgecolor)
        self.edge_color_edit.setPlaceholderText("#RRGGBB")
        self.edge_color_edit.setMaximumWidth(120)
        self.edge_color_edit.set_hex(color)

        self.pick_btn = qw.QToolButton()
        self.pick_btn.setText("🎨")
        self.pick_btn.setToolTip("Pick a color")

        self.pick_btn2 = qw.QToolButton()
        self.pick_btn2.setText("🎨")
        self.pick_btn2.setToolTip("Pick a color")

        self.del_btn = qw.QToolButton()
        self.del_btn.setText("✕")
        self.del_btn.setToolTip("Remove this row")

        self.pick_btn.clicked.connect(self._pick_color)
        self.pick_btn2.clicked.connect(self._pick_color2)
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))

        self.color_edit.textChanged.connect(self.color_edit._update_swatch)
        self.edge_color_edit.textChanged.connect(self.edge_color_edit._update_swatch)

        top_lay.addWidget(self.value_edit, 1)
        top_lay.addWidget(self.size_edit, 0)
        top_lay.addWidget(self.label_edit, 0)
        top_lay.addWidget(self.del_btn, 0)
        bot_lay.addWidget(self.marker_edit, 1)
        bot_lay.addWidget(self.color_edit, 0)
        bot_lay.addWidget(self.pick_btn, 0)
        bot_lay.addWidget(self.edge_color_edit, 0)
        bot_lay.addWidget(self.pick_btn2, 0)

        overall_lay.addWidget(top_widget)
        overall_lay.addWidget(bot_widget)

    def _pick_color(self) -> None:
        initial = qg.QColor(self.color_edit.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit.set_hex(c.name())

    # I am lazy and stupid
    def _pick_color2(self) -> None:
        initial = qg.QColor(self.color_edit2.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit2.set_hex(c.name())

# OverlayMarkerLabel = tuple[Any, str, str | None, str, str | None, str | None]
    def get_data(self):
        try:
            size = int(self.size_edit.text().strip())
        except ValueError:
            size = None
        return (
            self.value_edit.text().strip(),
            size,
            self.label_edit.text().strip(),
            self.marker_edit.text().strip(),
            self.color_edit.text().strip(),
            self.edge_color_edit.text().strip(),
        )

class ValueColorLabelRow(qw.QWidget):
    removed = qc.pyqtSignal(object)

    def __init__(self, value: str = "", label: str = "", color: str = "", indep= False, parent=None):
        super().__init__(parent)
        lay = qw.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.value_edit = qw.QLineEdit(value)
        self.value_edit.setPlaceholderText("Cell Value")
        self.value_edit.setMaximumWidth(120)

        self.color_edit = ColorLineEdit()
        self.color_edit.setPlaceholderText("#RRGGBB")
        self.color_edit.setMaximumWidth(120)
        self.color_edit.set_hex(color)

        self.pick_btn = qw.QToolButton()
        self.pick_btn.setText("🎨")
        self.pick_btn.setToolTip("Pick a color")

        self.label_edit = qw.QLineEdit(label)
        self.label_edit.setPlaceholderText("Label (Optional)")

        if not indep:
            self.del_btn = qw.QToolButton()
            self.del_btn.setText("✕")
            self.del_btn.setToolTip("Remove this row")
            self.del_btn.clicked.connect(lambda: self.removed.emit(self))

        lay.addWidget(self.value_edit, 1)
        lay.addWidget(self.color_edit, 0)
        lay.addWidget(self.pick_btn, 0)
        lay.addWidget(self.label_edit, 0)

        if not indep:
            lay.addWidget(self.del_btn, 0)

        self.pick_btn.clicked.connect(self._pick_color)
        self.color_edit.textChanged.connect(self.color_edit._update_swatch)

    def _pick_color(self) -> None:
        initial = qg.QColor(self.color_edit.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit.set_hex(c.name())

    def get_triple(self) -> tuple[str, str, str]:
        return (
            self.value_edit.text().strip(), 
            self.color_edit.text().strip(),
            self.label_edit.text().strip()
        )

class LabelColorRow(qw.QWidget):
    removed = qc.pyqtSignal(object)

    def __init__(self, label: str = "", color: str = "", color2: str | None = None, parent=None, indep= False, extra_picker= False):
        super().__init__(parent)
        lay = qw.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.label_edit = qw.QLineEdit(label)
        self.label_edit.setPlaceholderText("Label")

        self.color_edit = ColorLineEdit()
        self.color_edit.setPlaceholderText("#RRGGBB")
        self.color_edit.setMaximumWidth(120)
        self.color_edit.set_hex(color)

        self.pick_btn = qw.QToolButton()
        self.pick_btn.setText("🎨")
        self.pick_btn.setToolTip("Pick a color")

        if extra_picker:
            self.color_edit2 = ColorLineEdit()
            self.color_edit2.setPlaceholderText("#RRGGBB")
            self.color_edit2.setMaximumWidth(120)
            if color2 is not None:
                self.color_edit2.set_hex(color2)
            else:
                self.color_edit2.set_hex("")

            self.pick_btn2 = qw.QToolButton()
            self.pick_btn2.setText("🎨")
            self.pick_btn2.setToolTip("Pick a color")

        if not indep:
            self.del_btn = qw.QToolButton()
            self.del_btn.setText("✕")
            self.del_btn.setToolTip("Remove this row")

        lay.addWidget(self.label_edit, 1)
        lay.addWidget(self.color_edit, 0)
        lay.addWidget(self.pick_btn, 0)
        if extra_picker:
            lay.addWidget(self.color_edit2, 0)
            lay.addWidget(self.pick_btn2, 0)

        if not indep:
            lay.addWidget(self.del_btn, 0)

        self.pick_btn.clicked.connect(self._pick_color)
        if extra_picker:
            self.pick_btn2.clicked.connect(self._pick_color2)
        if not indep:
            self.del_btn.clicked.connect(lambda: self.removed.emit(self))

        self.color_edit.textChanged.connect(self.color_edit._update_swatch)
        if extra_picker:
            self.color_edit2.textChanged.connect(self.color_edit2._update_swatch)

    def _pick_color(self) -> None:
        initial = qg.QColor(self.color_edit.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit.set_hex(c.name())

    # I am lazy and stupid
    def _pick_color2(self) -> None:
        initial = qg.QColor(self.color_edit2.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit2.set_hex(c.name())

    def get_pair(self) -> tuple[str, str]:
        return (self.label_edit.text().strip(), self.color_edit.text().strip())

    def get_triple(self) -> tuple[str, str, str] | None:
        if not hasattr(self, "color_edit2"):
            return None
        return (self.label_edit.text().strip(), self.color_edit.text().strip(), self.color_edit2.text().strip())

class ColorRow(qw.QWidget):
    removed = qc.pyqtSignal(object)

    def __init__(self, color: str = "", parent=None, indep= False):
        super().__init__(parent)
        lay = qw.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)

        self.color_edit = ColorLineEdit()
        self.color_edit.setPlaceholderText("#RRGGBB")
        self.color_edit.setMaximumWidth(120)
        self.color_edit.set_hex(color)

        self.pick_btn = qw.QToolButton()
        self.pick_btn.setText("🎨")
        self.pick_btn.setToolTip("Pick a color")

        if not indep:
            self.del_btn = qw.QToolButton()
            self.del_btn.setText("✕")
            self.del_btn.setToolTip("Remove this row")

        lay.addWidget(self.color_edit, 0)
        lay.addWidget(self.pick_btn, 0)

        if not indep:
            lay.addWidget(self.del_btn, 0)

        self.pick_btn.clicked.connect(self._pick_color)
        if not indep:
            self.del_btn.clicked.connect(lambda: self.removed.emit(self))

        self.color_edit.textChanged.connect(self.color_edit._update_swatch)

    def _pick_color(self) -> None:
        initial = qg.QColor(self.color_edit.text().strip())
        if initial.name().lower() == "#000000":
            initial = qg.QColor("#ffffff")
        c = qw.QColorDialog.getColor(initial, self, "Choose color")
        if c.isValid():
            self.color_edit.set_hex(c.name())

    def get_color(self) -> tuple[str]:
        return (self.color_edit.text().strip(),)
