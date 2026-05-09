from PyQt6 import (
    QtWidgets as qw,
    QtGui as qg,
    QtCore as qc
) 
import yaml
from .tools.loader import get_user_models_dir, get_user_logs_dir
import sys, os, shutil
from .paths import APP_DIR, assets_path, anonymous_submission_mode_active, release_mode_active
from .bootstrap import bootstrap_user_environment
import logging, atexit
import logging.config
from logging.handlers import RotatingFileHandler
import threading
import multiprocessing as mp
import ctypes
import argparse

PLATFORM = sys.platform

# windows needs this for my app to appear as anything other than IDLE
if PLATFORM.startswith("win"):
    if anonymous_submission_mode_active(APP_DIR):
        myappid = "com.redacted.overseer"
    else:
        myappid = "com.alexcreiner.overseer"

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help= "Path to an alternative config.yml file.")

    return parser.parse_args()

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = logging.getLogger(__name__)
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def handle_thread_exception(args: threading.ExceptHookArgs):
    logging.getLogger(__name__).error(
        "Uncaught thread exception",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )

threading.excepthook = handle_thread_exception
sys.excepthook = handle_exception

from .MainWindow import MainWindow

def apply_dpi_scaled_font(app: qw.QApplication, base_pt: float = 10.0) -> None:
    screen = app.primaryScreen()
    if not screen:
        return
    dpi = screen.logicalDotsPerInch()  # ~96 at 100% scaling
    scale = dpi / 96.0

    f = app.font()
    f.setPointSizeF(base_pt * scale)
    app.setFont(f)

def apply_display_stuff(app):
    apply_dpi_scaled_font(app)
    app.setStyle("Fusion")
    platform = sys.platform
    if not platform == "darwin":
        icon_path = assets_path("icon.ico" if sys.platform.startswith("win") else "icon.png")
        app.setWindowIcon(qg.QIcon(str(icon_path)))
    app.setDesktopFileName("overseer")

    light_palette = qg.QPalette()

    light_palette.setColor(qg.QPalette.ColorRole.Window, qg.QColor(245, 245, 245))
    light_palette.setColor(qg.QPalette.ColorRole.WindowText, qc.Qt.GlobalColor.black)
    light_palette.setColor(qg.QPalette.ColorRole.Base, qg.QColor(255, 255, 255))
    light_palette.setColor(qg.QPalette.ColorRole.AlternateBase, qg.QColor(240, 240, 240))
    light_palette.setColor(qg.QPalette.ColorRole.Text, qc.Qt.GlobalColor.black)
    light_palette.setColor(qg.QPalette.ColorRole.Button, qg.QColor(240, 240, 240))
    light_palette.setColor(qg.QPalette.ColorRole.ButtonText, qc.Qt.GlobalColor.black)
    light_palette.setColor(qg.QPalette.ColorRole.Highlight, qg.QColor(76, 163, 224))
    light_palette.setColor(qg.QPalette.ColorRole.HighlightedText, qc.Qt.GlobalColor.white)

    app.setPalette(light_palette)

    # doesn't seem to work
    app.setStyleSheet("""
        QToolTip {
            max-width: 300px;
            white-space: normal;
        }
    """)

# TODO: move out of here, we should not be importing functions from an entrypoint like this
def reconfigure_logging(env, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "log.jsonl"

    with open(env.app_dir / "logging_config.yml", "r") as f:
        logging_config = yaml.safe_load(f)

    logging_config["handlers"]["app_file"]["filename"] = str(log_file)

    root = logging.getLogger()
    for handler in root.handlers[:]:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        root.removeHandler(handler)

    logging.config.dictConfig(logging_config)
    logging.captureWarnings(True)

    return log_file

def main():
    args = parse_args()
    env = bootstrap_user_environment(config_override= args.config)

    if not release_mode_active(APP_DIR):
        with open(env.config_file, "r") as f:
            settings = yaml.safe_load(f).get("global_settings", {})
    else:
        with open(env.config_dir / "config.example.yml", "r") as f:
            settings = yaml.safe_load(f).get("global_settings", {})            

    if not release_mode_active(APP_DIR):
        env.models_dir = get_user_models_dir(settings, env)
        env.log_dir = get_user_logs_dir(settings, env)
        env.log_dir.mkdir(parents=True, exist_ok=True)

    reconfigure_logging(env, env.log_dir)

    # mp.freeze_support()
    app = qw.QApplication(sys.argv)
    apply_display_stuff(app)

    app.setApplicationName("Overseer")
    app.setApplicationDisplayName("Overseer")

    window = MainWindow(env)

    if not PLATFORM == "darwin":
        icon_path = assets_path("icon.ico" if sys.platform.startswith("win") else "icon.png")
        window.setWindowIcon(qg.QIcon(str(icon_path)))

    window.showMaximized()
    app.exec()

if __name__ == "__main__":
    print("greetings!")
    main()
