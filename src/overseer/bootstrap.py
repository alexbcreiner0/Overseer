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
    CONFIG_FILE,
    KEYBINDINGS_FILE,
    APP_DIR,
    defaults_path,
    ensure_dirs,
    resolve_config,
    release_mode
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
    app_dir: Path
    release_mode: bool

def copy_if_missing(src: Path, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

def copy_tree_if_missing(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    shutil.copytree(src, dst)

def bootstrap_user_environment(config_override: str | None = None) -> BootstrapResult:
    default_config = defaults_path("config.example.yml")
    default_keybinds = defaults_path("keybindings.yml")
    default_models = defaults_path("models")

    models_dir_already_existed = MODELS_DIR.exists()

    if release_mode:
        active_config_file = default_config
    else:
        ensure_dirs()
        try:
            active_config_file = resolve_config(
                config_override,
                CONFIG_FILE
            )
        except FileNotFoundError:
            print(f"Error: {config_override} not found.")
            active_config_file = CONFIG_FILE

    if active_config_file == CONFIG_FILE and not CONFIG_FILE.exists():
        copy_if_missing(default_config, CONFIG_FILE)

    if not KEYBINDINGS_FILE.exists():
        copy_if_missing(default_keybinds, KEYBINDINGS_FILE)

    if (
        default_models.exists()
        and not models_dir_already_existed
    ):
        shutil.copytree(
            default_models,
            MODELS_DIR,
            dirs_exist_ok=True,
        )

    return BootstrapResult(
        config_dir=CONFIG_DIR,
        data_dir=DATA_DIR,
        cache_dir=CACHE_DIR,
        user_data_dir=USER_APP_DIR,
        log_dir=LOG_DIR,
        models_dir=MODELS_DIR,
        config_file=active_config_file,
        app_dir=APP_DIR,
        release_mode=release_mode,
    )

if __name__ == "__main__":
    print(f"{bootstrap_user_environment().release_mode}")
# print(f"{CONFIG_DIR=}")
# print(f"{DATA_DIR=}")
# print(f"{CACHE_DIR=}")
# print(f"{LOG_DIR=}")
# print(f"{MODELS_DIR=}")
# print(f"{CONFIG_FILE=}")

