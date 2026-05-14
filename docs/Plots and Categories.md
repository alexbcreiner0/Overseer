In this section we will go over all of the currently existing plotting features which Overseer has. Let's start by giving an overview of the graph panel in general. 

# Categories
In Overseer, plots are to be organized into **categories**, which are collections of plots which you may want to view plotted with one another on the same axis. In the [plot controls tab](Anatomy%20of%20Overseer%20-%20The%20Control%20and%20Graph%20Panels#The%20Control%20Panel%20and%20Graph%20Panel) of the control panel, each [slot](Anatomy%20of%20Overseer%20-%20The%20Control%20and%20Graph%20Panels#Slots) contains a dropdown which allows you to choose which category the slot is set to:

![](assets/slot-controls.png)

The checkboxes above the dropdown all correspond to plots which belong to the category. If we open up the plot settings tab, we can see this very clearly:

![](assets/plot-settings.png)

Checkboxes of a category appear in the same order that the plots appear here in the settings as child entries of the category, in rows of three from left to right. You can drag and drop plots and categories to rearrange the order of either. (The dragging is a little finicky right now. Make sure that it looks properly indented where it should be before letting go of your mouse click. If you mess up, just close and reopen the settings without clicking save or apply.)

We can see that there are a variety of settings options available for a category. These are really axis settings which apply independently of the plots. Here we can set a title, as well as labels for the x and y axes. If an x-axis label is not chosen, Time \[t\] will be displayed by default. You can avoid this by just typing a single space into the entry box here. The title and y-axis labels, if left blank, will leave no title or y-label on the plot. 

We have a variety of controls for showing various basic aspects of the subplot. It is useful to turn these off depending on what you are plotting. For example, if we were making a pie chart, it would be important to have all of these checked off. We can select whether the axis is a 2D or 3D grid as well. 

Finally, tooltip info can be used to give a viewer of your model dynamic information on the category they have selected. Users can view this information by clicking on the ? button next to the category dropdown:

![](category-info.png)

# Plots
Overseer supports a wide variety of plot types. Though it will never support everything matplotlib has to offer, it aims to curate a thorough enough subset of plot types and options from that library to meet everyone's needs. Currently, it supports:
- Curves (both 2D and 3D)
- Histograms
- Scatter plots
- Heatmaps (with added support for rendering grids with discrete actors)
- Pie charts
- Vector fields
- Discrete graphs
- Surfaces in 3D

I would like to get contour plots working but I've been having trouble figuring out a system for making them look good consistently. If you look in the code there is a whole system for it, but it's not quite there yet.

Let's take a quick glance at the plot settings tab to situate ourselves:
![](assets/plot-settings-tab.png)

Every plot, regardless of type, has a user-facing name and an internal name. The internal name is just a more machine-friendly version of the name you give, and is computed automatically. It is worth seeing in case you wish to do any manual editing of the `plotting_data.yml` file, but otherwise can be ignored. The toggled checkbox determines whether it should appear when the user first opens up the category. 

Below that, we have the plot-type choice. The options below that depend on the plot type chosen. Many (aspirationally, all) of the options here have ? buttons which can be clicked on to provide useful info on what the setting does. Most settings for all plots are optional, or automatically set to a sensible default. Settings which are both necessary and not set to something automatically have asterisks, to denote what absolutely must be filled in. 

The options given for each plot type are a combination of settings which are specific to Overseer and settings which are just keyword arguments to matplotlib. The latter is curated, and discussion of these will be kept to a minimum, since the reader can either click the ?  box or consult matplotlib's own documentation to determine how they work (or simply experiment with them). 
## Curves
Curves are plotted using matplotlib's `plot` function. As we can see from the above, the only truly necessary setting here is the trajectory key (technically the key for the y-axis specifically). The reader who doesn't know what is meant by trajectory key should look through the [quick-start tutorial](Quick-Start%20Tutorial%20--%20Building%20a%20Model%20From%20Scratch). Generally, matplotlib requires additionally an x-axis, but as explained in the section on [writing simulations](Writing%20Simulations), the user can specify a default which Overseer will default to using. The x-axis trajectory key entry can thus be left blank *assuming* that your simulation provides this default.

The settings in between the trajectory keys and the Curves (label+color) entry are matplotlib settings, and so I will skip over those (though they should be self-explanatory). The aforementioned Curves (label+color) specifies the label which identifies the curve in the legend, and the color of the curve, respectively. (Ignore the label template checkbox and the +Add series button for the time being.) Colors can be specified in hexadecimal or by typing out the name of the color. The entry box itself will color to assure you that you've picked something valid. There is also a color picker which can be accessed by clicking the button next to the field. 
### 3D Curves
The z-axis trajectory key can of course be left blank unless the user is trying to plot a curve in 3D. There is actually nothing wrong with plotting 2D curves on a 3D axis. If your axis is set to 3D from the category settings and you plot a 2D curve, you will just see a 2D curve which looks confined to the $z=0$ coordinate. The z-axis trajectory will be ignored *unless* the category is set to 3D. 
#### Example
```python
def curve_demo_3d(params: Params):
    a, b = params.a, params.b

    eps = 0.03
    t = 0.0

    for _ in range(1000000):
        t += eps
        traj = {
            "sine": Append(a*np.sin(b*t)),
            "cosine": Append(b*np.cos(b*t)),
            "z": Append(1/(0.01*np.sqrt(t)))
        }

        yield traj, Append(t)
```

Results in:
![](assets/3d-curve.gif)

### Vector Plots
Suppose we were working with an economic model in which we had a set of prices for $n$ different commodity types, all of which were evolving over time. As a very contrived example, consider this simulation function:

```python
from .parameters import Params
from overseer.tools.dataclasses import Append, Extend, Replace
import numpy as np

def get_trajectories(params: Params):
    traj = {
        "t": Append(0),
        "prices": Append([1.5, 2.5, 3])
    }
    yield traj

    traj = {
        "t": Append(1),
        "prices": Append([3.2, 4.5, 7])
    }
    yield traj

    traj = {
        "t": Append(2),
        "prices": Append([5.2, 1.5, 5])
    }
    yield traj
```

Since we are telling Overseer to **Append** this list data, rather than **Extend** it, Overseer assumes that you are providing it with a vector trajectory, and knows how to plot all three of these scalar quantities over time without you having to create three separate plots for them. To do this, we don't really need to do anything different:
![](assets/vector-traj.png)
By clicking the +Add series button twice, we now have two more pairs of label+color entries, which we can use to label all three prices. The result is this:
![](assets/vector-traj2.png)
Typing out legend labels for every curve every time get get quite tiring. This is where the 'Use label template' checkbox comes into play. The following settings will produce the same results as what we just saw:
![](assets/vector-traj3.png)
The template here substitutes every instance of {i} for whichever of the quantities is being plotted. The colors are also optional. If we left these fields blank, colors would be chosen automatically for every curve. If the number of prices was 4 instead of three, the fourth quantity would be plotted, and a color would be chosen automatically for that fourth one which is different from the first three. 
## Surfaces
Though the options are somewhat limited currently, support for surfaces is there, using matplotlib's `plot_surface` function. This function requires three arguments, all of which are 2D arrays. The idea is to define two 1D arrays, and then use numpy's `meshgrid` function to create a 2D grid defining an set of $(x,y)$ coordinates. These can then be fed into a scalar function to return all of the z-values.

#### Example
```python
def surface_frame(t):
    x = np.linspace(-5, 5, 50)
    y = np.linspace(-5, 5, 50)
    X, Y = np.meshgrid(x, y)

    x1 = 1.5 * np.cos(0.03 * t)
    y1 = 1.5 * np.sin(0.03 * t)

    x2 = 1.5 * np.cos(0.025 * t + np.pi)
    y2 = 1.5 * np.sin(0.04 * t)

    r1 = np.sqrt((X - x1)**2 + (Y - y1)**2)
    r2 = np.sqrt((X - x2)**2 + (Y - y2)**2)

    Z = (
        np.sin(5 * r1 - 0.18 * t) / (1 + 0.35 * r1)
        + np.sin(4 * r2 - 0.15 * t) / (1 + 0.35 * r2)
    )

    return X, Y, Z
```

Results in
![](assets/3d-surface.gif)

At the time of writing this, the GUI settings are pretty lacking for these. At the moment there is only support for choosing a color map and whether or not to display the colorbar. More features will be added in the future. 

It is worth emphasizing that matplotlib is especially lacking features when it comes to updating surfaces. The only option really is to just reconstruct the entire plot every frame. So this is definitely the most taxing simulation to animate. 
## Vector Fields
Vector fields (or *quiver plots*) can be created using matplotlib's `quiver` function. This function takes as required arguments two 2D arrays, $U$ and $V$, where $(u_{ij}, v_{ij})$ is the displacement of a vector. If nothing else is specified, this vector extends from the origin. Optionally, a second pair of 2D arrays $X$ and $Y$ can be specified, where $(x_{ij}, y_{ij})$ denotes where that same vector extends from instead of the origin. 

At present, there isn't much to specify to Overseer besides these keys. A color map can be specified to color the vectors, and a fifth 2D array $C$ can be given to guide the coloring process, where $c_{ij}$ specifies the color magnitude of that vector.

A color bar can be toggled, but fair warning: this colorbar **DOES NOT WORK unless Overseer's figure mode has been set to constrained.** Even if that is the case, the colorbar does not seem to play very well with animations. I'd recommend keeping it turned off until the animation is finished.

#### Example
```python
def vector_field_demo(params: Params):
    vec_x = np.arange(-10, 11, 1)
    vec_y = np.arange(-10, 11, 1)
    Xg, Yg = np.meshgrid(vec_x, vec_y, indexing="xy")

    base_U = -Yg.astype(float)
    print(f"{base_U=}")
    base_V = Xg.astype(float)
    print(f"{base_V=}")

    traj = {
        "vec_X": Xg,
        "vec_Y": Yg
    }

    t = np.array([0.0])
    epsilon = 0.5e-2

    for _ in range(10000):
        current_t = t[-1]

        angle = 0.8 * current_t
        ca = np.cos(angle)
        sa = np.sin(angle)
        rot_U = base_U * ca - base_V * sa
        rot_V = base_U * sa + base_V * ca

        cx = 6.0 * np.cos(0.9 * current_t)
        cy = 6.0 * np.sin(1.2 * current_t)

        sigma_env = 2.2
        env = np.exp(-((Xg - cx) ** 2 + (Yg - cy) ** 2) / (2 * sigma_env**2))
        env = np.where(env > 0.18, env, 0.0)

        pulse = 0.5 * (1.0 + np.sin(3.0 * current_t))
        amp = env * pulse

        vec_U = amp * rot_U
        vec_V = amp * rot_V

        traj["vec_U"] = vec_U
        traj["vec_V"] = vec_V

        traj["vec_C"] = np.absolute(vec_U + vec_V)

        yield traj, t

        t = np.append(t, t[-1]+epsilon)
```

Results in:
![](2d-vector-field.gif)
## Histograms

## Scatter Plots
Support for scatter plots is currently very half-baked. 
## Heatmaps and Discrete Grids

## Pie Charts

## Discrete Graphs
