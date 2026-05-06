import numpy as np
import copy
from scipy.integrate import solve_ivp
from typing import Callable, Dict, Any, Optional
from .parameters import Params
from .CapitalistEconomy import CapitalistEconomy
import sys

# This is where the app will look for a get_trajectories function. 
def simulate(params):
    """ Unchanged dynamics, nothing special happening """
    sim_params = copy.deepcopy(params)
    if sim_params.economy_type == "unrestricted":
        economy = CapitalistEconomy(sim_params)
    elif sim_params.economy_type == "fixed_real_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_real_wage"])
    elif sim_params.economy_type == "nondecreasing_employment":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment"])
    elif sim_params.economy_type == "fixed_money_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_money_wage"])
    elif sim_params.economy_type == "fixed_struggle":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment", "fixed_money_wage"])
    else:
        print("Unrecognized economy_type parameter. Setting to the default.")
        economy = CapitalistEconomy(sim_params)

    e = None
    for i in range(params.T):
        try:
            economy.step()
        except Exception as error:
            e = error
            with open("log.txt", "w") as f:
                print(economy.traj, file= f)
            break
    try:
        economy.cleanup()
    except Exception as error:
        e = error

    traj, t = economy.traj, economy.t
    return traj, t, e

def simulate2(params: Params):
    """ Unchanged dynamics, nothing special happening """
    sim_params = copy.deepcopy(params)
    if sim_params.economy_type == "unrestricted":
        economy = CapitalistEconomy(sim_params)
    elif sim_params.economy_type == "fixed_real_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_real_wage"])
    elif sim_params.economy_type == "nondecreasing_employment":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment"])
    elif sim_params.economy_type == "fixed_money_wage":
        economy = CapitalistEconomy(sim_params, restrictions= ["fixed_money_wage"])
    elif sim_params.economy_type == "fixed_struggle":
        economy = CapitalistEconomy(sim_params, restrictions= ["nondecreasing_employment", "fixed_money_wage"])
    else:
        print("Unrecognized economy_type parameter. Setting to the default.")
        economy = CapitalistEconomy(sim_params)

    for i in range(params.T):
        economy.step()
        yield economy.traj, economy.t

    economy.cleanup()
    yield economy.traj, economy.t
