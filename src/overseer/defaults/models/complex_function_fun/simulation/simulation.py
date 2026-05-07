from .parameters import Params
from typing import Optional, Callable
import numpy as np
import cplot

MODEL_READY = False # Set this to True when you think it's ready.
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params, *, should_stop: Optional[Callable[[], bool]]= None, yield_every: int= 1):
    """
        Run a simulation, get a trajectories dictionary (keys are strings, values are numpy arrays)
        (we'll call it traj) as well as another numpy array (we'll call it t) representing the independent
        variable axis. If your simulation is iterative, you can instead yield your traj, t output each
        step to view the evolution of your sim as it animates. Otherwise, simply return traj, t at the end.
    """
    ymin, ymax = params.ymin, params.ymax
    xmin, xmax = params.xmin, params.xmax

    res = params.res

    x = np.linspace(xmin, xmax, res)
    y = np.linspace(ymin, ymax, res)

    t = np.array([])

    X, Y = np.meshgrid(x, y, indexing= "xy")
    W = (X+1j * Y).astype(np.complex128)

    sin_Z = np.tan(W) / 3

    absZ = np.abs(sin_Z)

    finite = absZ[np.isfinite(absZ)]

    # lo, hi = np.percentile(finite, [0, 100])  # or [2, 98]

    # abs_clipped = np.clip(absZ, lo, hi)
    # mag = np.log10(absZ)
    # mag -= mag.min()
    # mag /= mag.max()
    # gamma = 0.7
    # mag = mag ** gamma
    # sin_Z = np.exp(mag * np.log(abs_clipped.max())) * np.exp(1j * sin_Z)
    # sin_Z = np.exp(mag * np.log(absZ.max())) * np.exp(1j * sin_Z)

    RGB = cplot.get_srgb1(sin_Z, saturation_adjustment= 2)

    traj = {
        "x": x,
        "y": y,
        "w": W,
        "sin": sin_Z,
        "abs_sin": np.abs(sin_Z),
        "arg_sin": np.angle(sin_Z),
        "rgb": RGB
    }

    yield traj, t


