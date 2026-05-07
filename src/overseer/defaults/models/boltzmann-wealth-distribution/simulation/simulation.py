# from .parameters import Params
from typing import Tuple, Callable, Optional
import numpy as np
import mesa
from .parameters import Params
from .extra_functions import MoneyModel
import time

def get_trajectories(params: Params):
    model = MoneyModel(params)
    t = []
    for i in range(params.T):
        traj = model.get_traj()
        model.step()
        t.append(i)

        yield dict(traj), np.array(t)

if __name__ == "__main__":
    model = MoneyModel(10)
    for i in range(10):
        model.step()
    print(model.datacollector.get_model_vars_dataframe()["Gini"].to_numpy())
