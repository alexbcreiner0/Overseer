from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc
)
import sys

class FloatSlider(qw.QSlider):
    def __init__(self, orientation= "h", float_range= None, init_val= None):
        try: 
            if orientation == "v":
                super().__init__(qc.Qt.Orientation.Vertical)
            elif orientation == "h":
                super().__init__(qc.Qt.Orientation.Horizontal)
            else:
                raise ValueError
        except ValueError:
            print("Invalid orientation choice for FloatSlider. Valid choices are 'h' and 'v'.")
            sys.exit()

        self.current_val = init_val
        self.float_range = float_range
        self.slider_range = (0,1000)
        self.setMinimum(self.slider_range[0])
        self.setMaximum(self.slider_range[1])
        self.setTickInterval(10)

        self.tic_pos = self.compute_tic_pos(self.current_val)
        self.setValue(self.tic_pos)
        self.valueChanged.connect(self.update_value)

        self.wheelEvent = self.no_wheel

    def no_wheel(self, event):
        event.ignore()

    def compute_tic_pos(self, val):
        fmin, fmax = self.float_range
        smin, smax = self.slider_range

        val = max(min(val, fmax), fmin)
        frac = (val - fmin) / (fmax - fmin)

        return int(round(smin + frac * (smax - smin)))

    def compute_value(self, tic_pos):
        fmin, fmax = self.float_range
        smin, smax = self.slider_range

        frac = (tic_pos - smin) / (smax - smin)
        return fmin + frac * (fmax - fmin)

    def get_current_val(self):
        return self.compute_value(self.value())

    def update_value(self, tic_pos):
        new_val = self.compute_value(tic_pos)
        self.current_val = new_val

    def change_value(self, val):
        fmin, fmax = self.float_range

        new_val = max(min(val, fmax), fmin)
        tic_pos = self.compute_tic_pos(new_val)
        self.setValue(tic_pos)

