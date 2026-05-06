from .parameters import Params
import numpy as np
from .Economy import Economy

MODEL_READY = True # Set this to True when you think it's ready.
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params):
    economy = Economy(params)
    t = [0]

    yield economy.traj, np.array(t)

    for i in range(1, params.T):
        economy.step()
        t.append(i)

        yield dict(economy.traj), np.array(t)
    

