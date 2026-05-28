from .Economy import get_l_and_c
from dataclasses import fields
from .parameters import Params
import numpy as np
from typing import get_origin, get_args
from copy import deepcopy

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

def random_parameters(params):
    if not params.use_custom_l or not params.use_custom_c:
        return params

    new_params = deepcopy(params)
    
    new_params.l, new_params.c = get_l_and_c(params.L, params.R, tol= params.tol)

    return new_params, None
