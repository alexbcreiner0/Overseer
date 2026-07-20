from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import queue
from .Society import Society
import logging
logger = logging.getLogger(__name__)

def get_trajectories(params: Params, *, event_queue = None):
    society = Society(params)

    logger.info(f"{society.get_data()=}")
    yield society.get_data()

    while True:
        society.step()
        yield society.get_data()

