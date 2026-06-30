"""Optional-dependency registry (the 'every module imports' guard).

The ML stack uses heavy libraries (PyOD, LightGBM/XGBoost/CatBoost, PyTorch, PyG,
SHAP, MLflow, Evidently, Fairlearn, ONNX, OpenAI, FastAPI, ...). On the reference
machine they are all installed and REAL, but every module is written so it still
*imports* when a library is absent — heavy paths then degrade to a pure-numpy/sklearn
fallback or skip gracefully. Mirror of DATA's "guarded with pure-python fallbacks".

Usage::

    from ml._optional import HAS_TORCH, optional_import, require
    torch = optional_import("torch")          # -> module or None
    lgb = require("lightgbm")                  # -> module, else informative ImportError
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from types import ModuleType
from typing import Optional

# macOS dual-OpenMP hazard: torch ships its own libomp and so do lightgbm/sklearn; loading
# both aborts ("OMP: Error #15"). Allow the duplicate (the recommended workaround). We do NOT
# pin OMP_NUM_THREADS globally (it destabilised LightGBM); thread pinning is done per-process
# in conftest/torch-using modules. setdefault preserves any user-set value.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Canonical import names for every optional dependency we touch.
_OPTIONAL = (
    "pyod",
    "lightgbm",
    "xgboost",
    "catboost",
    "shap",
    "torch",
    "torch_geometric",
    "mlflow",
    "evidently",
    "fairlearn",
    "featuretools",
    "onnxruntime",
    "onnx",
    "skl2onnx",
    "onnxmltools",
    "openai",
    "jinja2",
    "fastapi",
    "networkx",
    "pygod",
    "dice_ml",
)

_cache: dict[str, Optional[ModuleType]] = {}


def optional_import(name: str) -> Optional[ModuleType]:
    """Return the imported module, or ``None`` if it is not installed."""
    if name in _cache:
        return _cache[name]
    try:
        mod = importlib.import_module(name)
    except Exception:  # ImportError or a broken transitive dep — treat as absent
        mod = None
    _cache[name] = mod
    return mod


_has_cache: dict[str, bool] = {}


def has(name: str) -> bool:
    """True iff the optional dependency is INSTALLED — checked WITHOUT importing it.

    Uses ``importlib.util.find_spec`` so probing ``HAS_TORCH`` does not actually load torch
    (which would force torch + LightGBM to co-load and segfault on macOS). The real import
    happens lazily via ``optional_import``/``require`` only when a method actually uses the lib.
    """
    if name in _has_cache:
        return _has_cache[name]
    try:
        result = importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        result = False
    _has_cache[name] = result
    return result


def require(name: str, *, reason: str = "") -> ModuleType:
    """Return the module or raise a clear ImportError telling the user what to install."""
    mod = optional_import(name)
    if mod is None:
        hint = f" ({reason})" if reason else ""
        raise ImportError(
            f"Optional dependency '{name}' is required{hint} but is not installed. "
            f"Install it into the ML venv, e.g. `.mlvenv/bin/python -m pip install {name}`."
        )
    return mod


# LAZY convenience flags: ``HAS_TORCH`` etc. resolve on FIRST ACCESS (module __getattr__),
# so merely importing ml._optional (and thus `import ml`) does NOT pull in torch + lightgbm +
# every heavy lib at once. That keeps torch and LightGBM from being co-loaded into a process
# that only needs one of them — the macOS dual-libomp segfault trigger.
_FLAG_TO_LIB = {
    "HAS_PYOD": "pyod", "HAS_LIGHTGBM": "lightgbm", "HAS_XGBOOST": "xgboost",
    "HAS_CATBOOST": "catboost", "HAS_SHAP": "shap", "HAS_TORCH": "torch",
    "HAS_TORCH_GEOMETRIC": "torch_geometric", "HAS_MLFLOW": "mlflow", "HAS_EVIDENTLY": "evidently",
    "HAS_FAIRLEARN": "fairlearn", "HAS_FEATURETOOLS": "featuretools", "HAS_ONNXRUNTIME": "onnxruntime",
    "HAS_ONNX": "onnx", "HAS_SKL2ONNX": "skl2onnx", "HAS_ONNXMLTOOLS": "onnxmltools",
    "HAS_OPENAI": "openai", "HAS_JINJA2": "jinja2", "HAS_FASTAPI": "fastapi",
    "HAS_NETWORKX": "networkx", "HAS_PYGOD": "pygod", "HAS_DICE_ML": "dice_ml",
}


def __getattr__(name: str) -> bool:
    """Lazily resolve HAS_<LIB> flags on first access (PEP 562 module __getattr__)."""
    if name in _FLAG_TO_LIB:
        return has(_FLAG_TO_LIB[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def installed_summary() -> dict[str, bool]:
    """Map every tracked optional dependency to whether it is importable (for logs/inventory)."""
    return {name: has(name) for name in _OPTIONAL}
