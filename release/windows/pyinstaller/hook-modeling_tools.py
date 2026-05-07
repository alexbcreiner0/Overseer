# hook-overseer.py
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files(
    "oversseer",
    include_py_files=True,
    subdir="defaults/models"
)
