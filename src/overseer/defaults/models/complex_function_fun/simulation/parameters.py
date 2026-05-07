from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    xmin: float = -10.0
    xmax: float = 10.0
    ymin: float = -10.0
    ymax: float = 10.0
    res: int = 1000
