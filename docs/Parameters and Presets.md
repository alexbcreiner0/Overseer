# Initialization
A model **parameter** is any piece of data which the model relies on to define its operation. These can be any type of variable, and Overseer must have a designated value for all of them in order to run your model. 

Parameters can be defined in the Parameter Settings menu:
![[param-settings.png.png]]

When specifying default values, you should type the value exactly how you would define it if you were writing Python code. So an 2x2 Numpy matrix should be defined as \[\[a,b\],\[c,d\]\], and so on. 

Hitting apply updates the `simulation/parameters.py` file in your model directory. If we were to open it, we would see this:

```python
from dataclasses import dataclass, field
from numpy import array, ndarray

@dataclass
class Params:
    T: int = 200
    N: int = 1000
    M: int = 100000
    w: ndarray = field(default_factory=lambda: array([10,90]))
```

You could easily make this yourself instead of using the GUI, but be mindful of the special way in which the default values for Numpy arrays need to be recorded. These parameters merely define a Python [dataclass](https://docs.python.org/3/library/dataclasses.html), which gets instantiated and handed to your simulation function as input when your simulation starts. 

In order to determine what the actual values of these parameters are supposed to be during initialization, Overseer relies on a specified **preset**. Presets are stored in yaml format, in the `data/params.yml` file of your model folder. They can be managed in the Preset Settings menu:

![[preset-menu.png.png]]

However, this is mostly only useful for tweaking.  In practice, you will create new presets by arriving at them naturally through experimentation with your controls, and then saving them in the top menu bar by selecting Parameters -> Save parameter settings. The real use for the Preset Settings menu is useful for making small changes to *existing* presets. 

When creating a demo for a model, a default preset **must** be specified, which is what is initially loaded with the demo:
![[default-preset.png]]

When a new model is created, a `simulation/params.yml` is generated automatically with a single preset, called `default_preset`:

```yaml
presets:
  default_preset:
    name: Default
    desc: ''
    params: null
```

The way that Overseer goes about choosing values for each parameter when a simulation begins can now be described as follows. For each parameter, Overseer first consults the specified preset to see if a parameter is specified there. If it is, then we stop here. If it isn't, then Overseer assumes that there is a default value specified in the definition of the `Params` dataclass - i.e. it assumes that *you* picked something for it to default to when defining your parameters. Because of this, you can actually get a model up and running without ever interacting with the preset system, **provided** you specify a default value for every parameter that you define. 

It is considered best practice when using Overseer to specify a default value for every parameter, but this is not always reasonable. The Preset Settings menu will mark parameters that don't have default values with an asterisk, and remind you to set values for them.  If you fail to fill in a parameter field marked by an asterisk and click apply anyway, Overseer *will not save your file*. 

One final note: parameters with default values set become optional arguments, and Python requires that optional arguments always are specified *after* the required arguments. Thus when defining parameters in the Parameter settings menu, you must always have the parameters without defaults appear in the list before the parameters without defaults. The $\uparrow$ and $\downarrow$ allow you to easily reorganize your parameters to conform to this, or you can click the 'Sift defaults down' button to automatically bring all parameters without defaults underneath those which have defaults. 
# Save as Initial
