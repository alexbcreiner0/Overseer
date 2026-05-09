# src/overseer/bootstrap.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

ENV_CONFIG = "OVERSEER_CONFIG"

from .paths import (
    CONFIG_DIR,
    DATA_DIR,
    CACHE_DIR,
    LOG_DIR,
    MODELS_DIR,
    USER_APP_DIR,
    DEMOS_FILE,
    CONFIG_FILE,
    KEYBINDINGS_FILE,
    APP_DIR,
    defaults_path,
    ensure_dirs,
    resolve_config,
)

@dataclass
class BootstrapResult:
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    user_data_dir: Path
    log_dir: Path
    models_dir: Path
    config_file: Path
    demos_file: Path
    app_dir: Path

def copy_if_missing(src: Path, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

def copy_tree_if_missing(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    shutil.copytree(src, dst)

def initialize_dirs(src: Path, dst: Path) -> None:
    """
        non-destructively create any missing directories and populate them
    """
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
            else:
                initialize_dirs(item, target)
        else:
            if not target.exists():
                shutil.copy2(item, target)

def bootstrap_user_environment(config_override: str | None = None) -> BootstrapResult:
    ensure_dirs()

    try:
        active_config_file = resolve_config(config_override, CONFIG_FILE)
    except FileNotFoundError:
        print(f"Error: {config_override} not found.")
        active_config_file = CONFIG_FILE

    default_config = defaults_path("config.example.yml")
    default_demos = defaults_path("demos.example.yml")
    default_keybinds = defaults_path("keybindings.yml")
    default_models = defaults_path("models")

    if active_config_file == CONFIG_FILE  and not CONFIG_FILE.exists():
        copy_if_missing(default_config, CONFIG_FILE)

    if not DEMOS_FILE.exists():
        copy_if_missing(default_demos, DEMOS_FILE)

    if not KEYBINDINGS_FILE.exists():
        copy_if_missing(default_keybinds, KEYBINDINGS_FILE)

    if default_models.exists():
        initialize_dirs(default_models, MODELS_DIR)

    return BootstrapResult(
        config_dir=CONFIG_DIR,
        data_dir=DATA_DIR,
        cache_dir=CACHE_DIR,
        user_data_dir=USER_APP_DIR,
        log_dir=LOG_DIR,
        models_dir=MODELS_DIR,
        demos_file=DEMOS_FILE,
        config_file=active_config_file,
        app_dir=APP_DIR,
    )

# print(f"{CONFIG_DIR=}")
# print(f"{DATA_DIR=}")
# print(f"{CACHE_DIR=}")
# print(f"{LOG_DIR=}")
# print(f"{MODELS_DIR=}")
# print(f"{CONFIG_FILE=}")

