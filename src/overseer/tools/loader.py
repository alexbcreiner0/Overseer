from __future__ import annotations
import yaml
import numpy as np
import importlib.util
import shlex
import shutil
import os
from copy import deepcopy
from dataclasses import fields, is_dataclass, asdict, MISSING
from typing import get_origin, get_args, Any, Optional, Tuple, Type
from overseer.paths import MODELS_DIR
from pathlib import Path
import logging
import sys
import ast
from PyQt6 import (
    QtGui as qg,
    QtCore as qc
)
import subprocess

# from parameters import Params, params_from_mapping
logger = logging.getLogger(__name__)

def open_with_default_app(path: Path):
    url = qc.QUrl.fromLocalFile(str(path.resolve()))
    qg.QDesktopServices.openUrl(url)
    ok = qg.QDesktopServices.openUrl(url)

def open_in_known_editor(path: Path, name, env, preferred_editor=None, preferred_terminal=None):
    """ Absolute nightmare, I hate computers """
    is_windows = sys.platform == "win32"
    is_macos = sys.platform == "darwin"

    def win_appdata_local(*parts: str) -> str:
        base = os.environ.get("LOCALAPPDATA", "")
        return str(Path(base, *parts)) if base else ""

    def win_program_files(*parts: str) -> list[str]:
        out = []
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(var)
            if base:
                out.append(str(Path(base, *parts)))
        return out

    supported_editors = {
        "Sublime Text": {
            "terminal": False,
            "commands": (
                [
                    "sublime_text.exe",
                    "subl.exe",
                    *win_program_files("Sublime Text", "sublime_text.exe"),
                ]
                if is_windows else
                ["subl"]
            ),
        },
        "VSCode": {
            "terminal": False,
            "commands": (
                [
                    "Code.exe",
                    win_appdata_local("Programs", "Microsoft VS Code", "Code.exe"),
                    *win_program_files("Microsoft VS Code", "Code.exe"),
                    "code",   # fallback only
                ]
                if is_windows else
                ["code"]
            ),
        },
        "VSCodium": {
            "terminal": False,
            "commands": (
                [
                    "VSCodium.exe",
                    win_appdata_local("Programs", "VSCodium", "VSCodium.exe"),
                    *win_program_files("VSCodium", "VSCodium.exe"),
                    "codium",   # fallback only
                ]
                if is_windows else
                ["codium"]
            ),
        },
        "PyCharm": {
            "terminal": False,
            "commands": ["pycharm64.exe", "pycharm.exe"] if is_windows else ["pycharm"],
        },
        "IDLE": {
            "terminal": False,
            "commands": ["idle"] if not is_windows else ["idle.bat", "idle.pyw"],
        },
        "Vim":    { "terminal": True,  "commands": ["vim", "vi"] if not is_windows else ["vim.exe"] },
        "Emacs":  { "terminal": True,  "commands": ["emacs"] if not is_windows else ["emacs.exe"] },
        "Helix":  { "terminal": True,  "commands": ["hx"] if not is_windows else ["hx.exe"] },
        "Neovim": { "terminal": True,  "commands": ["nvim"] if not is_windows else ["nvim.exe"] },
        "Nano":   { "terminal": True,  "commands": ["nano"] if not is_windows else ["nano.exe"] },
    }

    fallback_order = [
        "Sublime Text",
        "VSCode",
        "VSCodium",
        "PyCharm",
        "IDLE",
        "Neovim",
        "Vim",
        "Emacs",
        "Helix",
        "Nano",
    ]

    folder_path = path.parent.resolve()
    file_path = (path / name / "simulation" / "simulation.py").resolve()

    def get_editor_args(editor_key: str) -> list[str]:
        if editor_key in {"Neovim", "Vim", "Nano", "IDLE"}:
            return [str(file_path)]
        elif editor_key == "Sublime Text":
            template = env.app_dir / "templates" / "new_model.sublime-project"
            dst = path.parent / f"models.sublime-project"
            if not dst.exists():
                shutil.copy2(template, dst)
            print(f"{["--project", str(dst), str(file_path)]=}")
            return ["--project", str(dst), str(file_path)]
        else:
            return [str(folder_path), str(file_path)]

    def resolve_executable(candidates: list[str]) -> str | None:
        for candidate in candidates:
            if not candidate:
                continue

            p = Path(candidate)
            if p.is_file():
                return str(p)

            found = shutil.which(candidate)
            if found:
                return found

        return None

    def try_launch_editor(editor_key: str) -> bool:
        editor_info = supported_editors[editor_key]
        args = get_editor_args(editor_key)
        uses_term = editor_info["terminal"]
        try:
            if is_macos:
                if uses_term:
                    exec_path = resolve_executable(editor_info["commands"])
                    if not exec_path:
                        return False

                    return launch_macos_terminal_command(
                            [exec_path, *args],
                            preferred_terminal
                    )

                mac_apps = {
                    "Sublime Text": "Sublime Text",
                    "VSCode": "Visual Studio Code",
                    "VSCodium": "VSCodium",
                    "PyCharm": "PyCharm",
                    "IDLE": "IDLE",
                }
                app_name = mac_apps.get(editor_key)
                if app_name:
                    subprocess.Popen(["open", "-a", app_name, "--args", *args])
                    return True

            exec_path = resolve_executable(editor_info["commands"])
            if not exec_path:
                print(f"Returning false because exec_path is None")
                return False

            args = get_editor_args(editor_key)
            uses_term = editor_info["terminal"]

            if uses_term:
                if preferred_terminal is None:
                    return False
                # You may want a separate Windows terminal strategy later
                terminal_parts = shlex.split(preferred_terminal)
                subprocess.Popen(terminal_parts + [exec_path] + args)
                # subprocess.Popen([preferred_terminal, exec_path, *args])
                return True

            popen_kwargs = {}

            if is_windows:
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            subprocess.Popen([exec_path, *args], **popen_kwargs)
            return True

        except Exception as e:
            logger.error(f"Failed to load editor {editor_key} ({exec_path}): {e}")
            return False

    if preferred_editor in supported_editors:
        if try_launch_editor(preferred_editor):
            return

    for editor in fallback_order:
        if try_launch_editor(editor):
            return

    logger.error("Failed to load any editor.")

def launch_macos_terminal_command(command_argv: list[str], preferred_terminal: str | None) -> bool:
    def applescript_string(s: str) -> str:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

    command_str = " ".join(shlex.quote(part) for part in command_argv)
    cmd_as_ascript = applescript_string(command_str)

    terminal_name_map = {
        "Terminal": "Terminal",
        "Terminal.app": "Terminal",
        "iTerm2": "iTerm",
        "iTerm": "iTerm",
        "iTerm.app": "iTerm",
    }

    app_name = terminal_name_map.get((preferred_terminal or "").strip(), "Terminal")

    try:
        if app_name in {"Terminal", "Terminal.app", "Apple Terminal"}:
            subprocess.Popen([
                "osascript",
                "-e", 'tell application "Terminal" to activate',
                "-e", f'tell application "Terminal" to do script {cmd_as_ascript}',
            ])
            return True

        if app_name in {"iTerm", "iTerm.app", "iTerm2", "iTerm 2"}:
            subprocess.Popen([
                "osascript",
                "-e", 'tell application "iTerm" to activate',
                "-e", 'tell application "iTerm" to create window with default profile',
                "-e", f'tell application "iTerm" to tell current session of current window to write text {cmd_as_ascript}',
            ])
            return True

        return False

    except Exception:
        return False


# def open_in_known_editor(path: Path, env, preferred_editor= None, preferred_terminal= None):
#     supported_editors = {
#         "Sublime Text": { "name": "subl", "terminal": False },
#         "VSCode": { "name": "code", "terminal": False },
#         "VSCodium": { "name": "codium", "terminal": False },
#         "PyCharm": { "name": "pycharm", "terminal": False },
#         "IDLE": { "name": "idle", "terminal": False },
#         "Vim": { "name": "vi", "terminal": True },
#         "Emacs": { "name": "emacs", "terminal": True },
#         "Helix": { "name": "hx", "terminal": True },
#         "Neovim": { "name": "nvim", "terminal": True },
#         "Nano": { "name": "nano", "terminal": True },
#     }

#     fallback_order = [
#         "Sublime Text",
#         "VSCode",
#         "VSCodium",
#         "PyCharm",
#         "IDLE",
#         "Neovim",
#         "Vim",
#         "Emacs",
#         "Helix",
#         "Nano",
#     ]

#     folder_path = (path / "simulation").resolve()
#     file_path = (folder_path / "simulation.py").resolve()

#     def get_editor_args(editor_name: str) -> list[str]:
#         if editor_name in {"nvim", "vi", "nano", "idle"}:
#             return [str(file_path)]
#         elif editor_name == "subl":
#             model_name = path.name
#             template = env.app_dir / "templates" / "new_model.sublime-project"
#             dst = path / f"{model_name}.sublime-project"
#             if not dst.exists():
#                 shutil.copy2(template, dst)
#             return ["--project", str(path / f"{model_name}.sublime-project"), str(file_path)]
#         else:
#             return [str(folder_path), str(file_path)]

#     def try_launch_editor(exe, uses_term):
#         args = get_editor_args(exe)

#         exec_path = qc.QStandardPaths.findExecutable(exe)
#         if exec_path:
#             if uses_term:
#                 if preferred_terminal is None:
#                     return False
#                 try:
#                     terminal_parts = shlex.split(preferred_terminal)
#                     subprocess.Popen(terminal_parts + [exec_path] + args)
#                     return True
#                 except Exception as e:
#                     logger.log(logging.ERROR, f"Failed to load editor {exe} using terminal command {preferred_terminal}: {e}")
#                     return False

#             try:
#                 subprocess.Popen([exec_path] + args)
#                 return True
#             except Exception as e:
#                 logger.log(logging.ERROR, f"Failed to load editor {exe}: {e}")
#                 return False

#     if preferred_editor is not None and preferred_editor in supported_editors:
#         exe = supported_editors[preferred_editor]["name"]
#         uses_term = supported_editors[preferred_editor]["terminal"]

#         if try_launch_editor(exe, uses_term):
#             return

#     for editor in fallback_order:
#         exe = supported_editors[editor]["name"]
#         uses_term = supported_editors[editor]["terminal"]

#         if try_launch_editor(exe, uses_term):
#             return

#     logger.log(logging.ERROR, "Failed to load any editor.")
#     return

def list_subdirs(path):
    return [
        p.name
        for p in Path(path).iterdir()
        if p.is_dir()
    ]

def load_parameters_class_from_file(parameters_py: str | Path):
    """
    Load the Parameters dataclass from a model's parameters.py without relying on it
    being importable as a package.
    """
    parameters_py = Path(parameters_py)
    if not parameters_py.exists():
        raise FileNotFoundError(parameters_py)

    spec = importlib.util.spec_from_file_location(f"model_parameters_{parameters_py.stem}", parameters_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec for {parameters_py}")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # executes the user's module

    if not hasattr(mod, "Params"):
        raise AttributeError(f"{parameters_py} does not define a Parameters class")

    Parameters = getattr(mod, "Params")
    if not is_dataclass(Parameters):
        raise TypeError("Parameters exists but is not a dataclass")

    return Parameters

def get_user_models_dir(settings: dict, env) -> Path:
    raw_text = settings.get("user_models_dir")
    if raw_text is None:
        return env.models_dir

    try:
        raw_text = settings.get("user_models_dir")
        candidate = Path(raw_text).expanduser().resolve(strict= False)
    except Exception:
        return env.models_dir

    if candidate.exists() and candidate.is_dir():
        return candidate

    return env.models_dir

def get_user_logs_dir(settings: dict, env) -> Path:
    raw_text = settings.get("user_logs_dir")
    if raw_text is None:
        return env.log_dir

    try:
        raw_text = settings.get("user_logs_dir")
        candidate = Path(raw_text).expanduser().resolve(strict= False)
    except Exception:
        return env.log_dir

    if candidate.exists() and candidate.is_dir():
        return candidate

    return env.log_dir

def try_instantiate_with_defaults(Parameters: Type[Any]) -> Tuple[Optional[Any], list[str]]:
    """
    Attempt Parameters() using defaults/default_factory.
    Returns (instance or None, list of missing-required field names).
    """
    missing = []
    for f in fields(Parameters):
        if f.default is MISSING and f.default_factory is MISSING:
            missing.append(f.name)

    if missing:
        return None, missing

    return Parameters(), []

def load_presets(env, path):
    with open(env.models_dir / path / "data" / "params.yml", 'r') as f:
        doc = yaml.safe_load(f)
    return doc["presets"]

def _dump_to_yaml(env, presets, path):
    class FlowDumper(yaml.SafeDumper):
        pass

    def _repr_list(dumper, data):
        # always use flow style for lists
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)

    FlowDumper.add_representer(list, _repr_list)
    FlowDumper.ignore_aliases = lambda *a, **k: True

    text = yaml.dump(
        {"presets": presets},
        Dumper=FlowDumper,
        sort_keys=False,
        indent=2,
        width=88
    )

    with open(env.models_dir / path / "data" / "params.yml", "w") as f:
        f.write(text)

class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True

def load_from_path(filepath, thing):
    spec = importlib.util.spec_from_file_location(thing, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # print(f"Attempting to load {thing} from module")
    cls = getattr(module, thing)
    return cls

def coerce_value(val, anno):
    """Best-effort coercion based on the dataclass field annotation."""
    if anno is None:
        return val

    # np.ndarray (common case)
    if anno is np.ndarray or getattr(anno, "__name__", "") == "ndarray":
        return np.asarray(val)

    # typing.Optional[T]
    origin = get_origin(anno)
    if origin is not None:
        args = get_args(anno)
        if origin is list:
            # List[T]
            inner = args[0] if args else None
            return [ coerce_value(v, inner) for v in (val or []) ]
        if origin is tuple:
            inner = args[0] if args else None
            return tuple(coerce_value(v, inner) for v in (val or []))
        if origin is dict:
            k_anno, v_anno = (args + (None, None))[:2]
            return { coerce_value(k, k_anno): coerce_value(v, v_anno) for k, v in (val or {}).items() }
        if origin is type(None):  # Optional[None]? ignore
            return val
        if origin is np.ndarray:  # rare typing usage
            return np.asarray(val)

    # Nested dataclass?
    if is_dataclass(anno):
        # If a nested dataclass appears, instantiate it from the dict
        sub_fields = {f.name: f for f in fields(anno)}
        kwargs = {}
        for k, v in (val or {}).items():
            if k in sub_fields:
                kwargs[k] = coerce_value(v, sub_fields[k].type)
        return anno(**kwargs)

    # Basic scalars
    if anno in (float, int, bool, str):
        try:
            return anno(val)
        except Exception:
            return val  # fall back

    return val  # default: no change

def params_from_mapping(map: dict, dataclass_path: str):
    Params = load_from_path(dataclass_path, "Params")
    
    params_fields = fields(Params)
    kwargs = {}
    if map is not None:
        for f in params_fields:
            if f.name in map:
                kwargs[f.name] = coerce_value(map[f.name], f.type)

    # field_names = {f.name for f in fields(Params)}
    # filtered = {k: v for k, v in map.items() if k in field_names}
    return Params(**kwargs)

def to_plain(obj): # opaque as fuck chatgpt code for converting the parameters dataclass to a yaml-friendly dictionary
    """Recursively convert dataclass / numpy types to YAML-friendly Python types."""
    if is_dataclass(obj):
        obj = asdict(obj)
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj

def format_plot_config(plotting_data: dict, runtime_names: list[str] | None = None) -> dict:
    data = deepcopy(plotting_data)

    if not runtime_names:
        return data

    # build a mapping like {"c0": "Corn", "c1": "Iron", ...}
    fmt = {f"c{i}": name for i, name in enumerate(runtime_names)}

    for cat_key, cat_dict in data.items():
        for plot_key, plot_dict in cat_dict.get("plots", {}).items():
            if plot_dict.get("label_template"):
                template = plot_dict.get("label_template")
                new_labels = []
                for name in runtime_names:
                    new_labels.append(template.format(i = name))
                plot_dict["labels"] = new_labels

            else:
                for i, label in enumerate(plot_dict.get("labels", [])):
                    plot_dict["labels"][i] = label.format(**fmt)

    return data

    # recursively format every string in the dict
    # def rec(x):
    #     if isinstance(x, str):
    #         try:
    #             return x.format(**fmt)
    #         except Exception:
    #             return x  
    #     if isinstance(x, list):
    #         return [rec(v) for v in x]
    #     if isinstance(x, dict):
    #         return {k: rec(v) for k, v in x.items()}
    #     return x

    # return rec(deepcopy(plotting_data))

def reload_package_folder(anchor_module):
    """
    Reload all modules located in the same directory as anchor_module.
    """
    anchor_file = Path(anchor_module.__file__).resolve()
    folder = anchor_file.parent

    to_reload = []
    for name, mod in list(sys.modules.items()):
        if not mod or not hasattr(mod, "__file__") or not mod.__file__:
            continue
        try:
            mod_path = Path(mod.__file__).resolve()
        except Exception:
            continue
        if mod_path.parent == folder:
            to_reload.append(name)

    # Reload dependencies first, anchor last
    for name in sorted(to_reload):
        importlib.reload(sys.modules[name])

def flow_seqify(data: dict) -> dict:
    """ Recursively reformat all list-like objects of a dictionary so that yaml.dump makes them look nice """
    new_data = {}
    for key, item in data:
        if isinstance(item, dict):
            new_data[key] = flow_seqify(item) # recurse on dicts
        elif isinstance(item, (list, tuple, np.ndarray)):
            new_list = _flow_seqify_list(item)
            new_data[key] = new_list
        else:
            new_data[key] = item

    return new_data

def _flow_seqify_list(ls: list | tuple | np.ndarray) -> list:
    new_list = []
    for thing in ls:
        if isinstance(thing, (list, tuple, np.ndarray)):
            new_thing = _flow_seqify_list(thing)
        else:
            new_thing = thing
        new_list.append(new_thing)

    return new_list

def get_top_level_function_names(py_file: Path) -> list[str]:
    source = py_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_file))

    names = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)
    return names


