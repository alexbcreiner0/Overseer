from __future__ import annotations

import os
import sys
from pathlib import Path

# Let Sphinx import the local package from src/ during local builds.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "Overseer"
author = "Alex Creiner"
copyright = "2026, Alex Creiner"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
]

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "templates"
]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
    "dollarmath",
    "amsmath",
]

html_static_path = ["_static"]

autosummary_generate = True
autodoc_typehints = "description"
