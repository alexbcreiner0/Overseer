from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
)
from .LatexLabel import LatexLabel
from .FloatSlider import FloatSlider
from .HelpButton import HelpButton

class EntryBlock(qw.QWidget):
    valueChanged = qc.pyqtSignal(str, object)

    def __init__(self, name, var_label, slider_range, initial, tooltip, num_type= "float"):
        super().__init__()
        layout = qw.QVBoxLayout(self)
        layout.setSpacing(0)

        self.entry_text_changed = False

        self.name = name
        self.top_row_layout = qw.QHBoxLayout()
        if num_type != "float":
            if num_type == "int":
                self.num_type = num_type
                self.current_val = int(initial)
            else:
                print("Unrecognized num_type argument. Valid arguments are 'int' and 'float'. Defaulting to float.")
                self.num_type = "float"
        else:
            self.num_type = "float"
            self.current_val = initial
        self.range = slider_range
        
        self.label = LatexLabel(base_point_size= 12.0)
        self.label.setText(var_label)
        self.label.setFixedWidth(self.label.sizeHint().width())
        self.label.setSizePolicy(
            qw.QSizePolicy.Policy.Maximum,
            qw.QSizePolicy.Policy.Preferred
        )
        self.label.setAlignment(qc.Qt.AlignmentFlag.AlignLeft | qc.Qt.AlignmentFlag.AlignVCenter)
        
        self.entry = qw.QLineEdit()
        self.entry.setAlignment(qc.Qt.AlignmentFlag.AlignLeft)
        self.entry.setText(str(self.current_val))
        self.entry.setSizePolicy(
            qw.QSizePolicy.Policy.MinimumExpanding,
            qw.QSizePolicy.Policy.Fixed
        )
        self.debounce_timer = qc.QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.entry.textChanged.connect(lambda _: self.debounce_timer.start(300))
        self.debounce_timer.timeout.connect(self.entry_change)

        self.info_button = HelpButton("?", tooltip)

        self.top_row_layout.addWidget(self.label, 0)
        self.top_row_layout.addWidget(self.entry, 1)
        self.top_row_layout.addWidget(self.info_button, 0)

        self.top_row_widget = qw.QWidget()
        self.setSizePolicy(
            qw.QSizePolicy.Policy.Preferred,
            qw.QSizePolicy.Policy.Fixed
        )
        self.top_row_widget.setLayout(self.top_row_layout)

        self.bottom_row_layout = qw.QHBoxLayout()
        self.lhlabel = qw.QLabel(str(self.range[0]))
        self.rhlabel = qw.QLabel(str(self.range[1]))

        self.slider = FloatSlider(orientation= "h", float_range= self.range, init_val= self.current_val)
        self.slider.sliderReleased.connect(self.slider_change)
        self.slider.valueChanged.connect(self.slider_change_prelude)

        self.bottom_row_layout.addWidget(self.lhlabel)
        self.bottom_row_layout.addWidget(self.slider)
        self.bottom_row_layout.addWidget(self.rhlabel)

        self.bottom_row_widget = qw.QWidget()
        self.bottom_row_widget.setLayout(self.bottom_row_layout)

        layout.addWidget(self.top_row_widget)
        layout.addWidget(self.bottom_row_widget)

    def entry_change(self):
        try:
            val = float(self.entry.text())
        except ValueError:
            self.entry_text_changed = False
            return

        if self.num_type == "int":
            self.current_val = int(val)
        else:
            self.current_val = val
        
        if val < self.range[0]:
            slider_val = self.range[0]
        elif val > self.range[1]:
            slider_val = self.range[1]
        else:
            slider_val = val

        self.entry_text_changed = True
        self.slider.change_value(slider_val)
        self.entry_text_changed = False

        self.valueChanged.emit(self.name, self.current_val)

    def slider_change_prelude(self):
        if not self.slider.isSliderDown(): self.slider_change()

    def slider_change(self):
        if self.entry_text_changed:
            return
        new_val = self.slider.get_current_val()
        if self.num_type == "int":
            self.current_val = int(new_val)
        else:
            self.current_val = new_val
        self.entry.setText(str(self.current_val))

    def get(self):
        return self.current_val


