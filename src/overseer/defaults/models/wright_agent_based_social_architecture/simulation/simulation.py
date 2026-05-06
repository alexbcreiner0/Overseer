from .parameters import Params
import numpy as np
from .Economy import Economy
import inspect

MODEL_READY = False # Set this to True when you think it's ready.
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params):
    t = [0]
    T, N, M, w = params.T, params.N, params.M, params.w
    economy = Economy(M, N, w)

    for i in range(1,T+1):
        step = economy.my_step()
        for out in step:
            if out == -1:
                # yield None, None
                continue
        t.append(i)
        traj = economy.traj

        yield dict(traj), np.array(t) 

    economy.cleanup()
    traj = economy.traj
    yield dict(traj), np.array(t)
