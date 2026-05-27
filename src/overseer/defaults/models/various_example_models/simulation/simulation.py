from typing import Any
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import random
from PIL import Image
import scipy.sparse as sp
from scipy.integrate import solve_ivp

def random_hex_color():
    """Return a list of n random colors in hexadecimal form."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"

def curve_demo_3d(params: Params, event_queue):
    a, b = params.a, params.b

    eps = 0.03
    t = 0.0

    for _ in range(1000000):
        t += eps
        traj = {
            "sine": Append(a*np.sin(b*t)),
            "cosine": Append(b*np.cos(b*t)),
            "z": Append(1/(0.01*np.sqrt(t))),
            "color": Append(random_hex_color()),
            "size": Append(random.randint(1,300))
        }

        yield traj, Append(t)

def surface_demo(params: Params, event_queue):
    t = 0
    eps = 0.5
    X, Y, Z = _surface_frame(t)
    traj = {
        "X": Replace(X),
        "Y": Replace(Y),
        "Z": Replace(Z),
        "t": Append(t)
    }
    for _ in range(10000):
        yield traj
        t += eps
        X, Y, Z = _surface_frame(t)
        traj = {
            "X": Replace(X),
            "Y": Replace(Y),
            "Z": Replace(Z),
            "t": Append(t)
        }

def vector_field_demo(params: Params, event_queue):
    vec_x = np.arange(-10, 11, 1)
    vec_y = np.arange(-10, 11, 1)
    Xg, Yg = np.meshgrid(vec_x, vec_y, indexing="xy")

    base_U = -Yg.astype(float)
    print(f"{base_U=}")
    base_V = Xg.astype(float)
    print(f"{base_V=}")

    traj = {
        "vec_X": Xg,
        "vec_Y": Yg
    }

    t = np.array([0.0])
    epsilon = 0.5e-2

    for _ in range(10000):
        current_t = t[-1]

        angle = 0.8 * current_t
        ca = np.cos(angle)
        sa = np.sin(angle)
        rot_U = base_U * ca - base_V * sa
        rot_V = base_U * sa + base_V * ca

        cx = 6.0 * np.cos(0.9 * current_t)
        cy = 6.0 * np.sin(1.2 * current_t)

        sigma_env = 2.2
        env = np.exp(-((Xg - cx) ** 2 + (Yg - cy) ** 2) / (2 * sigma_env**2))
        env = np.where(env > 0.18, env, 0.0)

        pulse = 0.5 * (1.0 + np.sin(3.0 * current_t))
        amp = env * pulse

        vec_U = amp * rot_U
        vec_V = amp * rot_V

        traj["vec_U"] = vec_U
        traj["vec_V"] = vec_V

        traj["vec_C"] = np.absolute(vec_U + vec_V)

        yield traj, t

        t = np.append(t, t[-1]+epsilon)

def _surface_frame(t):
    x = np.linspace(-5, 5, 50)
    y = np.linspace(-5, 5, 50)
    X, Y = np.meshgrid(x, y)

    x1 = 1.5 * np.cos(0.03 * t)
    y1 = 1.5 * np.sin(0.03 * t)

    x2 = 1.5 * np.cos(0.025 * t + np.pi)
    y2 = 1.5 * np.sin(0.04 * t)

    r1 = np.sqrt((X - x1)**2 + (Y - y1)**2)
    r2 = np.sqrt((X - x2)**2 + (Y - y2)**2)

    Z = (
        np.sin(5 * r1 - 0.18 * t) / (1 + 0.35 * r1)
        + np.sin(4 * r2 - 0.15 * t) / (1 + 0.35 * r2)
    )

    return X, Y, Z

def scatter_demo(params, event_queue):
    rng = np.random.default_rng()
    sample = rng.random(size= (100,3))

    x_points = sample[:,0]
    y_points = sample[:,1]
    z_points = sample[:,2]

    return { "x_pts": x_points, "y_pts": y_points, "z_pts": z_points }

def cts_heatmap_demo(params, event_queue):
    t = [0.0]
    res, T = 3, 100
    nx, ny = 120, 80
    Lx, Ly = 0.8, 0.8
    dx, dy = Lx/(nx-1), Ly/(ny-1)

    L = laplacian_2d_dirichlet_sparse(nx, ny, dx, dy)

    x = np.linspace(0, Lx, nx)
    y = np.linspace(0, Ly, ny)

    X, Y = np.meshgrid(x,y)
    alpha = 0.01

    rng = np.random.default_rng(seed= None) 

    x0 = rng.uniform(0.1*Lx, 0.9*Lx)
    y0 = rng.uniform(0.1*Ly, 0.9*Ly)

    sigma_x = rng.uniform(0.03*Lx, 0.15*Lx)
    sigma_y = rng.uniform(0.03*Ly, 0.15*Ly)

    A = rng.uniform(0.5, 2.0)
    B = 0.0

    u = gaussian_blob(X, Y, x0=x0, y0=y0, sigma_x=sigma_x, sigma_y=sigma_y, A=A, B=B)

    traj = {
        "u": Replace(u)
    }

    yield traj

    current_t = 0.0
    for i in range(T):
        t_eval = np.linspace(current_t, current_t+1, res+1)[1:]
        new_t, new_u, sol = solve_heat_dirichlet_sparse(u, x, y, t_eval= t_eval, L= L, alpha= alpha)
        
        m = sol.y.shape[1]
        for i in range(m):
            current_t = new_t[i]
            u = new_u[i]
            traj["u"] = Replace(u)
            t.append(current_t)

            yield dict(traj), t.copy()

    yield dict(traj), t.copy()

def gaussian_blob(X, Y, *, x0, y0, sigma_x, sigma_y, A=10.0, B=0.0):
    return B + A * np.exp(-(((X - x0)**2) / (2*sigma_x**2) + ((Y - y0)**2) / (2*sigma_y**2)))

def laplacian_2d_dirichlet_sparse(nx: int, ny: int, dx: float, dy: float) -> sp.csr_matrix:
    nx_i = nx - 2
    ny_i = ny - 2
    if nx_i <= 0 or ny_i <= 0:
        raise ValueError("Grid too small for interior unknowns.")

    ex = np.ones(nx_i)
    ey = np.ones(ny_i)

    Tx = sp.diags([ex, -2 * ex, ex], [-1, 0, 1], shape=(nx_i, nx_i), format="csr") / (dx * dx)
    Ty = sp.diags([ey, -2 * ey, ey], [-1, 0, 1], shape=(ny_i, ny_i), format="csr") / (dy * dy)

    L = sp.kron(sp.eye(ny_i, format="csr"), Tx, format="csr") + sp.kron(Ty, sp.eye(nx_i, format="csr"), format="csr")
    return L

def solve_heat_dirichlet_sparse(u0_full, x, y, t_eval, L, alpha=0.01,
                                method="BDF", rtol=1e-6, atol=1e-8):
    ny, nx = u0_full.shape
    u0 = u0_full[1:-1, 1:-1].ravel()
    def rhs(t, yy):
        return alpha * (L @ yy)

    jac_sparsity = (L != 0).astype(int)
    t_span = (float(t_eval[0]), float(t_eval[-1]))

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

    U = np.zeros((len(sol.t), ny, nx), dtype=float)
    for k in range(len(sol.t)):
        U[k, :, :] = u0_full 
        U[k, 1:-1, 1:-1] = sol.y[:, k].reshape(ny - 2, nx - 2)

    return sol.t, U, sol

