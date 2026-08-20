from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    grid_x: int = 50
    grid_y: int = 50
    init_sheep_popn: int = 100
    init_wolf_popn: int = 30
    sheep_reprod_rate: float = 0.03
    wolf_reprod_rate: float = 0.08
    wolf_death_rate: float = 0.02
    res: int = 1
