# .pyw files are meant to be entrypoints for GUI based python applications
# they are a way to run python programs or modules without a terminal popup
from pathlib import Path
import os
import subprocess
import sys

APP_ROOT = Path(__file__).resolve().parent
SRC_DIR = APP_ROOT / "src"
PYTHON_EXE = APP_ROOT / ".venv" / "Scripts" / "pythonw.exe"

if not PYTHON_EXE.exists():
    raise SystemExit(f"Missing virtualenv python: {PYTHON_EXE}")

env = os.environ.copy()
env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

subprocess.Popen(
    [str(PYTHON_EXE), "-m", "overseer", *sys.argv[1:]],
    cwd=str(APP_ROOT),
    env=env,
)
