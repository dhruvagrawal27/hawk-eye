"""Shared pytest fixtures for the ML suite (ML-28).

Puts the repo root on sys.path so ``import ml`` and ``import data`` resolve when
pytest is run from anywhere, and provides cached feature-source fixtures.
"""
from __future__ import annotations

import os
import sys
import warnings

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

warnings.filterwarnings("ignore")

# Training many tiny torch models back-to-back segfaults under the default OpenMP thread
# pool on macOS; pin to a single thread for the whole ML suite (defensive, suite-wide).
try:  # pragma: no cover
    import torch

    torch.set_num_threads(1)
except Exception:
    pass


@pytest.fixture(scope="session")
def synthetic_source():
    from ml.adapters import SyntheticFeatureSource

    return SyntheticFeatureSource(n_employees=60, n_days=7, seed=1405)


@pytest.fixture(scope="session")
def data_source():
    from ml.adapters import DataSimFeatureSource

    return DataSimFeatureSource()


@pytest.fixture(scope="session")
def supervised_xy(data_source):
    X, y = data_source.supervised_xy()
    return X, y


@pytest.fixture(scope="session")
def entity_xy(data_source):
    return data_source.entity_features(), data_source.entity_labels()
