from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
# from widgets.SectionDivider import SectionDivider

class TitleControlWidget(qw.QWidget):
    """Per-plot legend controls: toggle, size, position."""
    settingsChanged = qc.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = qw.QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        self.title_checkbox = qw.QCheckBox("Title")
        self.title_checkbox.setChecked(True)

        self.xlabel_checkbox = qw.QCheckBox("X-Axis Title")
        self.xlabel_checkbox.setChecked(True)

        self.ylabel_checkbox = qw.QCheckBox("Y-Axis Title")
        self.ylabel_checkbox.setChecked(True)

        # layout.addWidget(SectionDivider("Legend", alignment= "left"))
        layout.addWidget(self.title_checkbox)
        layout.addWidget(self.xlabel_checkbox)
        layout.addWidget(self.ylabel_checkbox)
        self.title_checkbox.stateChanged.connect(self._emit)
        self.xlabel_checkbox.stateChanged.connect(self._emit)
        self.ylabel_checkbox.stateChanged.connect(self._emit)

    def _emit(self, *args):
        self.settingsChanged.emit()

    def get_settings(self):
        return {
            "title": self.title_checkbox.isChecked(),
            "xlabel": self.xlabel_checkbox.isChecked(),
            "ylabel": self.ylabel_checkbox.isChecked(),
        }
