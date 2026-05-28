from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc
)

class SectionDivider(qw.QWidget):
    def __init__(self, title: str = "", alignment= "center", parent=None):
        super().__init__(parent)
        layout = qw.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        left = qw.QFrame()
        left.setFrameShape(qw.QFrame.Shape.HLine)
        left.setFrameShadow(qw.QFrame.Shadow.Sunken)
        left.setMinimumWidth(20)
        if alignment == "left":
            left.setSizePolicy(qw.QSizePolicy.Policy.Maximum, qw.QSizePolicy.Policy.Preferred)

        right = qw.QFrame()
        right.setFrameShape(qw.QFrame.Shape.HLine)
        right.setFrameShadow(qw.QFrame.Shadow.Sunken)
        if alignment == "right":
            left.setSizePolicy(qw.QSizePolicy.Policy.Maximum, qw.QSizePolicy.Policy.Preferred)

        label = qw.QLabel(title)
        
        if alignment == "left":
            label.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        elif alignment == "right":
            label.setAlignment(qc.Qt.AlignmentFlag.AlignRight)
        else: 
            label.setAlignment(qc.Qt.AlignmentFlag.AlignCenter)

        label.setSizePolicy(qw.QSizePolicy.Policy.Expanding,
                            qw.QSizePolicy.Policy.Preferred)

        layout.addWidget(left, 1)
        layout.addWidget(label, 0)
        layout.addWidget(right, 1)

