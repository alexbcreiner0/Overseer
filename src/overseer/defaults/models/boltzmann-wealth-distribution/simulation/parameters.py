from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    n_agents: int = 100
    T: int = 1000
    taxation: str = 'None'
    transaction_type: str = 'unit'
    tau_s: int = 10
    delta: float = 0.03
    max_debt: float = 0.0
