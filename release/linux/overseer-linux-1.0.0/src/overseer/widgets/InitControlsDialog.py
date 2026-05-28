from __future__ import annotations
from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc,
    QtGui as qg
)
import numpy as np  # ensure np.ndarray is available
from dataclasses import fields
from .HelpFormLayout import HelpFormLayout
from overseer.tools.loader import (
    load_parameters_class_from_file, 
    try_instantiate_with_defaults
)
from overseer.tools.creation_tools import (
    flow_seqify
)

class InitControlsDialog(qw.QDialog):
    """
    "One-click initializer" dialog:
      - shows params detected from the model preset/Parameters dataclass
      - allows include/exclude
      - generates basic defaults
    """
    def __init__(self, env, model_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Initialize Control Panel – {model_name}")
        self.resize(720, 520)

        self._model_name = model_name
        self._params_instance = None  # populated in _load_params()
        self._Parameters = None
        self._param_fields = {}
        self._missing_required = []
        self.env = env

        root = qw.QVBoxLayout(self)

        info = qw.QLabel(
            "Select which parameters to include. The initializer will generate a basic\n"
            "control panel layout (3 controls per row) you can refine afterwards."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.table = qw.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Include", "Name", "Type", "Shape"])
        self.table.horizontalHeader().setSectionResizeMode(0, qw.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, qw.QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, qw.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, qw.QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        # Defaults
        defaults_box = qw.QGroupBox("Defaults")
        form = HelpFormLayout(defaults_box)
        self.edit_divider_title = qw.QLineEdit("Parameters")
        self.edit_label_template = qw.QLineEdit("{name}=")
        self.numeric_min = qw.QLineEdit()
        self.numeric_min.setText("0.0")
        self.numeric_max = qw.QLineEdit()
        self.numeric_max.setText("1.0")

        label_template_help = "A string of text to accompany every control widget. Insert the placeholder {name} where you want the parameter to be substituted. For example, the default text will have your parameter name, followed by an equal sign, followed by the entry box for an entry widget. Alternatively, you could surround both sides of this with dollar signs to have the name displayed in LaTeX math mode font."

        form.addRow("Divider title:", self.edit_divider_title, help_text= "A title which appears at the top of your control panel. Mostly just there to look nice. You can place more dividers to group controls together later in the actual editor.")
        form.addRow("Label template:", self.edit_label_template, help_text= label_template_help)
        form.addRow("Numeric range min:", self.numeric_min, help_text= "For scalar ints and floats, a slider will be created along with a text box for entering the number. These two numbers specify the upper and lower bound for every slider. (You can change individual slider settings after finishing this initialization.) Non-numeric text will be ignored. If the app detects that your parameter is an int, but the number you enter is a float, it will be truncated automatically.")
        form.addRow("Numeric range max:", self.numeric_max)
        root.addWidget(defaults_box)

        btns = qw.QDialogButtonBox(
            qw.QDialogButtonBox.StandardButton.Ok | qw.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._load_params()

    def _load_params(self) -> None:
        try:
            Parameters = load_parameters_class_from_file(
                self.env.models_dir / self._model_name / "simulation" / "parameters.py"
            )
        except Exception as e:
            qw.QMessageBox.warning(self, "Parameters load error", str(e))
            return

        self._Parameters = Parameters
        self._param_fields = {f.name: f for f in fields(Parameters)}
        instance, missing = try_instantiate_with_defaults(Parameters)
        self._params_instance = instance
        self._missing_required = missing  # store if you want to display it

        self.table.setRowCount(0)

        for f in fields(Parameters):
            name = f.name
            typ = f.type
            shape = ""

            if instance is not None:
                try:
                    val = getattr(instance, name)
                    if isinstance(val, np.ndarray):
                        shape = str(val.shape)
                    elif isinstance(val, (int, float, bool, str)):
                        shape = ""
                except Exception:
                    pass

            row = self.table.rowCount()
            self.table.insertRow(row)

            chk = qw.QTableWidgetItem()
            chk.setFlags(chk.flags() | qc.Qt.ItemFlag.ItemIsUserCheckable)
            chk.setCheckState(qc.Qt.CheckState.Checked)
            self.table.setItem(row, 0, chk)

            self.table.setItem(row, 1, qw.QTableWidgetItem(name))
            self.table.setItem(row, 2, qw.QTableWidgetItem(getattr(typ, "__name__", str(typ))))
            self.table.setItem(row, 3, qw.QTableWidgetItem(shape))

        if missing:
            # Optional: show a non-blocking warning in the dialog
            # (still useful: you can generate scalar controls using default ranges even without instance)
            qw.QMessageBox.information(
                self,
                "Some parameters have no defaults",
                "Some dataclass fields have no default/default_factory, so Parameters() could not be instantiated.\n"
                "The initializer can still create controls, but array shapes / current values may be unknown for:\n\n"
                + ", ".join(missing),
            )

    def build_dividers(self):
        """
        Convert table selection + defaults into internal divider list.
        Wizard still defaults to 3 controls per row.
        Output schema: [{"title": str, "rows": [{"controls": [spec, ...]}, ...]}]
        """

        div_title = self.edit_divider_title.text().strip() or "Parameters"
        label_tmpl = self.edit_label_template.text() or ""
        rmin_text, rmax_text = self.numeric_min.text(), self.numeric_max.text()
        try:
            rmin = float(rmin_text)
            rmax = float(rmax_text)
        except ValueError:
            rmin = 0.0
            rmax = 1.0

        rows = []
        current = {"controls": []}

        def flush_row():
            nonlocal current
            if current["controls"]:
                rows.append(current)
            current = {"controls": []}

        # If we can't inspect params, still return a valid divider in the new shape
        if self._Parameters is None:
            return [{"title": div_title, "rows": [{"controls": []}]}]

        for row in range(self.table.rowCount()):
            include_item = self.table.item(row, 0)
            if include_item is None or include_item.checkState() != qc.Qt.CheckState.Checked:
                continue

            name_item = self.table.item(row, 1)
            if name_item is None:
                continue

            pname = name_item.text().strip()
            if not pname:
                continue

            val = None
            has_val = False
            if self._params_instance is not None:
                try:
                    val = getattr(self._params_instance, pname)
                    has_val = True
                except Exception:
                    has_val = False

            f = self._param_fields.get(pname)
            ann = None if f is None else f.type

            spec = {"param_name": pname, "tooltip": ""}

            if has_val:
                # since bools are also ints, this must go at top!
                if isinstance(val, bool):
                    spec["control_type"] = "checkbox"
                    spec["label"] = pname

                elif isinstance(val, (int, float)):
                    spec["control_type"] = "entry_block"
                    spec["type"] = "scalar"

                    if ann is float:
                        spec["scalar_type"] = "float"
                    elif ann is int:
                        spec["scalar_type"] = "int"
                    else:
                        spec["scalar_type"] = "int" if isinstance(val, int) else "float"

                    is_int = (spec["scalar_type"] == "int")
                    spec["range"] = flow_seqify([int(rmin) if is_int else rmin,
                                             int(rmax) if is_int else rmax])

                    # label template: support {name}
                    if label_tmpl in ["", "name"]:
                        spec["label"] = pname
                    elif "{name}" in label_tmpl:
                        spec["label"] = label_tmpl.replace("{name}", pname)

                elif isinstance(val, np.ndarray):
                    spec["control_type"] = "entry_block"
                    shape = val.shape
                    if len(shape) > 1:
                        spec["type"] = "matrix"
                        spec["dim"] = flow_seqify(list(shape))
                    else:
                        spec["type"] = "vector"
                        spec["dim"] = int(shape[0])

                    if label_tmpl in ["", "name"]:
                        spec["label"] = pname
                    elif "{name}" in label_tmpl:
                        spec["label"] = label_tmpl.replace("{name}", pname)

                elif isinstance(val, str):
                    spec["control_type"] = "dropdown"
                    spec["label"] = pname
                    spec["names"] = flow_seqify([val])
                    spec["values"] = flow_seqify([val])

            else:
                if ann is bool:
                    spec["control_type"] = "checkbox"
                    spec["label"] = pname

                elif ann is str:
                    spec["control_type"] = "dropdown"
                    spec["label"] = pname
                    spec["names"] = flow_seqify(["(set me)"])
                    spec["values"] = flow_seqify([""])

                elif ann is np.ndarray or (ann is not None and "ndarray" in str(ann)):
                    spec["control_type"] = "entry_block"
                    spec["type"] = "vector"
                    spec["dim"] = 1
                    spec["label"] = f"${pname}=$"

                else:
                    spec["control_type"] = "entry_block"
                    spec["type"] = "scalar"
                    spec["scalar_type"] = "float"
                    spec["range"] = flow_seqify([rmin, rmax])
                    spec["label"] = f"${pname}=$"

            current["controls"].append(spec)
            if len(current["controls"]) >= 3:
                flush_row()

        flush_row()
        div: DividerModel = {"title": div_title, "rows": rows if rows else [{"controls": []}]}
        return [div]

