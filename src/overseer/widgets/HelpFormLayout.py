# widgets/HelpFormLayout.py
from __future__ import annotations

from PyQt6 import QtWidgets as qw, QtCore as qc

from .HelpButton import HelpButton  # adjust import path as needed


class HelpFormLayout(qw.QFormLayout):
    """
    QFormLayout that can *optionally* append a help/tooltip button to a field row.

    Default: no help button.
    Opt-in per row via addRow(..., help_text="...") or addRow(..., help=True).
    """

    def __init__(
        self,
        parent: qw.QWidget | None = None,
        *,
        help_button_cls: type[qw.QToolButton] = HelpButton,
        button_fixed_width: int = 22,
        button_text: str = "?",
    ):
        super().__init__(parent)
        self._help_button_cls = help_button_cls
        self._button_fixed_width = button_fixed_width
        self._button_text = button_text

        # Map original field widget -> wrapper widget (only for wrapped rows)
        self._field_to_wrapper: dict[qw.QWidget, qw.QWidget] = {}

    def addRow(self, *args, **kwargs):
        """
        Supports:
          addRow(QWidget)  # spanning, unchanged
          addRow(label, field)  # unchanged
          addRow(label, field, help_text="...")  # opt-in
          addRow(label, field, help=True)        # opt-in, uses fallback text
        """
        help_text = kwargs.pop("help_text", None)
        help_flag = bool(kwargs.pop("help", False))
        if kwargs:
            unknown = ", ".join(kwargs.keys())
            raise TypeError(f"Unknown keyword(s) for addRow: {unknown}")

        if len(args) == 1 and isinstance(args[0], qw.QWidget):
            # Spanning row (no label/field distinction) — keep as-is.
            return super().addRow(args[0])

        if len(args) != 2:
            raise TypeError(f"HelpFormLayout.addRow expected 1 or 2 positional args, got {len(args)}")

        label, field = args
        if not isinstance(field, qw.QWidget):
            raise TypeError("HelpFormLayout.addRow(field=...) must be a QWidget")

        # Only wrap when explicitly requested
        if help_flag or (isinstance(help_text, str) and help_text.strip()):
            wrapped = self._wrap_field(field, help_text=help_text)
            return super().addRow(label, wrapped)

        return super().addRow(label, field)

    def setRowVisible(self, *args):  # noqa: N802
        """
        Compatibility with setRowVisible(widget,bool) even if widget is nested in our wrapper.
        """
        if len(args) != 2:
            raise TypeError("setRowVisible expects (row_or_widget, visible_bool)")

        target, visible = args
        if isinstance(target, int):
            return super().setRowVisible(target, visible)

        if not isinstance(target, qw.QWidget):
            raise TypeError("setRowVisible target must be int or QWidget")

        row = self._find_row_for_widget_or_descendant(target)
        if row is None:
            return super().setRowVisible(target, visible)

        return super().setRowVisible(row, visible)

    def _wrap_field(self, field: qw.QWidget, *, help_text: str | None) -> qw.QWidget:
        tip = (help_text or "").strip()
        if not tip:
            tip = self._fallback_tooltip_for(field)

        btn = self._help_button_cls(text=self._button_text, tooltip=tip)
        btn.setFocusPolicy(qc.Qt.FocusPolicy.NoFocus)
        if self._button_fixed_width > 0:
            btn.setFixedWidth(self._button_fixed_width)

        # If you requested help but provided no text and no fallback exists, hide/disable.
        if not tip:
            btn.setVisible(False)
            btn.setEnabled(False)

        wrap = qw.QWidget()
        lay = qw.QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addWidget(field, 1)
        lay.addWidget(btn, 0, alignment=qc.Qt.AlignmentFlag.AlignVCenter)

        self._field_to_wrapper[field] = wrap
        return wrap

    def _fallback_tooltip_for(self, w: qw.QWidget) -> str:
        prop = w.property("help_text")
        if isinstance(prop, str) and prop.strip():
            return prop.strip()
        return (w.toolTip() or "").strip()

    def _find_row_for_widget_or_descendant(self, w: qw.QWidget) -> int | None:
        # If caller passes the original field widget, and we wrapped it, jump to wrapper
        if w in self._field_to_wrapper:
            w = self._field_to_wrapper[w]

        for row in range(self.rowCount()):
            label_item = self.itemAt(row, qw.QFormLayout.ItemRole.LabelRole)
            field_item = self.itemAt(row, qw.QFormLayout.ItemRole.FieldRole)

            label_w = label_item.widget() if label_item else None
            field_w = field_item.widget() if field_item else None

            if w is label_w or w is field_w:
                return row
            if field_w is not None and field_w.isAncestorOf(w):
                return row
            if label_w is not None and label_w.isAncestorOf(w):
                return row
        return None
