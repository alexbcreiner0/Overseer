import numpy as np
import copy
from scipy.integrate import solve_ivp
from typing import Callable, Dict, Any, Optional
from .parameters import Params
from .CapitalistEconomy import CapitalistEconomy
import sys
from overseer.tools.dataclasses import Append, Extend, Replace

def simulate(params: Params, *, event_queue= None):
    """ Unchanged dynamics, nothing special happening """
    sim_params = copy.deepcopy(params)
    if sim_params.economy_type == "unrestricted":
        economy = CapitalistEconomy(sim_params, event_queue= event_queue)
    elif sim_params.economy_type == "fixed_real_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_real_wage"], event_queue= event_queue)
    elif sim_params.economy_type == "nondecreasing_employment":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment"], event_queue= event_queue)
    elif sim_params.economy_type == "fixed_money_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_money_wage"], event_queue= event_queue)
    elif sim_params.economy_type == "fixed_struggle":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment", "fixed_money_wage"], event_queue= event_queue)
    else:
        print("Unrecognized economy_type parameter. Setting to the default.")
        economy = CapitalistEconomy(sim_params, event_queue= event_queue)

    for i in range(params.T):
        gen = economy.step()
        for traj, t in gen:
            yield traj, t

    economy.cleanup()
    yield economy.traj, Append(economy.current_t)
