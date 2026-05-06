import yaml
import os, importlib, inspect
import pprint
import subprocess
from pathlib import Path
from paths import rpath
from tools.loader import load_presets, params_from_mapping
from dataclasses import fields
from numpy import ndarray
# This mostly contains wizards for creating new simulations.
# WARNING: THESE EXISTED BEFORE I CREATED A DEDICATED GUI SETTINGS MENU.
# WARNING: NEARLY EVERYTHING HERE IS VERY DEPRECATED AND UNSAFE TO USE. DO NOT USE THESE FUNCTIONS.

def list_subdirs(path):
    return [
        p.name
        for p in Path(path).iterdir()
        if p.is_dir()
    ]

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

# still used
def create_new_model_dir(name= None, gui_dialog= False):

    if name is None:
        name = input("Model folder name: ")

    if os.path.isdir(name):
        if not gui_dialog:
            print("Folder already exists. Either rename it or delete it and try again.")
        return

    os.mkdir(rpath("models", name))
    os.mkdir(rpath("models", name, "data"))
    os.mkdir(rpath("models", name, "simulation"))
    with open(rpath("models", name, "__init__.py"), "w"): pass
    with open(rpath("models", name, "data", "control_panel_data.yml"), "w"): pass
    with open(rpath("models", name, "data", "plotting_data.yml"), "w"): pass
    with (
        open(rpath("models", name, "data", "params.yml"), "w") as fout,
        open(rpath("templates", "params_dot_yml.txt")) as fin
    ):
        print(fin.read(), file= fout)
    with open(rpath("models", name, "simulation", "__init__.py"), "w"): pass
    with (
        open(rpath("models", name, "simulation", "parameters.py"), "w") as fout,
        open(rpath("templates", "parameters_dot_py.txt"), "r") as fin
    ):
        print(fin.read(), file= fout)
    with (
        open(rpath("models", name, "simulation", "simulation.py"), "w") as fout,
        open(rpath("templates", "simulation_dot_py.txt"), "r") as fin
    ):
        print(fin.read(), file= fout)

    with open(rpath("config.yml"), "r") as f:
        data = yaml.safe_load(f)

    with open(rpath("config.yml"), "w") as f:
        data = _normalize_flowseqs_for_dump(data)
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    if not gui_dialog:
        print("Done! Next steps are: \n 1. Fill in your simulation function in simulation/simulation.py",  
            "\n 2. Fill in your Params dataclass in simulation/parameters.py \n 3. Fill in your data/params.yml",
            "\n 4. Create and fill in your data/control_panel_data.yml file \n 5. Create and fill in your data/plotting_data.yml")
        print("A wizard currently exist for creating your plotting_data.yml file. Consider calling the new_plot_file() function next for that!")


def _normalize_flowseqs_for_dump(data: dict) -> dict:
    demos = data.get("demos", {})
    for _k, demo in demos.items():
        if not isinstance(demo, dict):
            continue
        details = demo.get("details")
        if not isinstance(details, dict):
            continue

        lims = details.get("starting_lims")
        if not lims:
            continue

        # expecting [[x0, x1], [y0, y1]]
        if (
            isinstance(lims, (list, tuple))
            and len(lims) == 2
            and all(isinstance(row, (list, tuple)) and len(row) == 2 for row in lims)
        ):
            x = [float(lims[0][0]), float(lims[0][1])]
            y = [float(lims[1][0]), float(lims[1][1])]
            details["starting_lims"] = FlowSeq([FlowSeq(x), FlowSeq(y)])

    return data

def _add_plot_category(sim_name, yaml_name, name, title= None, x_label= None, y_label= None, tooltip= None, plots= None):

    with open(rpath("models", sim_name, "data", "plotting_data.yml"), "r") as f:
        data = yaml.safe_load(f)

    if data is None: data = {}

    with open(rpath("models", sim_name, "data", "plotting_data_bak.yml"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    data[yaml_name] = {
        "name": name,
        "title": title,
        "x_label": x_label,
        "y_label": y_label,
        "tooltip": tooltip,
        "plots": plots
    }

    with open(rpath("models", sim_name, "data", "plotting_data.yml"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    os.remove(rpath("models", sim_name, "data", "plotting_data_bak.yml"))
    print(f"Done adding category {name} to {sim_name}")

def _add_plot(sim_name, name, labels, category, traj_key, toggled= False, checkbox_name= None, linestyle= "solid", colors= ["red", "green", "blue"]):

    with open(rpath("models", sim_name, "data", "plotting_data.yml"), "r") as f:
        data = yaml.safe_load(f)

    with open(rpath("models", sim_name, "data", "plotting_data_bak.yml"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    n = len(labels)
    colors = colors[0:n]
        
    plot_dict = {
        "labels": labels,
        "traj_key": traj_key,
        "toggled": toggled,
        "colors": colors,
        "linestyle": linestyle
    }

    if checkbox_name is not None:
        plot_dict["checkbox_name"] = checkbox_name
        plot_dict["toggled"] = toggled

    if data[category]["plots"] is None: data[category]["plots"] = {}

    data[category]["plots"][name] = plot_dict

    with open(rpath("models", sim_name, "data", "plotting_data.yml"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    os.remove(rpath("models", sim_name, "data", "plotting_data_bak.yml"))
    print(f"Done adding plot {name} to {sim_name}.")

def _get_new_plot_category_info() -> dict:
    output = {}

    correct = False
    while not correct:
        output["yaml_name"] = input("Internal name for category (no whitespace): ")
        output["name"] = input("Actual name for category (what the user will see): ")
        x_label_ans = input("x-axis title (leave blank for the default 'Time [t]'): ")
        output["x_label"] = "Time [t]" if not x_label_ans else x_label_ans
        y_label_ans = input("y-axis title (leave blank for a blank y-axis (e.g. rates or heterogeneous units)): ")
        output["y_label"] = None if not y_label_ans else y_label_ans
        tooltip_ans = input("Tooltip (any info you want the user to be able to see when hovering over the ? button). Leaving blank is fine: )")
        output["tooltip"] = None if not tooltip_ans else tooltip_ans

        print(f"Here is what you entered: ")
        pprint.pprint(output)
        feedback = input("Does this all look correct? (y/n) ")
        if feedback == "y": correct = True
            
    return output

def _get_new_plot_info(category= None) -> dict:
    output = {}

    correct = False
    while not correct:
        output["name"] = input("Plot name (internal, not for user): ")
        labels = []
        ans = input("Are you plotting a vector trajectory? (y/n) ")
        if ans.lower() == "y":
            done = False
            print("Type label names one at a time, or 'done' to finish.")
            i = 1
            while not done:
                string = input(f"Label {i}: ")
                if string.lower() == "done":
                    done = True
                    continue
                labels.append(string)
                i += 1
        else:
            labels.append(input("Name of plot (appears on legend): "))
        output["labels"] = labels
        if category is None:
            output["category"] = input("Category name (dropdown group) (case sensitive): ")
        else:
            output["category"] = category
        toggleable_answer = input("Toggleable? (y for yes, anything else to skip): ")
        toggleable = True if toggleable_answer == "y" else False
        if toggleable:
            output["checkbox_name"] = input("Checkbox name (press enter to skip): ")
            toggled_answer = input("Pre-toggled? y for yes, anything else for no: ")
            output["toggled"] = True if toggled_answer == "y" else False

        output["traj_key"] = input("Trajectory key: ")
        linestyle_answer = input("Linestyle (leave blank for solid, otherwise da for dashed and do for dotted: ")
        if linestyle_answer == "da":
            output["linestyle"] = "dashed"
        elif linestyle_answer == "do":
            output["linestyle"] = "dotted"
        else:
            output["linestyle"] = "solid"

        colors = []
        if len(labels) == 1:
            color = input("Color of plot (Basic names and hex codes are both accepted. Hex codes should begin with #): ")
            colors.append(color)
        else:
            print("Enter colors for your plots. Basic names and hex codes are both accepted. Hex codes should begin with #")
            for i in range(len(labels)):
                color = input(f"Color of plot {labels[i]}: ")
                colors.append(color)
        output["colors"] = colors

        print(f"You entered:")
        pprint.pprint(output)
        feedback = input("Does this all look correct? (y/n) ")
        if feedback.lower() == "y": correct = True

    return output

def _get_info_and_add_plot(sim_name, category= None):
    output = _get_new_plot_info(category)
    _add_plot(sim_name, **output)

def _get_info_and_add_category(sim_name):
    output = _get_new_plot_category_info()
    _add_plot_category(sim_name, **output)

    return output["yaml_name"]

def new_plots(sim_name= None, category= None):
    """ Wizard for adding new plots to an existing plotting_data.yml file """
    if sim_name is None:
        sim_name = input("Enter folder name: ")
    if category is None:
        category = input("Enter category of plots to add to (internal name): ")

    first_run = True
    confirm_plot = "y"
    while True:
        if not first_run:
            confirm_plot = input("Create another plot for this category? (y/n) ")
        if not confirm_plot.lower() == "y":
            print("Done adding plots.")
            break

        _get_info_and_add_plot(sim_name, category)
        first_run = False

    print("Done")

def new_plot_file():
    """ Wizard for creating a new plotting_data.yml file """
    print("Before starting, you should have already created a folder for your simulation, and it should already contain a data subfolder.")
    confirm = input("If there is already a plotting_data.yml file, this process will DELETE it. Continue? (y/n) ")
    if not confirm.lower() == "y":
        print("Aborting.")
        return
    
    sim_name = input("Sim name (the name of the folder): ")
    try:
        with open(rpath("models", sim_name, "data", "plotting_data.yml"), "w") as f:
            pass
    except OSError:
        print("Error! Did you create the necessary folders and spell the name right?")
        print("Aborting")
        return

    print("File created. Entering category and plot creation phase.")
    while True:
        confirm_category = input("Create a plot category? (y/n) ")
        if not confirm_category.lower() == "y":
            print("Done adding categories.")
            break

        category = _get_info_and_add_category(sim_name)

        while True:
            confirm_plot = input("Create a new plot for this category? (y/n) ")
            if not confirm_plot.lower() == "y":
                print("Done adding plots.")
                break

            _get_info_and_add_plot(sim_name, category)

def resave_config(data):
    with open(rpath("config.yml.bak"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    try:
        with open(rpath("config.yml"), "w") as f:
            yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)
    except OSError:
        print("Error saving your config file! If your config.yml file was deleted, a backup is available as 'config.yml.bak'. Rename it to config.yml.")
    finally:
        os.remove(rpath("config.yml.bak"))

    with open(rpath("config.yml"), "r") as f:
        data = yaml.safe_load(f)
    with open(rpath("config.yml.bak"), "w") as f:
        yaml.safe_dump(data, f, sort_keys= False, allow_unicode= True)

    return data

def new_control_panel_file(model= None):
    print("Disclaimer 1: This is NOT a comprehensive wizard. Many more specialized features of the control panel can currently only be interacted with via editing the control_panel.yml file directly. The purpose of this function is only to get you off the ground with a 'quick and 'dirty' start.")
    print("Emphasis on dirty. Don't expect the control panel to look nice without some tweaking.")
    print()
    print("Disclaimer 2: This will DELETE an existing control_panel.yml file if one exists. Only use this wizard for creating new models.")
    print()
    print("Disclaimer 3: You are expected to have already defined a dataclass in the parameters.py file AND specified a set of starting parameters in the params.yml file BEFORE running this function. Both of these are necessary for this function to work properly.")
    print()

    if model is None:
        models = list_subdirs(rpath("models"))
        print(f"Models: ")
        for i, model in enumerate(models):
            print(f"[{i}]: {model}")
        sub_choice = input("Enter a number corresponding to the model you are creating a control panel for, or type 'q' to quit: ")
        if sub_choice.lower().strip() == 'q': return
        try:
            choice_num = int(sub_choice.strip())
            model = models[choice_num]
        except (KeyError, IndexError):
            print("Invalid selection. Please enter one of the numbers displayed above: ")
            return

    presets = load_presets(model)
    print(next(iter(presets)))
    try:
        preset = presets[next(iter(presets))]["params"]
    except StopIteration:
        print(f"You need to define at least one preset first!")
        return

    params = params_from_mapping(preset, rpath("models", model, "simulation", "parameters.py"))
    all_params = {}
    for i, field in enumerate(fields(params)):
        all_params[i] = [field.name, field.type]
        if isinstance(getattr(params, field.name), ndarray):
            all_params[i].append(getattr(params, field.name).shape)
        print(f"[{i}]: {field.name} - {field.type}")

    exemptions_str = input("Enter the numbers corresponding to any of the above parameters which you do NOT want to have controls for, separated by commas: ")
    exemptions_strs = exemptions_str.split(",")
    try:
        if exemptions_strs == ['']:
            exemptions_ints = []
        else:
            exemptions_ints = [int(exemp.strip()) for exemp in exemptions_strs]
    except ValueError:
        print("Error, at least one of your exemptions is not a number. Please double check and make sure that you are entering the NUMBER listed next to the parameter and not the actual name.")
        return

    params_to_add = {}
    for param_num in all_params:
        if param_num not in exemptions_ints:
            params_to_add[all_params[param_num][0]] = all_params[param_num][1:]

    controls = {"divider1": {"title": "Parameters"}}
    current_row = {}
    for i, param in enumerate(params_to_add):
        if i % 3 == 0 and i != 0:
            rowNum = i // 3
            controls[f"row{rowNum}"] = current_row.copy()
            current_row.clear()

        print(f"Creating a widget for {param}.")
        param_dict = {}
        param_dict["param_name"] = param
        param_type = params_to_add[param][0]
        if param_type is int or param_type is float:
            print(f"{param} detected as a number, so we will create for it an entry block.")
            param_dict["label"] = input("Enter a label for the parameter. LaTeX is accepted, but you need to add the dollar signs to indicate math mode. If it isn't rendering, check the yaml file and make sure that it is using single quotes: ")
            param_dict["control_type"] = "entry_block"
            param_dict["type"] = "scalar"
            if param_type is int:
                param_dict["scalar_type"] = "int"
            else:
                param_dict["scalar_type"] = "float"

            good_in = False
            while good_in == False:
                rang = input(f"Enter the slider range for {param} as two numbers, separated by a comma: ")
                rang_list = rang.split(',')
                try: 
                    if param_type is int:
                        rang_nums = [int(x.strip()) for x in rang_list]
                    else:
                        rang_nums = [float(x.strip()) for x in rang_list]
                    good_in = True
                except ValueError:
                    print("Invalid input. Try again.")
    
            param_dict["range"] = FlowSeq(rang_nums)

        if param_type is ndarray:
            param_dict["control_type"] = "entry_block"
            shape = params_to_add[param][1]
            if len(shape) > 1:
                print(f"{param} is a {shape[0]}x{shape[1]} matrix. We'll make a special widget for it.")
                param_dict["type"] = "matrix"
                param_dict["dim"] = FlowSeq(list(shape))
            else:
                print(f"{param} is a {shape[0]} dimensional vector. We'll make a special widget for it.")
                param_dict["type"] = "vector"
                param_dict["dim"] = shape[0]

            param_dict["label"] = input("Enter a label for the parameter. LaTeX is accepted, but you need to add the dollar signs to indicate math mode. If it isn't rendering, check the yaml file and make sure that it is using single quotes: ")

        if param_type is bool or param_type is str:
            print(f"{param} detected as either a string or a Boolean, so we will create for it a dropdown.")
            param_dict["control_type"] = "dropdown"
            param_dict["param_name"] = param
            param_dict["label"] = input("Enter a label for the dropdown (LaTeX is not accepted): ")

            names = []
            values = []
            if param_type is bool:
                values = [True, False]
                tru_name = input(f"Enter a descriptive name for whatever {param} being True corresponds to (or just True if you're lazy): ")
                false_name = input(f"Enter a descriptive name for whatever {param} being False corresponds to (or just False if you're lazy): ")
                names = [tru_name, false_name]
            else:
                while True:
                    name = input("Enter a dropdown option name: ")
                    names.append(name)
                    values.append(input(f"Enter what {param} should be set to when {name} is selected: "))
                    done = input("Is that all of the dropdown options? (y/n)")
                    if done.lower == 'y': break

            param_dict["names"] = FlowSeq(names)
            param_dict["values"] = FlowSeq(values)

        param_dict["tooltip"] = input("Enter a tooltip for this parameter (or leave blank if you don't care): ")

        current_row[param] = param_dict

    i = len(params_to_add)
    if len(current_row) > 0:
        rowNum = i // 3 + 1
        controls[f"row{rowNum}"] = current_row

    print("We're ready to create the file.")
    pprint.pprint(controls)
    confirm = input(f"Continue to create the file? (y/n): ")

    if confirm.lower() != 'n':
        try:
            with open(rpath("models", model, "data", "control_panel_data.yml"), "w") as f:
                yaml.safe_dump(controls, f, sort_keys= False, allow_unicode= True)
        except OSError:
            print("Something went wrong creating the file. Aborting.")
            return

    print("Done! If you've ran all of the other wizards, you should be ready to run your model now. Have fun!")

def _add_demo(data, intern_name= "", new_demo: dict= {}, gui_dialog= False):
    if new_demo == {}:
        default = False
        intern_name = input("Internal name for demo: ")
        new_demo = {}
        new_demo["details"] = {}
        new_demo["name"] = input("Display name for demo: ")
        new_demo["desc"] = input("Description of demo: ")
        models = list_subdirs(rpath("models"))
        print(f"Models: ")
        for i, model in enumerate(models):
            print(f"[{i}]: {model}")
        sub_choice = input("Enter a number corresponding to the model you are using: ")
        try:
            choice_num = int(sub_choice.strip())
            model = models[choice_num]
        except (KeyError, IndexError):
            print("Invalid selection. Please enter one of the numbers displayed above: ")
            return
        new_demo["details"]["simulation_model"] = model
        params_path = rpath("models", model, "data", "params.yml")
        sim_functions_module = importlib.import_module(f"models.{model}.simulation.simulation")
        functions_dict = dict(inspect.getmembers(sim_functions_module, inspect.isfunction))
        functions_list = list(functions_dict.keys())
        for i, func in enumerate(functions_list):
            print(f"[{i}]: {func}")
        sub_choice = input("Enter a number corresponding to the default simulation function: ")
        try:
            choice_num = int(sub_choice.strip())
            func_name = functions_list[choice_num]
        except (KeyError, IndexError):
            print("Invalid selection. Please enter one of the numbers displayed above: ")
            return
        new_demo["details"]["simulation_function"] = func_name
        choices = {}
        with open(params_path, "r") as f:
            presets = yaml.safe_load(f)["presets"]
        for i, preset in enumerate(presets):
            choices[i] = preset
            print(f"[{i}]: {preset}")
        sub_choice = input("Enter a number corresponding to the default starting parameters: ")
        try:
            choice_num = int(sub_choice.strip())
            preset_name = choices[choice_num]
        except (KeyError, IndexError):
            print("Invalid selection. Please enter one of the numbers displayed above: ")
            return
        new_demo["details"]["default_preset"] = preset_name
        sub_selection = input("specify starting x and y limits? (y/n): ")
        if sub_selection.lower().strip() == 'y':
            x_input = input("Enter lower and upper x limits, separated by a comma: ")
            y_input = input("Enter lower and upper y limits, separated by a comma: ")
            
            x_lims_str = x_input.split(',')
            y_lims_str = y_input.split(',')
            try:
                xlims = [float(x.strip()) for x in x_lims_str]
                ylims = [float(y.strip()) for y in y_lims_str]
            except ValueError:
                print("Invalid inputs. Please enter only numbers separated by commas.")
                return

            new_lims = FlowSeq([xlims, ylims])
            new_demo["details"]["starting_lims"] = new_lims
    else:
        default = True if "default" in new_demo else False

    proceed = True
    if not gui_dialog:
        print(f"Your demo: ")
        pprint.pprint(new_demo)
        sub_selection = input("Does this all look correct? (y/n): ")
        if sub_selection.lower().strip() != 'y':
            proceed = False

    if proceed:
        if default:
            for demo in data["demos"]:
                if "default" in data["demos"][demo]:
                    del data["demos"][demo]["default"]

        data["demos"][intern_name] = new_demo
        data = resave_config(data)
    else:
        if not gui_dialog:
            print(f"Aborting")

    if not gui_dialog:
        print("Done. New demo created.")

    return data

def edit_config(info= None, gui_dialog= False):
    with open(rpath("config.yml"), "r") as f:
        data = yaml.safe_load(f)
 
    selection = "z"
    while selection.lower() != "q":
        print(f"What would you like to do? \n \
            To edit your default image save directory, type 's'. \n \
            To edit one of your demos, type 'e'. \n \
            To delete a demo, type 'r'. \n \
            To choose a new default demo, type 'd' \n \
            To add a new demo, type 'a'. \n \
            To quit, type 'q'.")
        selection = input("Enter your selection: ")

        if selection == "s":
            new_location = input("Enter the complete filepath for your new default save location: ")
            data["global_settings"]["default_save_dir"] = new_location
            data = resave_config(data)
            print(f"Done. Save location changed to {new_location}.")

        if selection == 'd':
            demos = data["demos"]
            print("Your demos: ")
            choices = {}
            current_def_index = -1
            for i, demo in enumerate(demos):
                choices[i] = demo
                if "default" in demos[demo]:
                    current_def_index = i
                    print(f"[{i}] (CURRENT DEFAULT) {demo}")
                else:
                    print(f"[{i}]: {demo}")
            choice = input("Enter the number of the demo you want to choose as default: ")
            try:
                choice_num = int(choice.strip())
                demo = choices[choice_num]
            except (KeyError, ValueError):
                print("Invalid selection. Please enter one of the numbers displayed above: ")
                continue
            if current_def_index != -1:
                del data["demos"][choices[current_def_index]]["default"]
            data["demos"][demo]["default"] = True
            data = resave_config(data)
            print(f"Done. {demo} set as new default.")

        if selection == "r":
            print(f"Disclaimer: This deletes the demo specification from the config file only. It does NOT delete a model folder itself. You are expected to do that yourself.")
            demos = data["demos"]
            print("Your demos: ")
            choices = {}
            for i, demo in enumerate(demos):
                choices[i] = demo
                print(f"[{i}]: {demo}")
            choice = input("Enter the number of the demo you want to choose as default: ")
            try:
                choice_num = int(choice.strip())
                demo = choices[choice_num]
            except (KeyError, ValueError):
                print("Invalid selection. Please enter one of the numbers displayed above: ")
                continue
            confirm = input(f"Are you sure you want to delete {demo}? This cannot be undone. (y/n): ")
            if confirm.lower().strip() == 'y':
                del data["model_specific_settings"][demo]
                del data["demos"][demo]
                data = resave_config(data)
                print(f"Done. Deleted {demo}.")
            else:
                print(f"Aborting deletion.")

        if selection == "a":
            data = _add_demo(data, gui_dialog= gui_dialog)

        if selection == "e":
            demos = data["demos"]
            print("Your demos: ")
            choices = {}
            for i, demo in enumerate(demos):
                choices[i] = demo
                print(f"[{i}]: {demo}")
            choice = input("Enter the number for the demo you would like to edit: ")
            try:
                choice_num = int(choice.strip())
                demo_name = choices[choice_num]
            except (KeyError, ValueError):
                print("Invalid selection. Please choose one of the numbers above.")
                continue
            sub_selection = "z"
            while sub_selection.lower() != "done":
                choices = {1: "name", 2: "desc"}
                print(f"[1] Name: {demos[demo_name]["name"]}")
                print(f"[2] Description: {demos[demo_name]["desc"]}")
                details = demos[demo_name]["details"]
                for i, det in enumerate(details):
                    choices[2+i] = det
                    print(f"[{2+i}]: {det}: {details[det]}")

                sub_selection = input("Enter the number for the setting you want to change, or type 'done' when you are finished editing this demo: ")
                if sub_selection.lower() == "done": continue
                try:
                    choice_num = int(sub_selection.strip())
                except ValueError:
                    print("Invalid selection. Please choose one of the numbers above.")
                    continue
                if sub_selection == 1:
                    new_name = input("New name: ")
                    data["demos"][demo_name]["name"] = [new_name]
                    data = resave_config(data)
                    print(f"Done. Display name changed to {new_name}.")
                    continue
                if choice == 2:
                    new_desc = input("New description: ")
                    data["demos"][demo_name]["desc"] = new_desc
                    data = resave_config(data)
                    print(f"Done. Description changed.")
                    continue
                else:
                    try:
                        choice_name = choices[choice_num]
                    except KeyError:
                        print("Invalid selection. Please choose one of the numbers above.")
                        continue
                    if choice_name == "starting_lims":
                        x_input = input("Enter lower and upper x limits, separated by a comma: ")
                        y_input = input("Enter lower and upper y limits, separated by a comma: ")
                        
                        x_lims_str = x_input.split(',')
                        y_lims_str = y_input.split(',')
                        try:
                            xlims = [float(x.strip()) for x in x_lims_str]
                            ylims = [float(y.strip()) for y in y_lims_str]
                        except ValueError:
                            print("Invalid inputs. Please enter only numbers separated by commas.")
                            continue

                        new_lims = FlowSeq([xlims, ylims])
                        data["demos"][demo_name]["details"][choice_name] = new_lims
                        data = resave_config(data)
                        print(f"Done. Limits changed.")
                    else:
                        new_thing = input(f"New value for {choice_name}: ")
                        data["demos"][demo_name][choice_name] = new_thing
                        data = resave_config(data)
                        print(f"Done. {choice_name} for {demo_name} changed to {new_thing}.")

def main_menu():
    selection = "z"
    while selection.lower() != "q":
        print(f"What would you like to do? Select your wizard: \n \
            [1] New model creation \n \
            [2] New plot file creation \n \
            [3] Add new plots to existing plot \n \
            [4] New control panel creation wizard \n \
            [5] Edit your config file \n ")
        selection = input("Type the number corresponding to the option you want, or type 'q' to quit, or '?' for some guidance on getting started: ")

        if selection == "?":
            print("To create a model follow these steps:")
            print("1. Run the new model creation wizard.")
            print("2. Go into the new folder and do the following three things: ")
            print("   - Edit the simulation/simulation.py file and fill in the get_trajectories function with the actual meat of the simulation.")
            print("   - Edit the simulation/parameters.py file and define the parameters of your simulation.")
            print("   - Edit the data/params.yml file and define some starting values for those parameters.")
            print("3. Run the new plot file creation wizard.")
            print("4. Run the control panel creation wizard.")
            print("5. Run the 'Edit your config file' wizard, then within that run the 'add new demo' sub-wizard.")
            print("6. Run your model!")

        elif selection == "1":
            create_new_model_dir()

        elif selection == "2":
            new_plot_file()

        elif selection == "3":
            new_plots()

        elif selection == "4":
            new_control_panel_file()

        elif selection == "5":
            edit_config()

        else:
            print("Command not recognized. Please either choose from the numbered options above, type ? for help, or q to quit.")

if __name__ == "__main__":
    # Call your functions here
    
    # Both arguments optional for both of these
    # new_plots(sim_name, category) <- For adding plots to an existing plotting_data.yaml file
    # new_plot_file() 

    # new_plots()
    # create_new_model_dir()
    # edit_config()
    main_menu()

