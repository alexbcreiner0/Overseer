# Keyboard Shortcuts
### General Controls
- F1 opens the global settings tab.
- F2 opens the control panel settings tab.
- F3 opens the plot settings tab.
- F4 opens the demo settings tab.
- F5 re-runs the simulation
- F6 calls the plt.tight_layout function (assuming you are in tight layout mode). This will attempt to fit everything into the screen nicely. Sometimes you need to call it multiple times. The other mode is constrained layout. Matplotlib's documentation touts constrained mode as the new, better, and preferred mode to the point where they emit warnings when a user changes from it. In general, constrained mode IS better, *provided* nothing about the layout is changing. However, there are many things that my application does which make constrained mode as much or more of a nightmare to deal with as tight mode. There's no winning here, as far as I can see. My advice is to try both and go back and forth depending on your situation. You'll just have to experiment a bit.
- F7 re-loads the simulation. The difference between this and the F5 shortcut is that F7 **also re-loads all of your simulation files**. This means that if you have made any changes to your simulation, pressing this will load those changes and run the *updated* version.
- F8 reloads the control panel and plots, if you've made any changes to them. (For instance, changing the color of a curve, or adding a scrollbar.)
- F9 reloads keybindings, if you've edited them.

- Ctrl+Tab cycles between the Model Controls tab and the Axis Controls tab of the control panel.
- Ctrl+Shift+Tab does the same thing but backwards.
- Ctrl+K toggles the control panel tab entirely. If you are in constrained mode and have multiple plots visible, they will likely be spread out too far. I would recommend only doing this in tight layout mode, and pressing F6 a few times both before and after performing this toggle.
- Space will pause the simulation if it is running.
- There is currently no shortcut for stopping the simulation. Just click the button in the toolbar. Sorry!
- Ctrl+S,S (as in, holding control+S, then releasing both, THEN pressing s again) opens up the dialog for saving a screenshot. **Make sure that you click the 'toggle transparency' checkbox in the toolbar before saving a picture, or the background will be transparent!**
- Ctrl+S,P opens up the dialog for saving a preset.
- Ctrl+S,D saves the current *entire view* as the default which your demo opens to. (An autosave for this feature exists, which can be toggled in the global settings.)
- Ctrl++ (as in holding control and pressing the +/= key), speeds up the simulation speed.
- Ctrl+- slows down the simulation speed.
- Esc closes the application.
- Ctrl+RightArrow will *expand* the axis grid rightward by one unit. This means that if you have only a single plot, it will create a second one to the right of it. If you have two vertically stacked plots, a 2x2 grid will appear. And so on.
- Ctrl+DownArrow does the same thing but expands downward. These two arrows combined are how one creates new axes in the grid.
- Ctrl+LeftArrow contracts the grid left.
- Ctrl+UpArrow contracts the grid upward.
- Ctrl+

### Axis Controls
Since you could have a whole variable grid of different plots visible at a given moment, there is a whole system of shortcuts for controlling them.
- Ctrl+B,X,Y selects the (X,Y)-axis as your **slot target** for further keyboard commands. For example, Ctrl+B,2,2 with a 2x2 grid of axes will target the bottom right axis of that grid. All further commands described below will apply to *that* specific axis. 
- Ctrl+S,C saves current view of the slot target as the default coordinate for that plotting category. What this means is that whenever you change plot categories after that, whatever the current x and y limits of that axis will automatically change to those saved coordinates. This is assuming you have the 'use saved limits when switching plot categories' setting checked in the Global settings. This is especially useful for things like fixed 2D grids, pie charts, and heatmaps. If unchecked, switching categories will preserve axis limits. 
- Ctrl+1/2/3/4/5/6/7/8/9 toggles the 1st/2nd/3rd/.../9th checkable plot of the slot target on or off. Numbering is done left to right, top to bottom. So for example, the middle plot on the second row of your category controls can be toggled with Ctrl+5.
- Ctrl+UpArrow/DownArrow toggles the plot category of the slot target up or down.
- Ctrl+L,Ctrl+T toggles the legend of the slot target on or off.
- Ctrl+]/\[ increments or decrements the legend size of the slot target.
- Ctrl+L,Ctrl+R cycles the location of the slot target's legend.
- Ctrl+L,Ctrl+T toggles the slot target's title.
- Ctrl+L,Ctrl+X toggles the slot target's X-axis title.
- Ctrl+L,Ctrl+Y toggles the slot target's Y-axis title.