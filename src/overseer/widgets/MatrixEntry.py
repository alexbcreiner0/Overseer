from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
)
from functools import partial
from numpy import ndarray, zeros
import numpy as np
from .LatexLabel import LatexLabel
from .HelpButton import HelpButton

class MatrixEntry(qw.QWidget):
    textChanged = qc.pyqtSignal(str, ndarray)

    def __init__(self, name, label, dim, initial, tooltip= ""):
        super().__init__()
        root = qw.QHBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        self.name = name
        self.dim = dim
        print(f"{dim=}")
        self._bulk_updating = False
        self._cell_timers = []

        left_entries = qw.QWidget()
        left_layout = qw.QVBoxLayout(left_entries)

        label_widget = LatexLabel()
        font = label_widget.font()
        font.setPointSize(7)
        label_widget.setFont(font)
        label_widget.setText(label)

        tooltip_widget = HelpButton("?", tooltip)

        left_layout.addWidget(label_widget, alignment = qc.Qt.AlignmentFlag.AlignLeft, stretch=3)
        left_layout.addWidget(tooltip_widget, alignment= qc.Qt.AlignmentFlag.AlignLeft, stretch=0)
        root.addWidget(left_entries, alignment= qc.Qt.AlignmentFlag.AlignLeft, stretch= 0)

        matrix_entries = qw.QWidget()
        matrix_layout = qw.QGridLayout(matrix_entries)

        self.debounce_timer = qc.QTimer(self)
        self.debounce_timer.setSingleShot(True)

        self.entries = []
        for i in range(dim[0]):
            self.entries.append([])
            self._cell_timers.append([])
            for j in range(dim[1]):
                entry = qw.QLineEdit()
                self.entries[i].append(entry)
                matrix_layout.addWidget(entry, i, j)
                try:
                    entry.setText(str(initial[i][j]))
                except Exception:
                    pass

                timer = qc.QTimer(entry)
                timer.setSingleShot(True)
                self._cell_timers[i].append(timer)

                def on_txt(_=None, t=timer):
                    if self._bulk_updating:
                        return
                    t.start(300)

                entry.textChanged.connect(on_txt)
                timer.timeout.connect(partial(self._on_text_change, i, j))

                # entry.textChanged.connect(partial(self._on_text_change, i, j))

        root.addWidget(matrix_entries, alignment= qc.Qt.AlignmentFlag.AlignLeft, stretch= 3)

    def _on_text_change(self, i, j):
        try:
            self.textChanged.emit(self.name, self._current_matrix())
        except ValueError:
            pass

    def _current_matrix(self):
        new_matrix = zeros(self.dim)
        for i in range(self.dim[0]):
            for j in range(self.dim[1]):
                new_matrix[i][j] = float(self.entries[i][j].text())
        if self.dim[0] != self.dim[1]:
            new_matrix = new_matrix.reshape(1, -1)[0]
        return new_matrix


    def change_values(self, array):
        self._bulk_updating = True
        try:
            for i in range(self.dim[0]):
                for j in range(self.dim[1]):
                    self._cell_timers[i][j].stop()

            for i in range(self.dim[0]): # loop over rows
                if self.dim[1] > 1: # if there's more than 1 column
                    for j in range(self.dim[1]):
                        with qc.QSignalBlocker(self.entries[i][j]):
                            self.entries[i][j].setText(f"{array[i][j]:.8g}")
                else:
                    with qc.QSignalBlocker(self.entries[i][0]):
                        if isinstance(array[i], (int, float, np.int64, np.float64)):
                            self.entries[i][0].setText(f"{array[i]:.8g}")
                        else:
                            self.entries[i][0].setText(f"{array[i][0]:.8g}")
        finally:
            self._bulk_updating = False

        try:
            self.textChanged.emit(self.name, self._current_matrix())
        except ValueError:
            pass
