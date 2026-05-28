from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    N: int = 500
    M: int = 50000
    L: int = 4
    R: int = 20
    C: int = 2
    T: int = 10000
    max_trade_attempts: int = 25
    avg_interval: int = 70
    l: ndarray = field(default_factory=lambda: array([1.0, 3.0, 3.0, 11.0]))
    use_custom_l: bool = True
    use_custom_c: bool = True
    psi: float = 0.5
    const_gamma: float = 0.5
    omega: float = 0.5
    c: ndarray = field(default_factory=lambda: array([20.0, 17.0, 19.0, 18.0]))
    tol: float = 0.005
