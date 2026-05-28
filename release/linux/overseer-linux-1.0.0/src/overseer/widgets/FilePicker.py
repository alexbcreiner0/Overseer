from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QToolButton, QFileDialog
)

class FilePicker(QWidget):
    def __init__(self, parent=None, mode= "folder"):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.line_edit = QLineEdit()
        self.button = QToolButton()
        self.button.setText("...")
        self.mode = "folder"

        layout.addWidget(self.line_edit)
        layout.addWidget(self.button)

        self.button.clicked.connect(self.browse)

    def browse(self):
        if self.mode == "folder":
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder:
                self.line_edit.setText(folder)
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select File",
                "",
                "All Files (*.*)"
            )
            if file_path:
                self.line_edit.setText(file_path)

    def text(self):
        return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(text)
