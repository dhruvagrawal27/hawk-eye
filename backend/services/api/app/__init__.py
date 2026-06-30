"""Hawk-Eye control-plane API (FastAPI).

The `app` package is the FastAPI control plane (BACKEND-1..29). It binds to the
cross-cutting packages that live at the ``backend/`` root: ``rules_engine`` (L1/SoD),
``fusion`` (L6), ``serving`` (model serving client), ``regulatory`` (EWS/CRILC/FMR),
``reliability``, ``integrations``, and ``compliance``.

ALERT-ONLY: nothing in this package auto-blocks money or auto-classifies fraud. Every
classification is a human disposition; ``block-request`` is Analyst→Lead, never automatic.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
