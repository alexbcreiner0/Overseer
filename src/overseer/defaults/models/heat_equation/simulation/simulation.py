from .parameters import Params
from typing import Optional, Callable
import numpy as np
import scipy.sparse as sp
from scipy.integrate import solve_ivp
import logging

logger = logging.getLogger(__name__)

MODEL_READY = False # Set this to True when you think it's ready.
HEAVY_COMPUTE = False # Set true if some sims are compute-heavy (app will attempt to boost performance in various ways).

def get_trajectories(params: Params, *, should_stop: Optional[Callable[[], bool]]= None, yield_every: int= 1):
    traj = {}
    t = [0.0]
    res, T = params.res, params.T
    nx, ny = 120, 80
    Lx, Ly = 1.0, 1.0
    dx, dy = Lx/(nx-1), Ly/(ny-1)

    L = laplacian_2d_dirichlet_sparse(nx, ny, dx, dy)

    x = np.linspace(0, Lx, nx)
    y = np.linspace(0, Ly, ny)

    X, Y = np.meshgrid(x,y)
    sigma = 0.08
    # u = np.exp(-(((X - 0.6)**2 + (Y - 0.5)**2) / (2*sigma**2)))
    alpha = params.alpha

    rng = np.random.default_rng(seed= None)  # seed=None for true randomness per run

    x0 = rng.uniform(0.0, Lx)
    y0 = rng.uniform(0.0, Ly)

    sigma_x = rng.uniform(0.03*Lx, 0.15*Lx)
    sigma_y = rng.uniform(0.03*Ly, 0.15*Ly)

    A = rng.uniform(0.5, 2.0)
    B = 0.0

    u = gaussian_blob(X, Y, x0=x0, y0=y0, sigma_x=sigma_x, sigma_y=sigma_y, A=A, B=B)

    dt = 0.25 * min(dx*dx, dy*dy) / alpha

    traj = {
        "u": np.array([u])
    }

    # example iterative template
    current_t = 0.0
    for i in range(T):
        # logger.debug(f"running step {i}")
        print(f"running step {i}")
        # necessary for allowing your sim to be paused or stopped 
        if should_stop and should_stop():
            break

        t_eval = np.linspace(current_t, current_t+1, res+1)[1:]
        new_t, new_u, sol = solve_heat_dirichlet_sparse(u, x, y, t_eval= t_eval, L= L, alpha= alpha)
        
        m = sol.y.shape[1]
        for i in range(m):
            current_t = new_t[i]
            u = new_u[i]
            traj["u"] = np.append(traj["u"], new_u, axis= 0)
            t.append(current_t)

            if (i % yield_every) == 0:
                yield dict(traj), t.copy()

    yield dict(traj), t.copy()

def gaussian_blob(X, Y, *, x0, y0, sigma_x, sigma_y, A=10.0, B=0.0):
    return B + A * np.exp(-(((X - x0)**2) / (2*sigma_x**2) + ((Y - y0)**2) / (2*sigma_y**2)))

def laplacian_2d_dirichlet_sparse(nx: int, ny: int, dx: float, dy: float) -> sp.csr_matrix:
    """
    Dirichlet=0 boundaries, unknowns are interior only: (ny-2) x (nx-2).
    Returns L of shape (N, N) acting on y = u_interior.ravel() (row-major).
    """
    nx_i = nx - 2
    ny_i = ny - 2
    if nx_i <= 0 or ny_i <= 0:
        raise ValueError("Grid too small for interior unknowns.")

    ex = np.ones(nx_i)
    ey = np.ones(ny_i)

    Tx = sp.diags([ex, -2 * ex, ex], [-1, 0, 1], shape=(nx_i, nx_i), format="csr") / (dx * dx)
    Ty = sp.diags([ey, -2 * ey, ey], [-1, 0, 1], shape=(ny_i, ny_i), format="csr") / (dy * dy)

    # Kronecker sum: I_y ⊗ Tx + Ty ⊗ I_x
    L = sp.kron(sp.eye(ny_i, format="csr"), Tx, format="csr") + sp.kron(Ty, sp.eye(nx_i, format="csr"), format="csr")
    return L

def solve_heat_dirichlet_sparse(u0_full, x, y, t_eval, L, alpha=0.01,
                                method="BDF", rtol=1e-6, atol=1e-8):
    """
    Sparse Laplacian version. Dirichlet boundary values are held fixed at u0_full boundaries.
    Unknowns are interior only.
    """
    ny, nx = u0_full.shape

    u0 = u0_full[1:-1, 1:-1].ravel()

    def rhs(t, yy):
        return alpha * (L @ yy)

    # Help BDF/Radau by providing sparsity structure (pattern only)
    jac_sparsity = (L != 0).astype(int)

    # IMPORTANT: span must cover the eval interval
    t_span = (float(t_eval[0]), float(t_eval[-1]))

    # Optional: keep solver from taking huge steps relative to your output sampling
    max_step = float(t_eval[1] - t_eval[0]) if len(t_eval) > 1 else np.inf

    sol = solve_ivp(
        fun=rhs,
        t_span=t_span,
        y0=u0,
        t_eval=t_eval,
        method=method,
        rtol=rtol,
        atol=atol,
        jac_sparsity=jac_sparsity,
        max_step=max_step,
    )

    # Reconstruct full field with fixed boundaries
    U = np.zeros((len(sol.t), ny, nx), dtype=float)
    for k in range(len(sol.t)):
        U[k, :, :] = u0_full  # boundary values fixed from initial
        U[k, 1:-1, 1:-1] = sol.y[:, k].reshape(ny - 2, nx - 2)

    return sol.t, U, sol

if __name__ == "__main__":
    nx, ny = 120, 80
    Lx, Ly = 2.0, 1.0
    dx, dy = Lx/(nx-1), Ly/(ny-1)

    x = np.linspace(0, Lx, nx)
    y = np.linspace(0, Ly, ny)

    X, Y = np.meshgrid(x,y)

    u = np.exp(-((X-0.6)**2) + (Y-0.5)**2) / (2*(0.08**2))
    print(f"{u=}")


