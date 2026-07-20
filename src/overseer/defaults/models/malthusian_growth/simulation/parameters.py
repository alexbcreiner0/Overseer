from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    T: int = 1000
    h: int = 5
    b: int = 1
    b_2: int = 2
    P_0: int = 1
    E_0: int = 1
    m: int = 4
    m_2: int = 5
    res: int = 3
    mode: str = "stateless_classless"
    a: int = 5 # surplus taxation rate
    e: int = 5 # state expense rate
    epsilon: float = 1.0 # extraction rate
    alpha: int = 3
    elite_conflict_mag: float = 0.8
    elite_conflict_rolls: int = 0
