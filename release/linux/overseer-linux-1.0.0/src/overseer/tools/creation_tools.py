import os
from overseer.paths import APP_DIR, MODELS_DIR
import yaml
import numpy as np
from pathlib import Path
import tempfile

class FlowSeq(list):
    """A list that should be dumped in flow style (inline)"""
    pass

def flowseq_representer(dumper, data):
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq",
        data,
        flow_style=True,
    )

yaml.add_representer(FlowSeq, flowseq_representer, Dumper=yaml.SafeDumper)

def flow_seqify(data):
    """ Recursively reformat all list-like objects of a dictionary so that yaml.dump makes them look nice """
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = flow_seqify(value)
        return data

    if isinstance(data, np.ndarray):
        data = data.tolist()

    if isinstance(data, (list, tuple)):
        return FlowSeq(flow_seqify(thing) for thing in data)

    return data

def create_new_model_dir(env, name= None, gui_dialog= False):
    """ CLI new model creation function. Gets called also by the new model creation dialog in the GUI settings """
    if name is None:
        name = input("Model folder name: ")

    if os.path.isdir(name):
        if not gui_dialog:
            print("Folder already exists. Either rename it or delete it and try again.")
        return

    models_dir = env.models_dir
    app_dir = env.app_dir
    os.mkdir(models_dir / name)
    os.mkdir(models_dir / name / "data")
    os.mkdir(models_dir / name / "simulation")
    with open(models_dir / name / "__init__.py", "w"): pass
    with open(models_dir / name / "data" / "control_panel_data.yml", "w"): pass
    with open(models_dir / name / "data" / "plotting_data.yml", "w"): pass
    # TODO: this is a silly way to do this
    with (
        open(models_dir / name / "data" / "params.yml", "w") as fout,
        open(app_dir / "templates" / "params_dot_yml.txt", "r") as fin 
    ):
        print(fin.read(), file= fout)
    with open(models_dir / name / "simulation" / "__init__.py", "w"): pass
    with (
        open(models_dir / name / "simulation" / "parameters.py", "w") as fout,
        open(app_dir / "templates" / "parameters_dot_py.txt", "r") as fin
    ):
        print(fin.read(), file= fout)
    with (
        open(models_dir / name / "simulation" / "simulation.py", "w") as fout,
        open(app_dir / "templates" / "simulation_dot_py.txt", "r") as fin
    ):
        print(fin.read(), file= fout)

    if not gui_dialog:
        print("Done! Next steps are: \n 1. Fill in your simulation function in simulation/simulation.py",  
            "\n 2. Fill in your Params dataclass in simulation/parameters.py \n 3. Fill in your data/params.yml",
            "\n 4. Create and fill in your data/control_panel_data.yml file \n 5. Create and fill in your data/plotting_data.yml")
        print("A wizard currently exist for creating your plotting_data.yml file. Consider calling the new_plot_file() function next for that!")

def atomic_write(path: Path, new_text: str | dict) -> None:
    """ Authoritative and hopefully safe file replacement function """
    bak = path.with_suffix(".bak")

    # backup current on-disk bytes/text
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        with open(bak, "w", encoding="utf-8") as f:
            f.write(old)

    # atomic replace
    d = os.path.dirname(path) or "."
    base = os.path.basename(path)
    fd, tmp = tempfile.mkstemp(prefix=base + ".", suffix=".tmp", dir=d, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if isinstance(new_text, dict):
                yaml.safe_dump(new_text, f, sort_keys= False, allow_unicode= True)
            else:
                f.write(new_text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    if os.path.exists(bak):
        os.remove(bak)
