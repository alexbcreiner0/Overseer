import logging
logger = logging.getLogger(__name__)
import numpy as np
from scipy.linalg import eig
import math
from copy import deepcopy
try:
    from .parameters import Params
except Exception:
    pass
from dataclasses import fields, is_dataclass, asdict
from typing import get_origin, get_args
import random
from pathlib import Path

CURRENT_NAMES = ["Corn", "Iron", "Sugar"]
CURRENT_N = 3
COMMODITIES = []
root = Path(__file__).parent.parent
with open( root / "data" / "commodities.txt", "r") as f:
    for line in f:
        COMMODITIES.append(line.strip())

def format_plot_config(params: dict, plotting_data: dict) -> dict:
    data = deepcopy(plotting_data)
    global CURRENT_NAMES

    for _, cat_dict in data.items():
        for _, plot_dict in cat_dict.get("plots", {}).items():
            if plot_dict.get("labels"):
                if len(plot_dict["labels"]) > 1:
                    del plot_dict["labels"]
            if plot_dict.get("label_template"):
                template = plot_dict.get("label_template")
                if not template:
                    continue

                plot_dict["labels"] = [
                    template.format(*CURRENT_NAMES, i=name)
                    for name in CURRENT_NAMES
                ]
        
    real_costs_plots = data["real_costs"]["plots"]
    plots_list = [plot_name for plot_name in real_costs_plots.keys() if plot_name not in {"labor_costs", "spectral_radii"}]
    while len(plots_list) > len(CURRENT_NAMES):
        name = plots_list[-1]
        del real_costs_plots[name]
    
    while len(CURRENT_NAMES) > len(plots_list):
        next_idx = len(plots_list)
        next_name = CURRENT_NAMES[next_idx]
        plots_list.append(f"{next_name.lower()}_costs")
        real_costs_plots[f"{next_name}_costs"] = {
            "checkbox_name": f"Materials Costs of {next_name}",
            "toggled": False,
            "linestyle": "solid",
            "linewidth": 1.5,
            "labels": [f"{name} cost of {next_name}" for name in CURRENT_NAMES],
            "colors": ["red", "green", "blue"],
            "traj_key": f"a_{next_idx}"
        }

    return data

def implement_culs_shock(params, env):
    return {
        "event": "shock_requested",
        "shock_type": "culs"
    }

def implement_cslu_shock(params, env):
    return {
        "event": "shock_requested",
        "shock_type": "cslu"
    }

def implement_cs_shock(params, env):
    return {
        "event": "shock_requested",
        "shock_type": "cs"
    }

def implement_ls_shock(params, env):
    return {
        "event": "shock_requested",
        "shock_type": "ls"
    }


def params_from_mapping(map: dict):
    params_fields = fields(Params)
    kwargs = {}
    for f in params_fields:
        if f.name in map:
            kwargs[f.name] = coerce_value(map[f.name], f.type)

    # field_names = {f.name for f in fields(Params)}
    # filtered = {k: v for k, v in map.items() if k in field_names}
    return Params(**kwargs)

def coerce_value(val, anno):
    """Best-effort coercion based on the dataclass field annotation."""
    if anno is None:
        return val

    # np.ndarray (common case)
    if anno is np.ndarray or getattr(anno, "__name__", "") == "ndarray":
        return np.asarray(val)

    # typing.Optional[T]
    origin = get_origin(anno)
    if origin is not None:
        args = get_args(anno)
        if origin is list:
            # List[T]
            inner = args[0] if args else None
            return [ coerce_value(v, inner) for v in (val or []) ]
        if origin is tuple:
            inner = args[0] if args else None
            return tuple(coerce_value(v, inner) for v in (val or []))
        if origin is dict:
            k_anno, v_anno = (args + (None, None))[:2]
            return { coerce_value(k, k_anno): coerce_value(v, v_anno) for k, v in (val or {}).items() }
        if origin is type(None):  # Optional[None]? ignore
            return val
        if origin is np.ndarray:  # rare typing usage
            return np.asarray(val)

    # Basic scalars
    if anno in (float, int, bool, str):
        try:
            return anno(val)
        except Exception:
            return val  # fall back

    return val  # default: no change

def random_weighted_graph(n, c = 1, weight_range = (1,10)):
    rng = np.random.default_rng()
    unweighted_graph = matrix_to_list(random_adj_matrix(n, c))
    graph = {u: {} for u in unweighted_graph}
    for u in graph:
        for v in unweighted_graph[u]:
            w = rng.integers(weight_range[0], weight_range[1])
            graph[u][v] = int(w)
    return graph

def matrix_to_list(adj_matrix):
    n = len(adj_matrix)
    vertices = list(range(0,n))
    G = {vertices[i]: [] for i in range(n)}
    for i,u in enumerate(G):
        for j in range(n):
            if adj_matrix[i][j] == 1:
                G[u].append(vertices[j])
    return G

def random_adj_matrix(n, c=1):
    p = math.log(n) / n
    adj_matrix = [[0]*n for i in range(n)]
    for i in range(n):
        for j in range(n):
            flip = np.random.binomial(1, p)
            adj_matrix[i][j] = flip
    return adj_matrix

def is_weighted(G):
    if len(G) == 0: return False
    for adj in G.values():
        if type(adj) == dict: return True
        break
    return False

def unweightify(G):
    new_G = {v: {} for v in G}
    for v in new_G:
        new_G[v] = [u for u in G[v].keys()]
    return new_G

def reverse(G):
    rev_G = {u: [] for u in G}
    for u in G:
        for v in G[u]:
            rev_G[v].append(u)
    return rev_G

def connectedness(G, node_order = None):

    if is_weighted(G):
        G = unweightify(G)
    ccnum, comp_id = 0, {u: 0 for u in G}
    visited = {u: False for u in G}

    def explore(u, node_order= None):
        visited[u] = True
        comp_id[u] = ccnum
        for v in G[u]:
            if not visited[v]:
                explore(v)

    if node_order == None:
        node_order = list(G.keys())

    for u in node_order:
        if not visited[u]:
            ccnum += 1
            explore(u)

    return ccnum, comp_id

def pre_post(G):
    
    visited = {u: False for u in G}
    pre, post = {u: None for u in G}, {u: None for u in G}
    clock = 0

    def explore(u):
        nonlocal clock
        visited[u] = True
        clock += 1
        pre[u] = clock

        for v in G[u]:
            if not visited[v]:
                explore(v)
        clock += 1
        post[u] = clock

    for u in G:
        if not visited[u]:
            explore(u)

    return pre, post

def order_by_post_desc(G):
    _, post = pre_post(G)
    return sorted(post, key=post.get, reverse=True)

def strong_connectedness(G):
    if is_weighted(G):
        G = unweightify(G)
    rev_G = reverse(G)
    order = order_by_post_desc(rev_G)
    return connectedness(G, order)

def is_strongly_connected(G):
    ccnum, _ = strong_connectedness(G)
    if ccnum == 1:
        return True
    else: 
        return False

def random_strongly_connected_weighted_graph(n):
    G = random_weighted_graph(n)
    while not is_strongly_connected(G):
        G = random_weighted_graph(n)
    return G

def weighted_graph_to_matrix(G):
    n = len(G)
    matrix = [np.zeros(n) for i in range(n)]
    for i in range(n):
        for j in range(n):
            if j in G[i]:
                matrix[i][j] = G[i][j]
    return np.array(matrix)

def productivize(matrix, epsilon=1e-1):
    evals, _ = eig(matrix)
    index = np.argmax(evals.real)
    if evals[index] >= 1:
        matrix /= (np.abs(evals[index]) + epsilon)
    return matrix

def random_irreducible_productive_matrix(dim):
    G = random_strongly_connected_weighted_graph(dim)
    return productivize(weighted_graph_to_matrix(G))

def random_vector(dim, unif_range= (0,1), random_nonzeros= False):
    if random_nonzeros:
        vec = np.array([np.random.binomial(1, 0.5) for i in range(dim)])
        while np.linalg.norm(vec) == 0:
            vec = np.array([np.random.binomial(3, 0.5) for i in range(dim)])
    else:
        vec = np.ones(dim)

    unif_rolls = np.random.uniform(unif_range[0], unif_range[1], dim)
    vec = vec * unif_rolls
    # for i in range(dim):
    #     num = float(vec[i]*unif_rolls[i])
    #     vec[i] = num

    return vec

def random_parameters(params, env, epsilon=1e-1):
    new_params = deepcopy(params)
    dim = int(params.A.shape[0])
    M = params.M

    # Generate all truly random stuff
    A = random_irreducible_productive_matrix(dim)
    l, p, q = random_vector(dim), random_vector(dim), random_vector(dim) # strictly positive
    b, c = random_vector(dim, random_nonzeros= True), random_vector(dim, random_nonzeros= True) # can have non-negative entries
    eps1, eps2, eps3 = np.random.uniform(1e-3,0.1), np.random.uniform(1e-3,0.1, dim), np.random.uniform(1e-3, 0.1) # random noise/difference factors
    alpha_w, alpha_c = np.random.uniform(1e-3,1), np.random.uniform(1e-3,1) # random scalars
    m_w = np.random.uniform(1e-3, M)

    w, r = np.random.uniform(1e-3,1), np.random.uniform(1e-3,0.1) # might need to adjust to ensure initial output changes are reasonable

    scalar = p.dot(b) / (m_w * alpha_w)
    p /= scalar

    scalar = p.dot(c) / (M-m_w)*alpha_c
    c /= scalar

    scalar = (p.dot(b) / (m_w*alpha_w))

    # b_bar = (p.dot(b) / (m_w*alpha_w)) * b 
    # c_bar = (p.dot(c) / (M-m_w)*alpha_c) * c
    b_bar = b.copy()
    c_bar = c.copy()

    M = A+np.outer(b,l)

    evals, evecs = eig(M)
    idx = np.argmax(evals.real)
    evec, rho = np.abs(evecs[idx]), np.abs(evals[idx])
    A /= (rho + eps1)
    l /= (rho + eps2)

    total_prior_demand = A@q + b + c
    s = total_prior_demand + eps2
    L = q.dot(l) + eps3

    new_params.A = A
    new_params.l = l
    new_params.b_bar = b_bar
    new_params.c_bar = c_bar
    new_params.m_w = m_w
    new_params.alpha_w = alpha_w
    new_params.alpha_c = alpha_c
    new_params.L = L
    new_params.s = s
    new_params.p = p
    new_params.q = q
    new_params.w = w
    new_params.r = r

    global CURRENT_NAMES
    global CURRENT_N
    CURRENT_NAMES = get_new_commodities(CURRENT_N)

    return new_params

def get_new_commodities(n):
    return random.sample(COMMODITIES, n)

def new_dim_vec(params):
    return (params.n, 1)

def new_dim_mat(params):
    return (params.n, params.n)

def sector_names_for_dropdown(params):
    global CURRENT_NAMES
    global CURRENT_N
    if params.n != CURRENT_N:
        old_n = CURRENT_N
        CURRENT_N = params.n
        if old_n > CURRENT_N:
            CURRENT_NAMES = CURRENT_NAMES[:CURRENT_N]
            return ["Random"] + CURRENT_NAMES[:CURRENT_N]
        else:
            n_new = CURRENT_N - old_n
            new_names = get_new_commodities(n_new)
            CURRENT_NAMES += new_names
            return ["Random"] + CURRENT_NAMES
    else:
        return ["Random"] + CURRENT_NAMES

def sector_vals_for_dropdown(params):
    out = [-1]
    for i in range(params.n):
        out.append(i)
    return out

if __name__ == "__main__":
    print(repr(random_irreducible_productive_matrix(5)))
