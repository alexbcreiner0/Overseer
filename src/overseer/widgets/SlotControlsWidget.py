from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
# from widgets.SectionDivider import SectionDivider

class SlotControlsWidget(qw.QWidget):
    """Per-plot legend controls: toggle, size, position."""
    settingsChanged = qc.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = qw.QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        self.legend_checkbox = qw.QCheckBox("Legend")
        self.legend_checkbox.setChecked(True)

        self.legend_size_spin = qw.QSpinBox()
        self.legend_size_spin.setRange(1, 24)
        self.legend_size_spin.setValue(10)
        self.legend_size_spin.setPrefix("Legend Size ")

        self.legend_loc_label = qw.QLabel("Legend Loc: ")

        self.legend_pos_combo = qw.QComboBox()
        self.legend_pos_combo.addItems(["upper right", "upper left",
                                 "lower left", "lower right"])

        self.lazy_legend_convert_dict = {
            "upper right": 0,
            "upper left": 1,
            "lower left": 2,
            "lower right": 3
        }

        self.title_checkbox = qw.QCheckBox("Plot Title")
        self.title_checkbox.setChecked(True)

        self.xlabel_checkbox = qw.QCheckBox("X-Axis Title")
        self.xlabel_checkbox.setChecked(True)

        self.ylabel_checkbox = qw.QCheckBox("Y-Axis Title")
        self.ylabel_checkbox.setChecked(True)

        # layout.addWidget(SectionDivider("Legend", alignment= "left"))
        layout.addWidget(self.legend_size_spin)
        layout.addWidget(self.legend_loc_label)
        layout.addWidget(self.legend_pos_combo)
        layout.addWidget(self.legend_checkbox)
        layout.addWidget(self.title_checkbox)
        layout.addWidget(self.xlabel_checkbox)
        layout.addWidget(self.ylabel_checkbox)

        self.legend_checkbox.stateChanged.connect(self._emit)
        self.legend_size_spin.valueChanged.connect(self._emit)
        self.legend_pos_combo.currentIndexChanged.connect(self._emit)
        self.title_checkbox.stateChanged.connect(self._emit)
        self.xlabel_checkbox.stateChanged.connect(self._emit)
        self.ylabel_checkbox.stateChanged.connect(self._emit)

    def _emit(self, *args):
        self.settingsChanged.emit()

    def get_settings(self):
        return {
            "legend_visible": self.legend_checkbox.isChecked(),
            "legend_fontsize": self.legend_size_spin.value(),
            "legend_loc": self.legend_pos_combo.currentText(),
            "title": self.title_checkbox.isChecked(),
            "xlabel": self.xlabel_checkbox.isChecked(),
            "ylabel": self.ylabel_checkbox.isChecked(),
        }

    def set_settings(self, settings: dict) -> None:
        if 'legend_visible' in settings:
            if settings['legend_visible'] == True:
                self.legend_checkbox.setChecked(True)
            else:
                self.legend_checkbox.setChecked(False)

        if 'legend_fontsize' in settings:
            self.legend_size_spin.setValue(settings['legend_fontsize'])

        if 'legend_loc' in settings:
            self.legend_pos_combo.setCurrentIndex(self.lazy_legend_convert_dict[settings['legend_loc']])

        if 'title' in settings:
            if settings['title'] == True:
                self.title_checkbox.setChecked(True)
            else:
                self.title_checkbox.setChecked(False)

        if 'xlabel' in settings:
            if settings['xlabel'] == True:
                self.xlabel_checkbox.setChecked(True)
            else:
                self.xlabel_checkbox.setChecked(False)

        if 'ylabel' in settings:
            if settings['ylabel'] == True:
                self.ylabel_checkbox.setChecked(True)
            else:
                self.ylabel_checkbox.setChecked(False)
