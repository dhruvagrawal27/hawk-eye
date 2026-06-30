"""Per-dataset loaders (DATA-12, Part 5.3 / 17.B).

One loader class per public benchmark. Each:
- `.load(path)` maps the real file to L0 / feature form IF present;
- a tiny synthetic stand-in generator so it runs fully offline (no download).

Datasets & purpose (Part 5.3 table):
- CERT (r4.2/r5.2/r6.2)  -> insider UEBA layers L2/L4
- IEEE-CIS (Vesta)       -> tabular supervised L3
- ULB Credit-Card        -> extreme-imbalance test bed
- PaySim                 -> scale/throughput test (WITH balance-leakage caveat)
- Elliptic               -> graph layer L5
- SPEDIA / Amazon-FDB    -> broader benchmarking / ablations

No drop-in pre-trained model exists for the bank (Part 5.3); public data = prototyping only.
"""
from data.datasets.loaders.cert import CertLoader  # noqa: F401
from data.datasets.loaders.ieee_cis import IeeeCisLoader  # noqa: F401
from data.datasets.loaders.ulb import UlbLoader  # noqa: F401
from data.datasets.loaders.paysim import PaySimLoader  # noqa: F401
from data.datasets.loaders.elliptic import EllipticLoader  # noqa: F401
from data.datasets.loaders.spedia import SpediaLoader  # noqa: F401

ALL_LOADERS = [
    CertLoader,
    IeeeCisLoader,
    UlbLoader,
    PaySimLoader,
    EllipticLoader,
    SpediaLoader,
]
