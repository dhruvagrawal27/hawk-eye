"""L4 SEQUENCE — the WARNING layer (ML-5).

Blueprint §20.4 / §22.2: run SIMPLE BASELINES FIRST over windowed event streams, then
optionally keep a deep model ONLY if it beats those baselines under HONEST (non-point
-adjust) evaluation. Models score + explain; they never block (ALERT-ONLY).

Public surface:
* windowing      -> ``build_windows``, ``build_verb_sequences``, ``WindowSet``
* baselines      -> ``WindowedPCADetector``, ``WindowedIsolationForestDetector``,
                    ``MatrixProfileDetector``, ``ConvAutoencoderBaseline``,
                    ``all_baselines``, ``run_baselines_first``
* deep (torch)   -> ``USAD``, ``TranAD``, ``AnomalyTransformer``, ``DeepLog``
* explainer      -> ``LAXCAT`` (supervised variable+temporal attention reason codes)
* gate           -> ``keep_if_beats_baselines`` (non-PA: VUS-PR / range-aware PR)

Every module imports even when torch is missing; deep ``fit`` then raises a clear
``require('torch')`` while the PCA/IF/matrix-profile baselines still work, and DeepLog
falls back to a numpy n-gram.
"""

from __future__ import annotations

from ml.layers.l4.anomaly_transformer import AnomalyTransformer
from ml.layers.l4.baselines import (
    ConvAutoencoderBaseline,
    MatrixProfileDetector,
    WindowedIsolationForestDetector,
    WindowedPCADetector,
    all_baselines,
    run_baselines_first,
)
from ml.layers.l4.deeplog import DeepLog
from ml.layers.l4.gate import GateResult, keep_if_beats_baselines
from ml.layers.l4.laxcat import LAXCAT
from ml.layers.l4.tranad import TranAD
from ml.layers.l4.usad import USAD
from ml.layers.l4.windows import (
    WindowSet,
    build_verb_sequences,
    build_windows,
)

__all__ = [
    "build_windows",
    "build_verb_sequences",
    "WindowSet",
    "WindowedPCADetector",
    "WindowedIsolationForestDetector",
    "MatrixProfileDetector",
    "ConvAutoencoderBaseline",
    "all_baselines",
    "run_baselines_first",
    "USAD",
    "TranAD",
    "AnomalyTransformer",
    "DeepLog",
    "LAXCAT",
    "keep_if_beats_baselines",
    "GateResult",
]
