from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    y1i: float
    y2i: float
    e: float
    a: float
    k1: float
    k2: float
    r: float
    s: float
    N0: int
    T: int
    dt: float = 0.01
    balanced: bool = False
    balanced_indep: str = 'y1'
    money_reinvestment: bool = False
    analytic_soln: bool = True
    enforce_nonneg: bool = False
    enforce_population_constraints: bool = False
