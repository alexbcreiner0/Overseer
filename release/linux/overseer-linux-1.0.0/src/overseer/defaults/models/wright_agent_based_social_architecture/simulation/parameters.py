from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    T: int = 200
    N: int = 1000
    M: int = 100000
    w: ndarray = field(default_factory=lambda: array([10,90]))
