from matplotlib.backends.backend_qt import NavigationToolbar2QT
from PyQt6 import QtWidgets as qw
from PyQt6 import QtCore as qc
from pathlib import Path
from typing import Any, Optional
from matplotlib.backends.qt_editor import figureoptions
from dataclasses import dataclass, fields, is_dataclass, asdict

class CustomNavigationToolbar(NavigationToolbar2QT):
    titles_applied = qc.pyqtSignal()

    def __init__(self, canvas, parent=None, default_dir=None, default_save_name= "figure", params= None):
        super().__init__(canvas, parent)
        self.set_default_dir(default_dir)
        
        self.default_save_name = default_save_name
        self.params= params

    def set_default_dir(self, default_dir: str | None):
        self.default_dir = Path(default_dir).expanduser() if default_dir else None
        if self.default_dir:
            self.default_dir.mkdir(parents=True, exist_ok=True)

    def _format_save_name(self) -> str:
        template = self.default_save_name
        
        if self.params is None or not is_dataclass(self.params):
            return template
        else:
            params_dict = asdict(self.params)
        
        result = ""
        i = 0
        while i < len(template):
            if template[i] == "{":
                j = template.find("}", i)
                if j == -1:
                    # if syntax error in string (e.g. a starting { but no ending }, just treat the { like any other character)
                    result += template[i]
                    i += 1
                    continue

                key = template[i+1:j]

                show_name = key.endswith("=")
                if show_name:
                    # the key doesn't include the equal sign
                    key = key[:-1]
                
                if key in params_dict:
                    value = params_dict[key]
                    if show_name:
                        result += f"{key}={value}"
                    else:
                        result += str(value)
                    i = j + 1
                else:
                    result += f"{key}"
                    i = j + 1
            else:
                result += template[i]
                i += 1

        return result

    def save_figure(self, *args):
        """
        Same as stock toolbar, but dialog starts in self.default_dir.
        """
        name = self._format_save_name()
        if self.default_dir:
            # Use Qt dialog directly so we can force starting directory
            fname, _ = qw.QFileDialog.getSaveFileName(
                self.parent(),                       # parent widget
                "Save the figure",
                str(self.default_dir / f"{name}.png"), # suggested path/name
                "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;All files (*)",
            )
            if not fname:
                return

            fig = self.canvas.figure

            # 2. Match figure size to the on-screen canvas (fix cramped / huge legend issue)
            w_px = self.canvas.width()
            h_px = self.canvas.height()
            dpi = fig.dpi
            fig.set_size_inches(w_px / dpi, h_px / dpi, forward=True)

            # Optional: tighten layout if you want
            fig.tight_layout()

            # 3. Actually save
            fig.savefig(fname, dpi=dpi)

            # self.canvas.figure.savefig(fname)
        else:
            super().save_figure(*args)

    # def save_figure(self, *args):
    #     # 1. Ask where to save
    #     path, _ = qw.QFileDialog.getSaveFileName(
    #         self,
    #         "Save figure",
    #         str(self.default_dir) if self.default_dir else "",
    #         "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;All files (*)",
    #     )
    #     # path, _ = qw.QFileDialog.getSaveFileName(
    #     #     self,
    #     #     "Save figure",
    #     #     self.default_dir,
    #     #     "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;All files (*)",
    #     # )
    #     if not path:
    #         return

    #     fig = self.canvas.figure

    #     # 2. Match figure size to the on-screen canvas (fix cramped / huge legend issue)
    #     w_px = self.canvas.width()
    #     h_px = self.canvas.height()
    #     dpi = fig.dpi
    #     fig.set_size_inches(w_px / dpi, h_px / dpi, forward=True)

    #     # Optional: tighten layout if you want
    #     fig.tight_layout()

    #     # 3. Actually save
    #     fig.savefig(path, dpi=dpi)
