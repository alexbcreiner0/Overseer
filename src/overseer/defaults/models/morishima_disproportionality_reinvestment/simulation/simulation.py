import copy
from .Economy import Economy
from .parameters import Params

def get_trajectories(params: Params):
    sim_params = copy.deepcopy(params)

    economy = Economy(sim_params)

    for i in range(params.T):
        economy.step()
        yield economy.traj, economy.t

    economy.get_analytic_curves()
    yield economy.traj, economy.t
