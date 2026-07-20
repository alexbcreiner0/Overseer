import logging
logger = logging.getLogger(__name__)
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import queue
from .Model import Model

def get_trajectories(params: Params, *, event_queue = None):
    model = Model(params)

    t = 0
    yield {
        "grass_grid": Replace(model.get_grass_grid()),
        "agent_grid": Replace(model.get_agents_grid()),
        "grass_values": Replace([0, int(params.grass_regrowth_time * 1/3), int(params.grass_regrowth_time * 2/3), params.grass_regrowth_time]),
        "grass_colors": Replace(["red", "orange", "#8bff33", "green"]),
        "t": Append(t),
        "n_sheep": Append(model.get_num_agents("sheep")),
        "n_wolves": Append(model.get_num_agents("wolf")),
    }

    while True:
        model.step()
        t += 1
        yield {
            "grass_grid": Replace(model.get_grass_grid()),
            "agent_grid": Replace(model.get_agents_grid()),
            "t": Append(t),
            "n_sheep": Append(model.get_num_agents("sheep")),
            "n_wolves": Append(model.get_num_agents("wolf")),
        }

