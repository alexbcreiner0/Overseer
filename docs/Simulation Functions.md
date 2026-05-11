## simulation.py
- A simulation function **must**
    - Take an instance of a dataclass as input
    - Return an output of the form `traj, t, e` where
        - `traj` is a dictionary of trajectories. Each trajectory is something you want to plot. Keys should be strings (a short name for the plot), and values should be 1D numpy arrays containing all points. 
        - `t` is a 1D numpy array which gets interpreted as the x-axis of any plot.
        - `e` is an Exception object. You can wrap your simulation in a `try-except` block, and if it fails you can output the exception object which will display within the app in the status bar. If you don't have an exception to pass, just make this third output `None`. 
    - Those are the *only* rules! Run code from other languages, agent based simulations, run numerical simulations of differential equations or just plot the line $y=x^2$!
- Multiple simulations are allowed. Typically, I only use one with behavior that is modified conditionally by the parameters. This is a matter of personal preference.
- In the `config.yml` file, make sure to include the name of the default simulation function that you want to use in the `simulation_function` entry of the entry for your model under `demos`.
****