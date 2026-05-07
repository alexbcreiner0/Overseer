from .parameters import Params
import numpy as np
from .Model import EpsteinModel

MODEL_READY = True # Set this to True when you think it's ready.
        # --- Model selection row ---
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params):

    model = EpsteinModel(params)
    T = params.T

    traj = {
        "u": model.get_grid(),
        "cell_values": [0,1,2,3,4], # all possible codes corresponding to cell states
        "cell_colors": ["#717171" for i in range(5)], # making all cells same color because I want to use markers instead
        "states": model.get_agent_states(),
        "pie_color_map": {1: "#D73229", 2: "#A2D392", 3: "#565656"},
        "pie_label_map": {1: "Active", 2: "Quiet", 3: "Arrested"}
    }
    t = np.array([0])

    yield traj, t

    for i in range(T):
        model.step()

        traj["u"] = model.get_grid()
        traj["states"] = model.get_agent_states()
        t = np.append(t, i)
        if i % 100 == 0:
            model.get_agent_states_lazy()
        yield dict(traj), t.copy()
