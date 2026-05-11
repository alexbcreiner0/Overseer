from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path
from .PlotSettingsTab import PlotSettingsTab
from .DemoSettingsTab import DemoSettingsTab
from .GlobalSettingsTab import GlobalSettingsTab
from .ControlSettingsTab import ControlSettingsTab
from .ParamSettingsTab import ParamSettingsTab
from .PresetSettingsTab import PresetSettingsTab
from .ModelSettingsTab import ModelSettingsTab
from .common import refresh_models
from overseer.paths import MODELS_DIR, CONFIG_FILE

from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)

class StatusBar(qw.QStatusBar):
    """QStatusBar that auto-clears messages after a timeout by default."""
    def show(self, msg: str, timeout_ms: int = 5000) -> None:
        self.showMessage(msg, timeout_ms)

class EditConfigDialog(qw.QDialog):

    configApplied = qc.pyqtSignal()

    def __init__(self, env, model: str = None, tab: int = 0, parent: Optional[qw.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Config")
        self.resize(1300, 640)

        root = qw.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.env = env

        body = qw.QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        nav_box = qw.QGroupBox("Settings and Utilities")
        nav_layout = qw.QVBoxLayout(nav_box)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_box.setSizePolicy(qw.QSizePolicy.Policy.Preferred, qw.QSizePolicy.Policy.Expanding)

        self.nav = qw.QListWidget()
        self.nav.setSpacing(2)
        self.nav.addItem("Application Settings")
        self.nav.addItem("Model Settings")
        self.nav.addItem("Parameter Settings")
        self.nav.addItem("Preset Settings")
        self.nav.addItem("Control Settings")
        self.nav.addItem("Plot Settings")
        self.nav.addItem("Demo Settings")

        self.status = StatusBar()
        self.status.setSizeGripEnabled(False)

        nav_layout.addWidget(self.nav, 1)
        body.addWidget(nav_box, 0)

        self.stack = qw.QStackedWidget()
        body.addWidget(self.stack, 1)

        self.page_global = GlobalSettingsTab(self.env, self)
        self.page_models = ModelSettingsTab(self.env, model, self)
        self.page_params = ParamSettingsTab(self.env, model, self)
        self.page_presets = PresetSettingsTab(self.env, model, self)
        self.page_controls = ControlSettingsTab(self.env, model, self)
        self.page_plots = PlotSettingsTab(self.env, model, self)
        self.page_demos = DemoSettingsTab(self.env, self)

        self.settings = self.page_global.get_settings_for_config()

        self._syncing_model = False

        self._current_model: Optional[str] = model
        self.stack.addWidget(self.page_global)
        self.stack.addWidget(self.page_models)
        self.stack.addWidget(self.page_params)
        self.stack.addWidget(self.page_presets)
        self.stack.addWidget(self.page_controls)
        self.stack.addWidget(self.page_plots)
        self.stack.addWidget(self.page_demos)

        self.idx_to_page = {
            0: self.page_global,
            1: self.page_models,
            2: self.page_params,
            3: self.page_presets,
            4: self.page_controls,
            5: self.page_plots,
            6: self.page_demos
        }

        self.idx_to_name = {
            0: "global",
            1: "models",
            2: "params",
            3: "presets",
            4: "controls",
            5: "plots",
            6: "demos"
        }

        self.page_plots.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.page_controls.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.page_params.availableParamsChanged.connect(self.page_controls.set_available_params)
        self.page_params.paramSettingsChanged.connect(self.page_presets.refresh_rows)
        self.page_params.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.page_presets.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.page_models.newModelCreated.connect(self.page_demos._refresh_models)
        self.page_models.model_list.currentTextChanged.connect(self._on_model_changed)
        self.page_models.modelsChanged.connect(self._refresh_model_combos)

        bottom = qw.QHBoxLayout()
        root.addLayout(bottom, 0)

        # Put status bar in a container so it doesn't stretch weirdly
        status_wrap = qw.QWidget()
        status_wrap_layout = qw.QVBoxLayout(status_wrap)
        status_wrap_layout.setContentsMargins(0, 0, 0, 0)
        status_wrap_layout.addWidget(self.status)
        bottom.addWidget(status_wrap, 1)

        self.buttons = qw.QDialogButtonBox()
        self.btn_apply = self.buttons.addButton("Apply", qw.QDialogButtonBox.ButtonRole.ApplyRole)
        self.btn_save = self.buttons.addButton("Save", qw.QDialogButtonBox.ButtonRole.ActionRole)
        self.btn_close = self.buttons.addButton(qw.QDialogButtonBox.StandardButton.Close)
        bottom.addWidget(self.buttons, 0)

        for b in (self.btn_apply, self.btn_save, self.btn_close):
            b.setDefault(False)
            b.setAutoDefault(False)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.btn_close.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_save.clicked.connect(self._on_save_clicked)

        self.stack.setCurrentIndex(tab)
        self.nav.setCurrentRow(tab)

        if model is not None:
            self._on_model_changed(model)


    def bootstrap(self, parent= None):
        self.show()
        self.raise_()
        self.activateWindow()
        # if self.exec() == qw.QDialog.DialogCode.Accepted: # close once the acceptance flag is flagged (in the on_save method)
        #     return 1
        # else:
        #     return 0

    def _current_model_name(self) -> Optional[str]:
        """Best-effort current model name across tabs."""
        # Prefer the Models tab selection if present
        m = getattr(self.page_models, "_current_model", None)
        if m:
            return str(m).strip() or None

        # Fall back to any per-model combo box that exists
        for page in (self.page_plots, self.page_controls, self.page_params, self.page_presets):
            combo = getattr(page, "model_combo", None)
            if combo is not None:
                try:
                    txt = combo.currentText().strip()
                    if txt:
                        return txt
                except Exception:
                    pass
        return None

    def _on_apply_clicked(self) -> None:
        model = self._current_model_name()
        if model:
            self._current_model = model
            self._on_model_changed(model)

        tab = self.idx_to_page[self.stack.currentIndex()]
        tab.on_apply_clicked()

        # I don't remember what this is for?
        self.settings = self.page_global.get_settings_for_config()

        self.configApplied.emit()

    def _on_save_clicked(self) -> None:
        self._on_apply_clicked()
        self.accept()

    # def _refresh_models(self):
    #     models = []
    #     potential_models = list_subdirs(self.env.models_dir, actual_paths= True)
        
    #     for pot_model in potential_models:
    #         init_path = pot_model / "__init__.py"
    #         if init_path.exists():
    #             models.append(pot_model.name)

    #     return models

    def _on_model_changed(self, model_name: str):
        if self._syncing_model:
            return

        self._syncing_model = True
        try:
            self._current_model = (model_name or '').strip() or None
            self.page_plots.set_model(model_name)
            self.page_controls.set_model(model_name)
            self.page_params.set_model(model_name)
            self.page_presets.set_model(model_name)
            self.page_models.set_model(model_name)
        finally:
            self._syncing_model = False

    def _refresh_model_combos(self) -> None:
        """Refresh model selectors in the per-model tabs.

        Triggered when the Models tab detects that the on-disk model list changed
        (e.g., after creating a new model).
        """
        for page in (self.page_plots, self.page_controls, self.page_params, self.page_presets):
            try:
                page._refresh_models()
            except Exception:
                pass

        # If current model disappeared, fall back to first available.
        try:
            models = refresh_models(self.env)
            if models:
                cur = None
                if getattr(self.page_plots, "model_combo", None) is not None:
                    cur = self.page_plots.model_combo.currentText().strip()
                if cur and cur in models:
                    return
                self._on_model_changed(models[0])
        except Exception:
            pass

if __name__ == "__main__":
    pass
