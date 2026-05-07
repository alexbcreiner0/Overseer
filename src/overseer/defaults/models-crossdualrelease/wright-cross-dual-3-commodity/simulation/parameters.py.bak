from dataclasses import dataclass, field
from numpy import array, ndarray


@dataclass
class Params:
    A: ndarray = field(default_factory=lambda: array([[0.2, 0.0, 0.4], [0.2, 0.8, 0.0], [0.0, 0.1, 0.1]]))
    l: ndarray = field(default_factory=lambda: array([0.7, 0.6, 0.3]))
    b_bar: ndarray = field(default_factory=lambda: array([0.6, 0.0, 0.2]))
    c_bar: ndarray = field(default_factory=lambda: array([0.2, 0.0, 0.4]))
    alpha_w: float = 0.8
    alpha_c: float = 0.7
    alpha_L: float = 0.0
    kappa: ndarray = field(default_factory=lambda: array([1.0, 1.0, 1.0]))
    eta: ndarray = field(default_factory=lambda: array([2.0, 2.0, 2.0]))
    eta_w: float = 0.25
    eta_r: int = 2
    L: int = 1
    w: float = 0.5
    r: float = 0.03
    q: ndarray = field(default_factory=lambda: array([0.01, 0.1, 0.1]))
    p: ndarray = field(default_factory=lambda: array([1.0, 0.8, 0.5]))
    s: ndarray = field(default_factory=lambda: array([0.01, 0.1, 0.25]))
    m_w: float = 0.5
    M: float = 1.0
    M_change_type: str = 'none'
    money_injection_target: str = 'capitalists'
    M_change_interval: int = 20
    M_change_duration: int = 1
    delta_M: int = 1
    shock_type: str = 'culs'
    change_type: str = 'none'
    economy_type: str = 'unrestricted'
    wage_deflation: float = 0.0
    gamma_L: float = 0.3
    atrophy_with_unemployment: str = 'always'
    supply_shock_mag: float = 0.5
    supply_shock_interval: int = 50
    supply_shock_setting: str = 'none'
    change_interval: int = 20
    shock_mag: float = 0.03
    cost_tradeoff: float = 0.01
    stop_cts_changes_halfway: bool = False
    fix_sector_receiving_change: int = -1
    init_tssi_melt: int = 1
    output_equation: str = 'absolute'
    employment_guardrails: bool = False
    s_floor: float = 1e-05
    mu_L: float = 0.5
    eps_u: float = 1e-08
    eps_m: float = 1e-08
    T: int = 100
    res: int = 3
