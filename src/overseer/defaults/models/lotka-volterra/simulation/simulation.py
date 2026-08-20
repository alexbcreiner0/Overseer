import logging
logger = logging.getLogger(__name__)
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import queue
from .Model import Model

def get_trajectories(params: Params, *, event_queue = None):
    model = Model(params)

    yield model.traj

    while True:
        model.step()
        yield model.traj

