from pathlib import Path

from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw
)

VALID_MODES = {"any", "file", "folder"}

class FilePicker(qw.QWidget):
    pathChanged = qc.pyqtSignal(str)

    def __init__(self, parent=None, mode= "folder"):
        super().__init__(parent)

        layout = qw.QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.line_edit = qw.QLineEdit()
        self.button = qw.QToolButton()
        self.button.setText("...")

        self.mode = mode if mode in VALID_MODES else "folder"

        layout.addWidget(self.line_edit)
        layout.addWidget(self.button)

        self.line_edit.editingFinished.connect(self._emit_current_path)

        if mode == "file":
            self.button.clicked.connect(self.browse_file)

        elif mode == "folder":
            self.button.clicked.connect(self.browse_folder)

        else:
            menu = qw.QMenu(self.button)

            file_action = menu.addAction("Choose file...")
            file_action.triggered.connect(self.browse_file)

            folder_action = menu.addAction("Choose folder...")
            folder_action.triggered.connect(self.browse_folder)

            self.button.setMenu(menu)
            self.button.setPopupMode(
                qw.QToolButton.ToolButtonPopupMode.InstantPopup
            )

    def _starting_directory(self) -> str:
        """Return a sensible existing directory for the dialog."""
        raw_path = self.text().strip()

        if not raw_path:
            return ""

        path = Path(raw_path).expanduser()

        if path.is_dir():
            return str(path)

        if path.parent.is_dir():
            return str(path.parent)

        return ""

    def _set_selected_path(self, path: str) -> None:
        if not path:
            return

        self.line_edit.setText(path)
        self.pathChanged.emit(path)

    def _emit_current_path(self) -> None:
        self.pathChanged.emit(self.text())

    def browse_file(self, _checked=False) -> None:
        file_path, _ = qw.QFileDialog.getOpenFileName(
            self,
            "Select File",
            self._starting_directory(),
            "All Files (*)",
        )
        self._set_selected_path(file_path)

    def browse_folder(self, _checked=False) -> None:
        folder = qw.QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            self._starting_directory(),
        )
        self._set_selected_path(folder)

    def text(self) -> str:
        return self.line_edit.text()

    def setText(self, text) -> None:
        self.line_edit.setText("" if text is None else str(text))
