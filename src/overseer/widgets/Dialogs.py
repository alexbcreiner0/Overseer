from PyQt6 import (
    QtWidgets as qw,
    QtGui as qg
)
import re, os
from datetime import datetime
from overseer.tools.creation_tools import create_new_model_dir
from overseer.paths import rpath

class DescDialog(qw.QDialog):
    def __init__(self, parent= None, display_text= ""):
        super().__init__(parent)
        root = qw.QVBoxLayout(self)
        self.resize(520, 200)
        
        display_label = qw.QLabel()
        if display_text == "":
            display_label.setText("No description provided.")
        else:
            display_label.setText(display_text)

        finish_button = qw.QDialogButtonBox(qw.QDialogButtonBox.StandardButton.Cancel)
        finish_button.rejected.connect(self.reject)
        root.addWidget(display_label)
        root.addWidget(finish_button)
        display_label.setWordWrap(True)

    def bootstrap(self):
        if self.exec() == qw.QDialog.DialogCode.Rejected: # close once the acceptance flag is flagged (in the on_save method)
            return  #after that, grab the variables and return them
        return None
 
class NewModelDialog(qw.QDialog):
    def __init__(self, parent= None):
        super().__init__(parent)
        root = qw.QVBoxLayout()
        self.resize(520, 200)
        
        entry_widget = qw.QWidget()
        layout = qw.QGridLayout(entry_widget)
        name_label = qw.QLabel("Name of Model: ")
        self.name_entry = qw.QLineEdit()
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(self.name_entry, 0, 1)

        self.status_bar = qw.QStatusBar()
        
        bottom_widget = qw.QWidget()
        bottom_layout = qw.QHBoxLayout(bottom_widget)

        buttons = qw.QDialogButtonBox()
        make_button = buttons.addButton("Create Directory", qw.QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(make_button, qw.QDialogButtonBox.ButtonRole.ActionRole)
        close_button = buttons.addButton(qw.QDialogButtonBox.StandardButton.Close)
        make_button.clicked.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        bottom_layout.addWidget(buttons)

        self.dialog_label = qw.QLabel()
        bottom_layout.addWidget(self.dialog_label)
        
        root.addWidget(entry_widget)
        root.addWidget(bottom_widget)

        root.addWidget(self.status_bar)

        self.setLayout(root)

    def _on_save(self):
        name = self.name_entry.text().strip()
        if not name:
            self.dialog_label.setText("Please enter a name.")
            self.name_entry.setFocus()
            return

        if os.path.isdir(rpath(make_shortname(name))):
            self.status_bar.showMessage("Name already in use. Please choose something different.")
            self.name_entry.setFocus()
            return
    
        # try:
        create_new_model_dir(make_shortname(name), gui_dialog= True)
        self.status_bar.showMessage(f"Done! Model Created. Check models directory for a folder named {make_shortname(name)}")
        # except OSError:
        #     self.status_bar.showMessage("Error creating model. Check your file permissions.")

    def get_values(self):
        return (
            make_shortname(self.name_entry.text().strip()),
            self.name_entry.text().strip(),
            self.desc_entry.toPlainText().strip()
        )

    def bootstrap(self, parent= None):
        if self.exec() == qw.QDialog.DialogCode.Accepted: # close once the acceptance flag is flagged (in the on_save method)
            return self.get_values() #after that, grab the variables and return them
        return None

class SaveDialog(qw.QDialog):
    def __init__(self, existing_names= [], title= "Save Preset", parent= None, name_text= None, desc_text= None):
        super().__init__(parent)
        self.existing_names = existing_names
        root = qw.QVBoxLayout()
        self.resize(520, 200)
        self.setWindowTitle(title)
        title = qw.QLabel(title)
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        title.setFont(font)

        root.addWidget(title)
        
        entry_widget = qw.QWidget()
        layout = qw.QGridLayout(entry_widget)
        if not name_text:
            name_label = qw.QLabel("Name: ")
        else:
            name_label = qw.QLabel(name_text)
        if not desc_text:
            desc_label = qw.QLabel("(Optional) Description: ")
        else:
            desc_label = qw.QLabel("(Optional) New Description: ")
        self.name_entry = qw.QLineEdit()
        now = datetime.now().astimezone()
        self.name_entry.setText(str(now))
        self.desc_entry = qw.QTextEdit()
        self.save_axis_settings = qw.QCheckBox("Include Axis Settings")
        layout.addWidget(name_label, 0, 0)
        layout.addWidget(desc_label, 1, 0)
        layout.addWidget(self.name_entry, 0, 1)
        layout.addWidget(self.desc_entry, 1, 1)
        layout.addWidget(self.save_axis_settings, 2, 0)

        bottom_widget = qw.QWidget()
        bottom_layout = qw.QHBoxLayout(bottom_widget)

        buttons = qw.QDialogButtonBox(
            qw.QDialogButtonBox.StandardButton.Save | # calls self.accept() when clicked
            qw.QDialogButtonBox.StandardButton.Cancel # calls self.reject() when clicked
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        bottom_layout.addWidget(buttons)

        self.dialog_label = qw.QLabel()
        bottom_layout.addWidget(self.dialog_label)
        
        root.addWidget(entry_widget)
        root.addWidget(bottom_widget)

        self.setLayout(root)

    def _on_save(self):
        name = self.name_entry.text().strip()
        if not name:
            self.dialog_label.setText("Please enter a name.")
            self.name_entry.setFocus()
            return
        if make_shortname(name) in self.existing_names:
            self.dialog_label.setText("Name already in use. Please choose something different.")
            self.name_entry.setFocus()
            return
        self.accept() # closes dialog when accepted

    def get_values(self):
        return (
            make_shortname(self.name_entry.text().strip()),
            self.name_entry.text().strip(),
            self.desc_entry.toPlainText().strip(),
            self.save_axis_settings.isChecked()
        )

    def bootstrap(self, parent= None):
        if self.exec() == qw.QDialog.DialogCode.Accepted: # close once the acceptance flag is flagged (in the on_save method)
            return self.get_values() #after that, grab the variables and return them
        return None
    
def make_shortname(display_name: str) -> str:
    s = display_name.lower()
    # replace spaces and punctuation with underscores
    s = re.sub(r"[^a-z0-9]+", "_", s)
    # collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s
