from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    T: int = 100
    res: int = 3
    alpha: float = 0.01
