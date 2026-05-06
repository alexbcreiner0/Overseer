from PyQt6 import QtWidgets as qw, QtCore as qc

class AxesControlWidget(qw.QWidget):
    """
    Composite widget:
      [Save] [Load]   X: [x_min] to [x_max]   Y: [y_min] to [y_max]

    - settingsChanged: emitted whenever the current limits should be applied
                       (editingFinished on any line edit OR after Load).
    """
    settingsChanged = qc.pyqtSignal()
    catSettingsChanged = qc.pyqtSignal()

    def __init__(self, z_axis= False, saved_limits= None, parent=None):
        super().__init__(parent)

        outer_outer = qw.QVBoxLayout(self)
        outer_outer.setContentsMargins(1,0,1,0)
        outer_outer.setSpacing(2)

        outer = qw.QHBoxLayout()
        outer.setContentsMargins(0,0,8,0)
        outer.setSpacing(10)

        entries = qw.QVBoxLayout()
        entries.setContentsMargins(0,1,0,1)
        entries.setSpacing(0)

        top_entries = qw.QHBoxLayout()
        top_entries.setContentsMargins(0, 1, 0, 1)
        top_entries.setSpacing(8)

        self.is_3d = z_axis

        self.save_button = qw.QPushButton("Store Current View")
        self.load_button = qw.QPushButton("Load Stored View")
        self.save_category_button = qw.QPushButton("Save View as Default")

        self.xmin_edit = qw.QLineEdit()
        self.xmax_edit = qw.QLineEdit()
        self.ymin_edit = qw.QLineEdit()
        self.ymax_edit = qw.QLineEdit()
        self.zmin_edit = qw.QLineEdit()
        self.zmax_edit = qw.QLineEdit()

        for edit in (self.xmin_edit, self.xmax_edit, self.ymin_edit, self.ymax_edit, self.zmin_edit, self.zmax_edit):
            # edit.setMaximumWidth(70)
            edit.textChanged.connect(self._on_editing_finished)

        top_entries.addSpacing(8)
        top_entries.addWidget(qw.QLabel("X-axis from:"), stretch= 0)
        top_entries.addWidget(self.xmin_edit, alignment= qc.Qt.AlignmentFlag.AlignLeft)
        top_entries.addWidget(qw.QLabel("to"), stretch= 0)
        top_entries.addWidget(self.xmax_edit, alignment= qc.Qt.AlignmentFlag.AlignLeft)

        self.xmin_edit.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)
        self.ymin_edit.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)

        self.xmax_edit.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)
        self.ymax_edit.setSizePolicy(qw.QSizePolicy.Policy.Expanding, qw.QSizePolicy.Policy.Preferred)

        entries.addLayout(top_entries)

        bottom_entries = qw.QHBoxLayout()
        bottom_entries.setContentsMargins(0,0,0,0)
        bottom_entries.setSpacing(8)

        bottom_entries.addSpacing(8)
        bottom_entries.addWidget(qw.QLabel("Y-axis from:"), stretch= 0)
        bottom_entries.addWidget(self.ymin_edit, alignment = qc.Qt.AlignmentFlag.AlignLeft)
        bottom_entries.addWidget(qw.QLabel("to"), stretch= 0)
        bottom_entries.addWidget(self.ymax_edit, alignment = qc.Qt.AlignmentFlag.AlignLeft)

        entries.addLayout(bottom_entries)

        self.z_row = qw.QWidget()
        z_layout = qw.QHBoxLayout(self.z_row)
        z_layout.setContentsMargins(0,0,0,0)
        z_layout.setSpacing(8)

        z_layout.addSpacing(8)
        z_layout.addWidget(qw.QLabel("Z-axis from:"), stretch= 0)
        z_layout.addWidget(self.zmin_edit, alignment = qc.Qt.AlignmentFlag.AlignLeft)
        z_layout.addWidget(qw.QLabel("to"), stretch= 0)
        z_layout.addWidget(self.zmax_edit, alignment = qc.Qt.AlignmentFlag.AlignLeft)

        entries.addWidget(self.z_row)

        save_load_button = qw.QWidget()
        save_load_button_lay = qw.QHBoxLayout(save_load_button)
        save_load_button_lay.setContentsMargins(0,0,0,0)
        save_load_button_lay.setSpacing(2)
        save_load_button_lay.addWidget(self.save_button)
        save_load_button_lay.addWidget(self.load_button)
        save_load_button_lay.addWidget(self.save_category_button)

        coords = qw.QVBoxLayout()
        coords.setContentsMargins(0,0,0,0)
        coords.setSpacing(2)

        top_coords = qw.QHBoxLayout()
        top_coords.setContentsMargins(0,0,0,0)
        top_coords.setSpacing(2)

        bottom_coords = qw.QHBoxLayout()
        bottom_coords.setContentsMargins(0,0,0,0)
        bottom_coords.setSpacing(2)

        # top_coords.addWidget(self.save_button)
        # bottom_coords.addWidget(self.load_button)

        self.saved_x_label = qw.QLabel("Stored X: -")
        self.saved_y_label = qw.QLabel("Stored Y: -")
        self.saved_z_label = qw.QLabel("Stored Z: -")

        self.z_saved_row = qw.QWidget()

        z_saved_layout = qw.QHBoxLayout(self.z_saved_row)
        z_saved_layout.setContentsMargins(0,0,0,0)
        z_saved_layout.setSpacing(2)
        z_saved_layout.addWidget(self.saved_z_label, alignment= qc.Qt.AlignmentFlag.AlignRight)

        top_coords.addWidget(self.saved_x_label, alignment= qc.Qt.AlignmentFlag.AlignRight)
        bottom_coords.addWidget(self.saved_y_label, alignment= qc.Qt.AlignmentFlag.AlignRight)

        # bottom_entries.addStretch(1)

        coords.addLayout(top_coords)
        coords.addLayout(bottom_coords)
        coords.addWidget(self.z_saved_row)

        outer.addLayout(entries)
        outer.addLayout(coords)

        outer_outer.addLayout(outer)
        outer_outer.addWidget(save_load_button)

        # per-widget saved limits
        if saved_limits is not None and isinstance(saved_limits, tuple) and len(saved_limits) >= 2:
            self._saved_xlim = saved_limits[0]
            self._saved_ylim = saved_limits[1]
        else:
            self._saved_xlim = None
            self._saved_ylim = None
        if saved_limits is not None and isinstance(saved_limits, tuple) and len(saved_limits) >= 3:
            self._saved_zlim = saved_limits[2]
        else:
            self._saved_zlim = None
        self._update_saved_labels()

        self.save_button.clicked.connect(self._on_save_clicked)
        self.load_button.clicked.connect(self._on_load_clicked)
        self.save_category_button.clicked.connect(self._on_save_cat_clicked)

        self._update_z_visibility()

    def set_projection(self, dim: str) -> None:
        new_state = (dim == "3d")

        if new_state == self.is_3d:
            return

        self.is_3d = new_state
        self._update_z_visibility()

    def _update_z_visibility(self):
        self.z_row.setVisible(self.is_3d)
        self.z_saved_row.setVisible(self.is_3d)

    def get_limits(self):
        """
        Returns (xlim, ylim) where each is a (min, max) tuple of floats,
        or None if parsing fails.
        """
        try:
            x0 = float(self.xmin_edit.text())
            x1 = float(self.xmax_edit.text())
            y0 = float(self.ymin_edit.text())
            y1 = float(self.ymax_edit.text())
            if self.is_3d:
                z0 = float(self.zmin_edit.text())
                z1 = float(self.zmax_edit.text())
        except ValueError:
            return None

        if self.is_3d:
            return (x0, x1), (y0, y1), (z0, z1)
        else:
            return (x0, x1), (y0, y1)

    def get_saved_limits(self):
        if self.is_3d:
            return self._saved_xlim, self._saved_ylim, self._saved_zlim
        else:
            return self._saved_xlim, self._saved_ylim

    def set_limits(self, xlim, ylim, zlim= None):
        """
        Programmatically update the line edits to match given limits.
        """
        if zlim is not None:
            (x0, x1), (y0, y1), (z0, z1) = xlim, ylim, zlim
        else:
            (x0, x1), (y0, y1) = xlim, ylim

        edits = (
            (self.xmin_edit, x0),
            (self.xmax_edit, x1),
            (self.ymin_edit, y0),
            (self.ymax_edit, y1),
        )
        if zlim is not None:
            more_edits = (
                (self.zmin_edit, z0),
                (self.zmax_edit, z1),
            )
            edits += more_edits
        for edit, val in edits:
            edit.blockSignals(True)
            edit.setText(f"{val:g}")
            edit.blockSignals(False)

    # ---- internal handlers ----
    def _update_saved_labels(self):
        if self._saved_xlim is None or self._saved_ylim is None:
            self.saved_x_label.setText("Stored X: –")
            self.saved_y_label.setText("Stored Y: –")
            if self._saved_zlim is not None:
                self.saved_z_label.setText("Stored Z: -")
        else:
            x0, x1 = self._saved_xlim
            y0, y1 = self._saved_ylim
            self.saved_x_label.setText(f"Stored X: ({x0:g}, {x1:g})")
            self.saved_y_label.setText(f"Stored Y: ({y0:g}, {y1:g})")
            if self._saved_zlim is not None:
                z0, z1 = self._saved_zlim
                self.saved_z_label.setText(f"Stored Z: ({z0:g}, {z1:g})")

    def _on_editing_finished(self):
        # Whenever user finishes editing any box, tell the outside world
        self.settingsChanged.emit()

    def _on_save_clicked(self):
        limits = self.get_limits()
        if limits is None:
            return

        if self.is_3d:
            self._saved_xlim, self._saved_ylim, self._saved_zlim = limits
        else:
            self._saved_xlim, self._saved_ylim = limits
        self._update_saved_labels()
        # optional: also emit settingsChanged so that whatever is currently
        # in the boxes definitely gets applied to the plot.
        self.settingsChanged.emit()

    def _on_save_cat_clicked(self):
        print("Save cat clicked, emitting.")
        self.catSettingsChanged.emit()

    def _on_load_clicked(self):
        if self.is_3d:
            if self._saved_xlim is None or self._saved_ylim is None or self._saved_zlim is None:
                return
            self.set_limits(self._saved_xlim, self._saved_ylim, self._saved_zlim)
        else:
            if self._saved_xlim is None or self._saved_ylim is None:
                return
            self.set_limits(self._saved_xlim, self._saved_ylim)

        # After loading from saved limits, apply them to the plot:
        self.settingsChanged.emit()
