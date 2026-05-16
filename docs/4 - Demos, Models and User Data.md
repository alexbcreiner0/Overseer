# User Data
In this section, we'll take a closer look at the user-facing files of your Overseer installation, covering where they are and what purposes each of them serves. We'll also look at the structure of a model folder and do the same for that. 
## Config Files
Upon first launching Overseer, a configuration folder will be created in the place where that kind of thing is expected:
- For Linux, look in `~/.config/Overseer`
- For Windows, look in `C:\Users\your_username\AppData\Roaming\Overseer`
- For Mac OS, look in `~/Library/Application Support/Overseer`
The two files created are `config.yml` and `keybindings.yml`. In general, Overseer uses the [yaml](https://en.wikipedia.org/wiki/YAML) format for nearly everything configuration related. 

For the most part, you should never need to do any editing of your `config.yml`, as all of its settings are editable within Overseer itself in the Application Settings. The `keybindings.yml` file, is meant to be edited by the user, but it can be quickly opened for editing from the settings menu.

Overseer does not allow you to change the location of your `config.yml` file, but it can be redirected to point at something different, using either the `--config` option flag or by exporting the `OVERSEER_CONFIG` environment variable. Since all development versions of Overseer merely use wrapper launchers which run the program with a Python command, the launcher file can be easily edited to open alternative config files in the same manner.   

## User Data
By default, a folder called Overseer is created in your user documents folder. This is where all of the data relating to your models and demos will be stored, along with log files which are helpful for debugging your code. Where Overseer looks for this folder can be changed in the application settings, but regardless of where it looks, Overseer expects to see the following structure:

```
Overseer/
├── demos.yml/
├── logs/
│   └── log.jsonl
└── models/
```

### demos.yml
`demos.yml` contains information for each of your demos. A demo listing looks like this:
```
demo_name:
    name: Display Name of Demo
    desc: A description of the demo.
    details:
        simulation_model: model_folder_name
        simulation_function: A function from simulation.py
        default_preset: Initial parameter settings for your simulation
	    axis_settings: How your demo should look when you load it.
	(optional) default: True
```
All of these fields should be edited within the GUI itself, in the Demo Settings. `axis_settings` are the exception. Instead, you can configure the view however you want, and then in the menu go to View -> Save current axis settings to store that view as the default which loads when you open the demo.

Finally, the default field will only ever be present on a single demo, and designates the demo which Overseer opens into. The demo which is highlighted green in the Demo Settings tab is the default demo.

### logs.jsonl
`log.jsonl` contains error logs in `json` format. If one of your models crashes, look here for the traceback message which would normally be printed to the terminal.

# Anatomy of a Model
New models are creates inside of the models folder. The basic structure looks like this:

```
model_name/
├── __init__.py
├── data/
│   ├── control_panel_data.yml
│   ├── params.yml
│   └── plotting_data.yml
└── simulation/
    ├── __init__.py
    ├── parameters.py
    ├── extra_functions.py (optional)
    └── simulation.py
```

If you have saved any results, there will be a third folder, called `saved_results`, which contains that data.

Starting with the simulation folder:

`simulation.py` is where Overseer looks for functions to use as entrypoints to start your simulation. Multiple simulation functions are allowed, and the specific one to use can be specified in the Demo Settings. However, it is recommended that you create separate Python files for any functions or classes which your simulation makes use of. These additional files can be created here in the simulation folder with no issues. For more details on what exactly is expected of the `simulation.py` function, look [here](6%20-%20Writing%20Simulations.md)

`parameters.py` defines a dataclass which contains all relevant starting parameters for your model. Any specific information you want the model to have during its simulation should be stored as a parameter within this dataclass. 

`extra_functions.py` is an extra file that you can define here \<explain buttons\>

\<explain the value of making extra files here\>

Turning towards the data folder:

`control_panel_data.yml` contains row-by-row information about the controls you want to have in the control panel.
`params.yml` contains a list of possible starting parameters for your models. The application will be able to create, save, delete and rename them but you must supply it initially with at least one set of values for each parameter.
`plotting_data.yml` contains plots which you want to be displayed within the application. 
`extra_data.yml` semi-deprecated. Would only be needed if there were no parameters at all in the `params.yml` file, or if that file were not found. Application will look here for a fallback set of initial parameters.

Now that we have a basic idea of how all of these files fit together, let's go through each in more depth.

# The Data Files
## plotting_data.yml
This is where you specify the plots to display. **There is a wizard to help you create a new plotting_data.yml file**. To run it, open up `modelling_tools.py` inside of the tools directory of this project, add a call to `create_new_plot_dir()` in the `if __name__ == "__main__": block, and run the program. There is also a separate wizard for adding new plots to an existing `plotting_data.yml` file. To use this, add a call to `new_plots()` in `modelling_tools.py` and run the file. 

You still need to understand how the file is meant to be structured in order to properly make use of the wizards. The overall structure of the yaml file should be as follows:
```yaml
plot_category1:
    name: Name of Plot
    title: Your Title
    tooltip: Your tooltip
    x_label: Title of x-axis
    y_label: Title of y-axis
    plots:
        plot1:
            # settings for plot1
        plot2: 
            # settings for plot2
        # and so on
plot_category2: 
    # repeat structure 
```
From this we can see that plots are organized into categories. Categories appear to the user in a dropdown window. Upon choosing a category, a new set of plots will be available, as specified in the `plots` setting. If you don't care to organize your plots into categories, you don't have to. Just define a single category which will have every plot. Now let's move on to what the plot settings look like. A basic example of a plot looks like this:

```yaml
    equilibrium_rop:
      checkbox_name: Equilibrium Rate of Profit
      colors:
      - orange
      labels:
      - Equilibrium Profit Rate
      linestyle: dashed
      toggled: true
      traj_key: epr
```

- If no `checkbox_name` is specified, then the plot will always appear when the category is selected, and `toggled` can also be left out. 
- `colors` should be self-explanatory, except for mentioning that hex codes for colors are also allowed. `labels` are for the displayed legend. 
- Finally, and most importantly, `traj_key` is the key for the plot within the `traj` dictionary which your simulation function is expected to output. 

The above example plots a single scalar quantity over time. Sometimes however, we have vector trajectories which we want to plot. For example, if we have an economy with multiple commodities, then it's more convenient to have a single trajectories item which includes a 1D numpy array of price vectors instead of scalars, e.g.

```python
traj["p"] = [[1,2,3], [4,5,6], [7,8,9],...]
```

Assuming that your trajectories dictionary stores the prices like this, then the following plot entry will plot all of them as a group:
```yaml
    prices:
      checkbox_name: Unit Prices
      colors:
      - red
      - green
      - blue
      labels:
      - Price of Commodity 1
      - Price of Commodity 2
      - Price of Commodity 3
      on_startup: true
      toggled: true
      traj_key: p
```

- on_startup is a bit of a band-aid setting. I'm not sure if it is still needed. If you are having trouble getting your trajectories to display from the default category on start-up, go ahead and include this. Otherwise, *leave it out*.


## params.yml
It should initially look like this: 
```yaml
presets:
  default_preset:
    name: Default
    desc: Info for the user
    params:
      A: [[0.2, 0.0, 0.4], [0.2, 0.8, 0.0], [0.0, 0.1, 0.1]]
      l: [0.7, 0.6, 0.3]
      # etcetera
```
The default preset does not have to be called `default_preset`, but whatever name you give it, you edit the `config.yml` file to include it as the `default_preset`. Note that not *all* parameters need to be specified here, as long as you specified default values for them in your `parameters.py` file. 

## extra_data.yml
You should be able to completely ignore this. If you are paranoid, just copy and paste your default preset into here like so
```yaml
default_preset:
   name: Default
   desc: Info for the user
   params:
      A: [[0.2, 0.0, 0.4], [0.2, 0.8, 0.0], [0.0, 0.1, 0.1]]
      l: [0.7, 0.6, 0.3]
      # etcetera
```
