from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    n_boids: int = 100
    space_width: int = 100
    space_height: int = 100
    vision: float = 2.0
    speed: float = 1.0
    separation: float = 2.0
    cohere: float = 0.03
    separate: float = 0.015
    match: float = 0.05
    T: int = 10000
