from PyQt6 import QtWidgets as qw
from PyQt6 import QtCore as qc
import re
import os
import tempfile
from pathlib import Path
import yaml
from .HelpFormLayout import HelpFormLayout

class FormSection(qw.QGroupBox):
    """A tidy groupbox with a built-in form layout."""
    def __init__(self, title: str):
        super().__init__(title)
        self.form = HelpFormLayout(self)
        self.form.setFieldGrowthPolicy(qw.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setLabelAlignment(qc.Qt.AlignmentFlag.AlignRight)

def make_shortname(display_name: str) -> str:
    s = display_name.lower()
    # replace spaces and punctuation with underscores
    s = re.sub(r"[^a-z0-9]+", "_", s)
    # collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s

def replace_key_preserve_order(d: dict, old_key: str, new_key: str, new_val) -> None:
    """Replace old_key with new_key (and new_val) keeping existing iteration order."""
    if old_key == new_key:
        d[old_key] = new_val
        return

    new_d = {}
    for k, v in d.items():
        if k == old_key:
            new_d[new_key] = new_val
        else:
            new_d[k] = v
    d.clear()
    d.update(new_d)


