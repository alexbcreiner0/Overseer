from PyQt6 import QtWidgets as qw

class VScrollArea(qw.QScrollArea):
    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        w = self.widget()
        if w:
            # Lock content width to the viewport width
            w.setFixedWidth(self.viewport().width())

