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

