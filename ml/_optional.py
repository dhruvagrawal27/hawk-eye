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
from types import ModuleType
from typing import Optional

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


def has(name: str) -> bool:
    """True iff the optional dependency is importable."""
    return optional_import(name) is not None


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


# Eagerly computed convenience flags (used in `if HAS_X:` guards and pytest skips).
HAS_PYOD = has("pyod")
HAS_LIGHTGBM = has("lightgbm")
HAS_XGBOOST = has("xgboost")
HAS_CATBOOST = has("catboost")
HAS_SHAP = has("shap")
HAS_TORCH = has("torch")
HAS_TORCH_GEOMETRIC = has("torch_geometric")
HAS_MLFLOW = has("mlflow")
HAS_EVIDENTLY = has("evidently")
HAS_FAIRLEARN = has("fairlearn")
HAS_FEATURETOOLS = has("featuretools")
HAS_ONNXRUNTIME = has("onnxruntime")
HAS_ONNX = has("onnx")
HAS_SKL2ONNX = has("skl2onnx")
HAS_ONNXMLTOOLS = has("onnxmltools")
HAS_OPENAI = has("openai")
HAS_JINJA2 = has("jinja2")
HAS_FASTAPI = has("fastapi")
HAS_NETWORKX = has("networkx")
HAS_PYGOD = has("pygod")
HAS_DICE_ML = has("dice_ml")


def installed_summary() -> dict[str, bool]:
    """Map every tracked optional dependency to whether it is importable (for logs/inventory)."""
    return {name: has(name) for name in _OPTIONAL}
