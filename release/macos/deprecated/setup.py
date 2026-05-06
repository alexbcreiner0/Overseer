from setuptools import setup, find_packages
from pathlib import Path
import sys, shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

APP = [ str(HERE / "main.py") ]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "../../src/overseer/assets/icon.icns",
    "plist": {
        "CFBundleName": "Overseer",
        "CFBundleDisplayName": "Overseer",
        "CFBundleIdentifier": "com.alexcreiner.overseer",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "12.0",
    },
    "packages": [
        # TODO: This was the minimal set of packages to get it working properly. Scipy, mesa, and networkx were needed
        #       to get the modules loaded during startup. In the future I need to refactor that so that modules can be 
        #       loaded independently of whether or not the packages are installed in the app venv.
        "overseer",
        # NEEDED BY APP
        # "PyQt6",
        # "matplotlib",
        # "numpy",
        "scienceplots",
        # "pyyaml",
        # "platformdirs",
        # NEEDED BY SPECIFIC MODELS
        "scipy",
        "mesa",
        "networkx"
    ],
    "includes": [
        "sip",
    ],
    # "frameworks": [],
    "matplotlib_backends": ["QtAgg"],
    "arch": "arm64",
}

# setup(
#     app=APP,
#     name="Overseer",
#     options={"py2app": OPTIONS},
#     setup_requires=["py2app"],
# )

setup(
    app=APP,
    name="Overseer",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    packages=find_packages(where="../../../src"),
    package_dir={"": "../../../src"},
    include_package_data=True,
    package_data={
        "overseer": [
            "*",
            "assets/**/*",
            "defaults/**/*",
            "templates/**/*"
        ]
    },
)
