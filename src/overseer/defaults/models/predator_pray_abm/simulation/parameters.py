from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    grass_regrowth_time: int = 10
    grid_x: int = 30
    grid_y: int = 30
    init_sheep_popn: int = 50
    init_wolf_popn: int = 30
    sheep_reprod_rate: float = 0.05
    wolf_reprod_rate: float = 0.03
    wolf_gain_from_food: float = 20
    sheep_gain_from_food: int = 4
