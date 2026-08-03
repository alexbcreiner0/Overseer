from __future__ import annotations
from collections import defaultdict

from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc,
)


class CurveVisibilityDialog(qw.QDialog):
    """Checkbox dialog for toggling plotted line artists."""

    def __init__(self, toolbar, graph_panel, parent=None):
        super().__init__(parent)
        self.toolbar = toolbar
        self.graph_panel = graph_panel

        self.checkboxes_by_axis: dict[int, list[qw.QCheckBox]] = {}
        self.items_by_axis: dict[int, list[dict]] = {}
        self._tab_axis_indices: list[int] = []

        self.graph_panel.curve_artists_changed.connect(self._schedule_rebuild)

        self.setWindowTitle("Curve visibility")
        self.resize(520, 600)

        self.checkboxes_by_key: dict[object, qw.QCheckBox] = {}
        self._items_signature = ()
        self._rebuild_pending = False

        root = qw.QVBoxLayout(self)

        # help_label = qw.QLabel(
        #     "Toggle the currently plotted curves. Hidden curves stay hidden during live updates "
        #     "as long as their Matplotlib GID stays the same."
        # )
        # help_label.setWordWrap(True)
        # root.addWidget(help_label)

        refresh_row = qw.QHBoxLayout()
        refresh_row.addStretch(1)

        refresh = qw.QPushButton("Refresh")
        refresh.clicked.connect(self.rebuild)
        refresh_row.addWidget(refresh)

        root.addLayout(refresh_row)

        self.tabs = qw.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        root.addWidget(self.tabs, stretch=1)

        close_buttons = qw.QDialogButtonBox(qw.QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        root.addWidget(close_buttons)

        self.rebuild()

    # def _schedule_rebuild(self) -> None:
    #     if not self.isVisible():
    #         return

    #     qc.QTimer.singleShot(0, self.rebuild)

    def _schedule_rebuild(self) -> None:
        if not self.isVisible() or self._rebuild_pending:
            return

        self._rebuild_pending = True
        qc.QTimer.singleShot(50, self._process_pending_rebuild)

    def rebuild(self, items: list[dict] | None = None) -> None:
        previous_axis_index = self._current_axis_index()

        self._clear_tabs()
        self.checkboxes_by_axis.clear()
        self.checkboxes_by_key.clear()
        self.items_by_axis.clear()
        self._tab_axis_indices.clear()

        if items is None:
            items = self.toolbar.curve_visibility_items()

        self._items_signature = self._visibility_signature(items)

        if not items:
            self._add_empty_tab()
            return
        # previous_axis_index = self._current_axis_index()

        # self._clear_tabs()
        # self.checkboxes_by_axis.clear()
        # self.items_by_axis.clear()
        # self._tab_axis_indices.clear()

        # items = self.toolbar.curve_visibility_items()
        # if not items:
        #     self._add_empty_tab()
        #     return

        by_axis: dict[int, list[dict]] = defaultdict(list)
        axis_titles: dict[int, str] = {}
        for item in items:
            axis_index = item["axis_index"]
            by_axis[axis_index].append(item)
            axis_titles[axis_index] = item["axis_title"]

        for axis_index in sorted(by_axis):
            axis_items = by_axis[axis_index]
            self.items_by_axis[axis_index] = axis_items
            self.checkboxes_by_axis[axis_index] = []

            title = axis_titles.get(axis_index) or f"Axis {axis_index + 1}"
            tab = self._build_axis_tab(axis_index, axis_items)

            self.tabs.addTab(tab, f"Axis {axis_index + 1}: {title}")
            self._tab_axis_indices.append(axis_index)

        if previous_axis_index in self._tab_axis_indices:
            self.tabs.setCurrentIndex(
                self._tab_axis_indices.index(previous_axis_index)
            )

    def _build_axis_tab(self, axis_index: int, items: list[dict]) -> qw.QWidget:
        tab = qw.QWidget()
        tab_layout = qw.QVBoxLayout(tab)
        tab_layout.setContentsMargins(6, 6, 6, 6)
        tab_layout.setSpacing(8)

        button_row = qw.QHBoxLayout()
        show_all = qw.QPushButton("Show all")
        hide_all = qw.QPushButton("Hide all")
        clear = qw.QPushButton("Reset defaults")

        show_all.clicked.connect(
            lambda _checked=False, index=axis_index: self._set_axis(index, True)
        )
        hide_all.clicked.connect(
            lambda _checked=False, index=axis_index: self._set_axis(index, False)
        )
        clear.clicked.connect(
            lambda _checked=False, index=axis_index: self._clear_axis_overrides(index)
        )

        button_row.addWidget(show_all)
        button_row.addWidget(hide_all)
        button_row.addWidget(clear)
        button_row.addStretch(1)
        tab_layout.addLayout(button_row)

        scroll = qw.QScrollArea()
        scroll.setWidgetResizable(True)

        content = qw.QWidget()
        form = qw.QVBoxLayout(content)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(8)

        for item in items:
            checkbox = qw.QCheckBox(item["label"])
            checkbox.setToolTip(item["tooltip"])
            checkbox.setChecked(bool(item["visible"]))
            checkbox.toggled.connect(
                lambda checked, key=item["key"]: self.toolbar.set_curve_visible(
                    key, checked
                )
            )
            form.addWidget(checkbox)
            self.checkboxes_by_axis[axis_index].append(checkbox)
            self.checkboxes_by_key[item["key"]] = checkbox

        form.addStretch(1)
        scroll.setWidget(content)
        tab_layout.addWidget(scroll, stretch=1)

        return tab

    def _set_axis(self, axis_index: int, visible: bool) -> None:
        for checkbox in self.checkboxes_by_axis.get(axis_index, []):
            checkbox.blockSignals(True)
            checkbox.setChecked(visible)
            checkbox.blockSignals(False)

        for item in self.items_by_axis.get(axis_index, []):
            self.toolbar.set_curve_visible(item["key"], visible)

    def _clear_axis_overrides(self, axis_index: int) -> None:
        items = self.items_by_axis.get(axis_index, [])
        keys = [item["key"] for item in items]

        # The toolbar's current public clear method clears every axis. To keep
        # this action local to one tab, first restore this axis's curves, then
        # remove only their entries from the toolbar's override dictionary.
        for key in keys:
            self.toolbar.set_curve_visible(key, True)

        overrides = getattr(self.toolbar, "_curve_visibility_overrides", None)
        if isinstance(overrides, dict):
            for key in keys:
                overrides.pop(key, None)

        for checkbox in self.checkboxes_by_axis.get(axis_index, []):
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)

    def _current_axis_index(self) -> int | None:
        tab_index = self.tabs.currentIndex()
        if 0 <= tab_index < len(self._tab_axis_indices):
            return self._tab_axis_indices[tab_index]
        return None

    def _add_empty_tab(self) -> None:
        tab = qw.QWidget()
        layout = qw.QVBoxLayout(tab)

        empty = qw.QLabel(
            "No curve-like Matplotlib line artists are currently available."
        )
        empty.setWordWrap(True)
        empty.setAlignment(qc.Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(empty)
        layout.addStretch(1)

        self.tabs.addTab(tab, "No curves")

    def _clear_tabs(self) -> None:
        while self.tabs.count():
            tab = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if tab is not None:
                tab.deleteLater()

    def _process_pending_rebuild(self) -> None:
        self._rebuild_pending = False

        if not self.isVisible():
            return

        # Never replace a widget while the user is clicking it.
        if (
            qw.QApplication.mouseButtons()
            != qc.Qt.MouseButton.NoButton
        ):
            self._schedule_rebuild()
            return

        items = self.toolbar.curve_visibility_items()
        signature = self._visibility_signature(items)

        if signature != self._items_signature:
            self.rebuild(items)
        else:
            self._sync_checkbox_states(items)

    def _visibility_signature(self, items: list[dict]) -> tuple:
        return tuple(
            (
                item["axis_index"],
                item["key"],
                item["label"],
                item["axis_title"],
            )
            for item in items
        )


    def _sync_checkbox_states(self, items: list[dict]) -> None:
        for item in items:
            checkbox = self.checkboxes_by_key.get(item["key"])
            if checkbox is None:
                continue

            visible = bool(item["visible"])

            if checkbox.isChecked() == visible:
                continue

            checkbox.blockSignals(True)
            checkbox.setChecked(visible)
            checkbox.blockSignals(False)
