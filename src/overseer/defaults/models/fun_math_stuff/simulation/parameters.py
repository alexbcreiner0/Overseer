from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    func_res: int = 300
    X: float = 10.0
    b_upper: float = 5.0
    curve_res: int = 300
    b_lower: float = 0.1
    b_res: int = 1000
