from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
)
from .SectionDivider import SectionDivider
from .HelpButton import HelpButton

class AutoSizingStack(qw.QStackedWidget):
    
    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w else super().minimumSizeHint()

class DropdownChoices(qw.QWidget):
    infoBoxHovered = qc.pyqtSignal()
    currentIndexChanged = qc.pyqtSignal(int)
    checkStateChanged = qc.pyqtSignal()

    def __init__(self, parent= None, items_per_row= 3):
        super().__init__(parent)
        root = qw.QVBoxLayout(self) # passing self as parent means don't have to call self.setLayout!
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        dropdown_layout = qw.QHBoxLayout()
        dropdown_layout.setContentsMargins(8,0,8,0)
        dropdown_layout.setSpacing(0)

        self.dropdown_choices = qw.QComboBox()
        self.info = HelpButton("?")
        self.items_per_row = items_per_row

        def no_wheel(event):
            event.ignore()
        self.dropdown_choices.wheelEvent = no_wheel

        self.stack = AutoSizingStack()
        root.addWidget(SectionDivider("Plots", alignment= "left"))
        root.addWidget(self.stack)
        dropdown_layout.addWidget(self.dropdown_choices)
        dropdown_layout.addWidget(self.info)
        root.addLayout(dropdown_layout)

        self.pages = {}
        self.grids = {}
        self.boxes = {}

        # self.dropdown_choices.currentTextChanged.connect(self._on_selection_changed)
        self.dropdown_choices.currentIndexChanged.connect(self._on_selection_changed)
        self.info.hovered.connect(self._on_info_hovered)

    def addItem(self, name):
        """Adds the dropdown option like normal, but also creates the necessary accompanying checkbox area for that option."""
        if name in self.pages:
            return

        page = qw.QWidget()
        grid = qw.QGridLayout(page)
        grid.setContentsMargins(8,0,8,0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.pages[name] = page
        self.grids[name] = grid
        self.boxes[name] = []

        self.stack.addWidget(page)
        self.dropdown_choices.addItem(name)

        if self.dropdown_choices.count() == 1:
            self.stack.setCurrentWidget(page)

    def addItems(self, names):
        for name in names: self.addItem(name)

    def add_checkbox(self, option, label, checked= False):
        if option not in self.pages:
            self.addItem(option)

        box = qw.QCheckBox(label)
        box.setChecked(checked)
        box.checkStateChanged.connect(self._on_checkstate_changed)

        grid = self.grids[option]
        boxes = self.boxes[option]
        index = len(boxes)
        row = index // self.items_per_row
        col = index % self.items_per_row

        grid.addWidget(box, row, col)
        boxes.append(box)
        return box

    def _on_checkstate_changed(self):
        self.checkStateChanged.emit()

    def _on_selection_changed(self, index):
        page = self.pages.get(self.dropdown_choices.currentText())
        if page is not None:
            self.stack.setCurrentWidget(page)
            self.stack.updateGeometry()
            if self.parentWidget():
                self.parentWidget().updateGeometry()
        self.currentIndexChanged.emit(index)

    def _on_info_hovered(self):
        self.infoBoxHovered.emit()

    def setToolTip(self, a0):
        self.info.setToolTip(a0)

    def get_current_checked_boxes(self):
        boxes = []
        if self.pages == {}:
            return boxes
        page = self.pages[self.dropdown_choices.currentText()]
        for checkbox in page.findChildren(qw.QCheckBox):
            if checkbox.isChecked(): boxes.append(checkbox.text())
        return boxes

    def set_checked_boxes(self, names):
        names = set(names or [])
        option = self.dropdown_choices.currentText()
        boxes = self.boxes.get(option, [])

        for box in boxes:
            box.blockSignals(True)
            box.setChecked(box.text() in names)
            box.blockSignals(False)

    def currentText(self):
        return self.dropdown_choices.currentText()

    def currentIndex(self):
        return self.dropdown_choices.currentIndex()

    def setCurrentIndex(self, idx):
        try:
            self.dropdown_choices.setCurrentIndex(idx)
        except IndexError:
            pass

