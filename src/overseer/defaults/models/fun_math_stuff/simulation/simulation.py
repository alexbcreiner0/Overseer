from .parameters import Params
from typing import Optional, Callable
import numpy as np

MODEL_READY = False # Set this to True when you think it's ready.
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params):
    traj = {}

    func_res, curve_res, b_lower, b_upper, b_res, X = params.func_res, params.curve_res, params.b_lower, params.b_upper, params.b_res, params.X

    x = np.linspace(-X,X,curve_res)
    B = np.linspace(b_lower,b_upper,b_res)

    k = 1+3/2*np.pi
    A = 0.5*np.ones(b_res)

    for i, b in enumerate(B):
        a = A[i]
        func = np.zeros(curve_res)
        for n in range(0,func_res):
            func += np.power(0.5,n)*np.cos(np.pow(b,n)*np.pi*x)

        traj["w"] = func
        yield dict(traj), np.array(x)

    # yield dict(traj), np.array(x)
