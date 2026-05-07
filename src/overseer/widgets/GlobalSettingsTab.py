from PyQt6 import QtWidgets as qw
import yaml
from .FilePicker import FilePicker
from pathlib import Path
import sys

from .common import FormSection

class GlobalSettingsTab(qw.QWidget):

    def __init__(self, env, parent):

        super().__init__(parent)
        self.env = env
        layout = qw.QVBoxLayout(self)

        sec = FormSection("Global settings")

        with open(self.env.config_file, "r") as f:
            global_settings = yaml.safe_load(f).get("global_settings")
            image_save_dir = global_settings.get("default_save_dir", str(Path.home()))
            save_name = global_settings.get("default_save_name", "figure")
            run_on_startup = global_settings.get("run_on_startup", True)
            autosave_axis_settings = global_settings.get("autosave_axis_settings", False)
            user_model_dir = global_settings.get("user_models_dir", str(env.models_dir))
            user_logs_dir = global_settings.get("user_logs_dir", str(env.log_dir))
            use_saved_cat_limits = global_settings.get("use_cat_limits", True)
            figure_mode = global_settings.get("figure_mode", "tight")
            preferred_editor = global_settings.get("preferred_editor", "Auto")
            if sys.platform == "win32":
                default_term = "powershell -NoExit "
            elif sys.platform == "darwin":
                default_term = "Apple Terminal"
            else:
                default_term = ""
            preferred_terminal = global_settings.get("preferred_terminal", default_term)

        # self.edit_default_save_dir = qw.QLineEdit(save_dir)
        # self.btn_browse_save_dir = qw.QToolButton()
        # self.btn_browse_save_dir.setText("…")

        self.edit_default_save_dir = FilePicker()
        self.edit_models_dir = FilePicker()
        self.edit_logs_dir = FilePicker()
        self.edit_default_save_dir.setText(image_save_dir)
        self.edit_models_dir.setText(user_model_dir)
        self.edit_logs_dir.setText(user_logs_dir)

        self.window = self.window()

        # save_dir_row = qw.QHBoxLayout()
        # save_dir_row.setContentsMargins(0, 0, 0, 0)
        # save_dir_row.addWidget(self.edit_default_save_dir, 1)
        # save_dir_row.addWidget(self.btn_browse_save_dir, 0)

        self.save_name = qw.QLineEdit(save_name)
        self.run_on_startup = qw.QCheckBox("Auto-run simulation on startup")
        self.autosave_axis_settings = qw.QCheckBox("Auto-save axis settings")
        self.use_cat_limits = qw.QCheckBox("Use saved limits when switching plot categories")
        self.run_on_startup.setChecked(run_on_startup)
        self.autosave_axis_settings.setChecked(autosave_axis_settings)
        self.use_cat_limits.setChecked(use_saved_cat_limits)

        self.preferred_editor = qw.QComboBox()
        preferred_editor_items = ["Auto", "Sublime Text", "VSCode", "VSCodium", "PyCharm", "IDLE", "Neovim", "Vim", "Nano", "Emacs", "Helix"]
        self.preferred_editor.addItems(preferred_editor_items)
        self.preferred_editor.setEditable(True)
        self.preferred_editor.setCurrentText(preferred_editor)

        self.preferred_terminal = qw.QComboBox()
        preferred_terminal_items = [
            "kitty -e ", "kitty -a ", "alacritty -e ", 
            "alacritty -a ", "wezterm start -- ", "gnome-terminal -- ", 
            "wt ", "powershell -NoExit ", "cmd /K ", "open -a Terminal ", 
            "Apple Terminal", "iTerm", "iTerm2"]
        self.preferred_terminal.setEditable(True)
        self.preferred_terminal.addItems(preferred_terminal_items)
        self.preferred_terminal.setCurrentText(preferred_terminal)

        figure_mode_radio_widget = qw.QWidget()
        figure_mode_radio_lay = qw.QHBoxLayout(figure_mode_radio_widget)
        self.figure_radio1 = qw.QRadioButton("Tight")
        self.figure_radio2 = qw.QRadioButton("Constrained")

        self.radio_group = qw.QButtonGroup(self)
        self.radio_group.addButton(self.figure_radio1, 1)
        self.radio_group.addButton(self.figure_radio2, 2)

        if figure_mode == "constrained":
            self.figure_radio2.setChecked(True)
        else:
            self.figure_radio1.setChecked(True)

        figure_mode_radio_lay.addWidget(self.figure_radio1)
        figure_mode_radio_lay.addWidget(self.figure_radio2)

        self.checkbox_row = qw.QWidget()

        self.checkbox_row_lay = qw.QHBoxLayout(self.checkbox_row)
        self.checkbox_row_lay.addWidget(self.run_on_startup)
        self.checkbox_row_lay.addWidget(self.autosave_axis_settings)
        self.checkbox_row_lay.addWidget(self.use_cat_limits)

        sec.form.addRow("Default image save directory:", self.edit_default_save_dir)
        sec.form.addRow("User models directory:", self.edit_models_dir)
        sec.form.addRow("Logging directory:", self.edit_logs_dir)
        help_text = "A template string for your save name to default to. Examples: \n \
                    'my_pic' will result in the save name defaulting to my_pic.png. \n \
                    'my_pic {a} {b}' will attempt to replace {a} and {b} with the values of the parameter named a and b in your model. \n \
                    'my_pic {a=}' will attempt to replace {a=} with the string 'a=<value of a>. So same as above except it titles the parameter with its name. \n \
                    'If a is not the name of a parameter in either of the above cases, then {a} will just be replaced with a in the name."
        sec.form.addRow("Default image save name:", self.save_name, help_text= help_text)
        sec.form.addRow("Preferred Editor/IDE:", self.preferred_editor, help_text = "If set to auto, order of precedence mirrors the order in which IDE's are shown in this list. Preferred editors which are entered manually and not in the list will be assumed to be CLI based and use the preferred terminal (see below).")
        sec.form.addRow("Preferred Terminal:", self.preferred_terminal, 
            help_text = "If your preferred editor is something which runs in a terminal like Vim or Neovim, \
                        you must specify a terminal to run it from. If your terminal doesn't appear on this list, \
                        you can type in the command to open it manually. If the command fails, Overseer will \
                        run down the list of preferred editors until it finds something that it can use on your computer. \
                        If it doesn't find anything, buttons attempting to use it will be unresponsive.")
        sec.form.addRow('', self.checkbox_row)
        sec.form.addRow("MatPlotLib figure mode:", figure_mode_radio_widget)

        # TODO: make apply/save actually work this way
        # hint = qw.QLabel(
        #     "Tip: use Apply to test changes without closing.\n"
        #     "Save writes the config file (you implement save_data())."
        # )
        # hint.setWordWrap(True)
        # hint.setStyleSheet("opacity: 0.85;")

        layout.addWidget(sec, 0)
        # layout.addWidget(hint, 0)
        layout.addStretch(1)

        # Browse button placeholder
        # self.btn_browse_save_dir.clicked.connect(self._browse_save_dir)

    def _wrap_layout(self, layout: qw.QLayout) -> qw.QWidget:
        w = qw.QWidget()
        w.setLayout(layout)
        return w

    def _browse_save_dir(self) -> None:
        # Optional convenience; you can remove if you don't want file dialogs
        path = qw.QFileDialog.getExistingDirectory(self, "Choose default save directory")
        if path:
            self.edit_default_save_dir.setText(path)
            self.window.status.show("Note: To actually apply the changes, you must first click Apply.", 2000)

    def get_settings_for_config(self):
        settings = {
            "save_name": self.save_name.text(),
            "run_on_startup": self.run_on_startup.isChecked(),
            "autosave_axis_settings": self.autosave_axis_settings.isChecked(),
            "use_cat_limits": self.use_cat_limits.isChecked(),
            "figure_mode": "tight" if self.radio_group.checkedId() == 1 else "constrained",
            "preferred_terminal": self.preferred_terminal.currentText(),
            "preferred_editor": self.preferred_editor.currentText()
        }
        if self.edit_models_dir.text() != self.env.models_dir and self.edit_models_dir.text():
            settings["user_models_dir"] = self.edit_models_dir.text()
        if self.edit_logs_dir.text() != self.env.log_dir and self.edit_logs_dir.text():
            settings["user_logs_dir"] = self.edit_logs_dir.text()
        if self.edit_default_save_dir.text() != str(Path.home()) and self.edit_default_save_dir.text():
            settings["default_save_dir"] = self.edit_default_save_dir.text()

        return settings
