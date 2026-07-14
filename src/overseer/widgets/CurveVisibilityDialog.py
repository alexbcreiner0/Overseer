from __future__ import annotations

from collections import defaultdict

from PyQt6 import QtWidgets as qw


class CurveVisibilityDialog(qw.QDialog):
    """Checkbox dialog for toggling plotted line artists."""

    def __init__(self, toolbar, parent=None):
        super().__init__(parent)
        self.toolbar = toolbar
        self.checkboxes: list[qw.QCheckBox] = []

        self.setWindowTitle("Curve visibility")
        self.resize(520, 600)

        root = qw.QVBoxLayout(self)

        help_label = qw.QLabel(
            "Toggle the currently plotted curves. Hidden curves stay hidden during live updates "
            "as long as their Matplotlib GID stays the same."
        )
        help_label.setWordWrap(True)
        root.addWidget(help_label)

        button_row = qw.QHBoxLayout()
        show_all = qw.QPushButton("Show all")
        hide_all = qw.QPushButton("Hide all")
        clear = qw.QPushButton("Clear overrides")
        refresh = qw.QPushButton("Refresh")

        show_all.clicked.connect(lambda: self._set_all(True))
        hide_all.clicked.connect(lambda: self._set_all(False))
        clear.clicked.connect(self._clear_overrides)
        refresh.clicked.connect(self.rebuild)

        button_row.addWidget(show_all)
        button_row.addWidget(hide_all)
        button_row.addWidget(clear)
        button_row.addStretch(1)
        button_row.addWidget(refresh)
        root.addLayout(button_row)

        self.scroll = qw.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = qw.QWidget()
        self.form = qw.QVBoxLayout(self.content)
        self.form.setContentsMargins(6, 6, 6, 6)
        self.form.setSpacing(8)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, stretch=1)

        close_buttons = qw.QDialogButtonBox(qw.QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        root.addWidget(close_buttons)

        self.rebuild()

    def rebuild(self) -> None:
        self._clear_layout(self.form)
        self.checkboxes.clear()

        items = self.toolbar.curve_visibility_items()
        if not items:
            empty = qw.QLabel("No curve-like Matplotlib line artists are currently available.")
            empty.setWordWrap(True)
            self.form.addWidget(empty)
            self.form.addStretch(1)
            return

        by_axis: dict[int, list[dict]] = defaultdict(list)
        axis_titles: dict[int, str] = {}
        for item in items:
            axis_index = item["axis_index"]
            by_axis[axis_index].append(item)
            axis_titles[axis_index] = item["axis_title"]

        for axis_index in sorted(by_axis):
            title = axis_titles.get(axis_index) or f"Axis {axis_index + 1}"
            group = qw.QGroupBox(f"Axis {axis_index + 1}: {title}")
            group_layout = qw.QVBoxLayout(group)

            for item in by_axis[axis_index]:
                cb = qw.QCheckBox(item["label"])
                cb.setToolTip(item["tooltip"])
                cb.setChecked(bool(item["visible"]))
                cb.toggled.connect(
                    lambda checked, key=item["key"]: self.toolbar.set_curve_visible(key, checked)
                )
                group_layout.addWidget(cb)
                self.checkboxes.append(cb)

            self.form.addWidget(group)

        self.form.addStretch(1)

    def _set_all(self, visible: bool) -> None:
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(visible)
            cb.blockSignals(False)
        self.toolbar.set_all_curves_visible(visible)

    def _clear_overrides(self) -> None:
        self.toolbar.clear_curve_visibility_overrides()
        self.rebuild()

    def _clear_layout(self, layout: qw.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                continue

            nested = item.layout()
            if nested is not None:
                self._clear_layout(nested)
                nested.deleteLater()
