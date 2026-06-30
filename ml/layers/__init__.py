"""Hawk-Eye model layers (L2 unsupervised ... L6 fusion).

Each ``ml/layers/<l*>/`` package owns one detection layer. Modules always import
even when their heavy dependency is absent: heavy libs are imported *inside*
methods and guarded through ``ml._optional`` so a clean numpy/sklearn fallback runs
where the library is missing (it is present on the reference ``.mlvenv``).
"""
from __future__ import annotations
