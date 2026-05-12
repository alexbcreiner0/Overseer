# Sim Controls Tab
## control_panel_data.yml
This file is where you specify, row by row, what controls you want to be displayed. Due to how finicky it can be to properly arrange the widgets in a good looking way, there is currently no wizard to help you create this file - you will have to do it yourself. The format of this yaml should be something like:
```yaml
divider1:
    title: My controls
    side: left # <- optional, can also be right or center, defaults to center
row1:
    widget_name1:
        control_type: type of widget
        param_name: name of parameter which the control is wired to
        # widget specific extra settings (See below)
        tooltip: String that displays when the user clicks the question mark next to the widget
    # more widgets...
# more dividers and rows...
```

Dividers are just meant to separate out groups of controls. The essential settings for each widget are the `control_type` which specifies what kind of widget you're making, and the `param_name`, which is which parameter (defined in your `parameters.py` file) the widget is expected to be wired to. The currently available control types are:
- `"dropdown"`: Good for qualitative parameters, such as strings or Booleans (sorry, no checkboxes right now)
- `"entry_block"`: Meant for numerical parameters, which **includes vectors and matrices**. See below for more info. Most of your widgets will be these.
- `"button_group`": Sets of buttons which execute functions related to your system. Limited functionality right now, see below for more info.

In more detail now:
### entry_block
An example entry block:
```yaml
  supply_shock_mag:
    control_type: "entry_block"
    param_name: "supply_shock_mag"
    label: '$\alpha_s = $'
    type: "scalar"
    range: [0, 1]
    scalar_type: "float"
    tooltip: "Controls the magnitude of the supply shocks."
```
Explanation: `control_type`, `param_name` and `tooltip` we already have mentioned. The other specific settings to the entry block widget are
- label: Exactly what it sounds like. Note that LaTeX is supported (use single-quotes). What would be displayed here is $\alpha_s = $ followed by an entry where the user can type values for the parameter.
- type: Should be either `"scalar"`, `"vector"`, or `"matrix"`. Depending on which of these is picked, different extra settings are expected.     
    - If it is a scalar, then additionally the application expects
        - range: For scalars, a slider is created. This range defines the left and right extremes of that slider
        - scalar_type: Self explanatory. Can be `"float"` or `"int"`
    - If it is a vector or a matrix, then additionally the application expects
        - dim: In the case of a vector, should be a single integer representing the dimension of the vector. Entries for each coordinate will be created as a column of text entries. In the case of a matrix, should be a pair of the form `[n,m]` where n and m are integers. What will be created is an $n \times m$ grid of text entries for each entry of the matrix.

### dropdown
An example of a dropdown:
```yaml
  economy_type:
    control_type: "dropdown"
    param_name: "economy_type"
    label: "Model Restrictions"
    names: ["Unrestricted", "Fixed Real Wage", "Non-decreasing Employment", "Fixed Struggle"]
    values: ["unrestricted", "fixed_real_wage", "nondecreasing_employment", "fixed_struggle"]
    tooltip: "Various restrictions which we may impose upon the economy. Fixed struggle combines a fixed money wage with non-decreasing employment. This could represent an economy in which the 'yellow' labor unions have significant institutional power and are able to keep the class struggle locked in a stalemate."
```
- For these widgets, the extra settings besides `control_type`, `param_name` and `tooltip` are:
    - label: What text gets displayed above the dropdown. LaTeX not supported currently.
    - names: The text options which the user will see
    - values: If the $i^{th}$ name is chosen in the dropdown, then the $i^{th}$ value of this list is what the application will set the parameter equal to. (So if this is supposed to be a Boolean, make sure that the associated values are `True` or `False` (no quotes).  

### button_group
This one is a little undercooked right now, but are perfectly usable within their currently limited scope. My only use for it has an entry like this
```yaml
  generation:
    control_type: "button_group"
    names: ["Random Parameters"]
    tooltips: ["Generate random parameters. Not entirely working at present."]
    display: "horizontal"
    functions: ["random_parameters"]
```
The idea is that it will create a set of buttons which perform various functions, either arranged horizontally or vertically according to the display setting. Functions for the buttons should be created inside of a file called `extra_functions.py` inside of the simulation folder of your model directory. These functions are expected to take an instance of your parameters dataclass as input and return a new parameters dataclass as output. Names specify the text which is displayed on the button. The $i^{th}$ name will be wired to the $i^{th}$ function. 

# Plot Controls Tab
