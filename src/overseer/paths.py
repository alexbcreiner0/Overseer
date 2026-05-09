# paths.py
from pathlib import Path
from platformdirs import user_config_dir, user_data_dir, user_cache_dir
import sys
import os
from dataclasses import dataclass
import yaml

ENV_CONFIG = "OVERSEER_CONFIG"

def resolve_config(cli_config: str | None, default_config_file: Path) -> Path:
    print(f"{cli_config=}")
    print(f"{os.environ.get(ENV_CONFIG)=}")
    raw = cli_config or os.environ.get(ENV_CONFIG)
    if not raw:
        return default_config_file
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    return path

def release_mode_active(app_dir: Path) -> bool:
    """ looks for special global settings to determine how to unload """
    config_path = app_dir / "defaults" / "config.example.yml"
    with open(config_path, "r") as f:
        settings = yaml.safe_load(f).get("global_settings", {})

    return settings.get("paper_release_mode", False)

def anonymous_submission_mode_active(app_dir: Path) -> bool:
    with open(app_dir / "defaults" / "config.example.yml") as f:
        settings = yaml.safe_load(f).get("global_settings", {})

    return settings.get("anonymous_submission_mode", False)

APP_NAME = "Overseer"
APP_AUTHOR = False

# the path of the containing folder
APP_DIR = Path(__file__).resolve().parent
release_mode = release_mode_active(APP_DIR)

def assets_path(*parts: str) -> Path:
    return APP_DIR.joinpath("assets", *parts)

def defaults_path(*parts: str) -> Path:
    return APP_DIR.joinpath("defaults", *parts)

CACHE_DIR = Path(user_cache_dir(APP_NAME, APP_AUTHOR))

if release_mode:
    USER_APP_DIR = defaults_path()
    CONFIG_DIR = defaults_path()
    CONFIG_FILE = CONFIG_DIR / "config.yml"
else:
    USER_APP_DIR = Path.home() / "Documents" / "Overseer"
    CONFIG_DIR = Path(user_config_dir(APP_NAME, APP_AUTHOR, roaming= True)) 
    CONFIG_FILE = CONFIG_DIR / "config.yml"

MODELS_DIR = USER_APP_DIR / "models"
DEMOS_FILE = USER_APP_DIR / "demos.yml"
DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))
KEYBINDINGS_FILE = CONFIG_DIR / "keybindings.yml"
LOG_DIR = USER_APP_DIR / "logs" if not release_mode else DATA_DIR / "logs"

def ensure_dirs():
    """ create any missing directory """
    for d in [CONFIG_DIR, DATA_DIR, CACHE_DIR, LOG_DIR, MODELS_DIR]:
        d.mkdir(parents= True, exist_ok = True)

def app_path(*parts):
    return APP_DIR.joinpath(*parts)

def bundle_root() -> Path:
    """
    Root directory for bundled resources.
    Works in dev, onedir, and onefile.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent

# deprecated
def rpath(*parts: str) -> Path:
    """ very simple helper function to create paths throughout the app """
    return bundle_root().joinpath(*parts)

if __name__ == "__main__":
    print(f"{CONFIG_DIR=}")
    print(f"{DATA_DIR=}")
    print(f"{CACHE_DIR=}")
    print(f"{LOG_DIR=}")
    print(f"{MODELS_DIR=}")
    print(f"{APP_DIR=}")

