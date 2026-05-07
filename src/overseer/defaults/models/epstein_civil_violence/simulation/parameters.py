from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    width: int = 40
    height: int = 40
    citizen_density: float = 0.7
    cop_density: float = 0.04
    citizen_vision: int = 7
    cop_vision: int = 7
    legitimacy: float = 0.8
    max_jail_term: int = 30
    active_threshold: float = 0.1
    arrest_prob_const: float = 2.3
    movement: bool = True
    T: int = 1000
    activ_order: str = 'random'
    grid_type: str = 'Von Neumann'
