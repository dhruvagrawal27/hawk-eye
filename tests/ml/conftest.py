"""Shared pytest fixtures for the ML suite (ML-28).

Puts the repo root on sys.path so ``import ml`` and ``import data`` resolve when
pytest is run from anywhere, and provides cached feature-source fixtures.
"""

from __future__ import annotations

import os

# macOS dual-OpenMP hazard (torch libomp vs lightgbm/sklearn libomp): allow the duplicate.
# We do NOT pin OMP_NUM_THREADS here (it destabilised LightGBM); torch threads are pinned below.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import sys
import warnings

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

warnings.filterwarnings("ignore")

# NOTE: we deliberately do NOT `import torch` here. conftest runs in EVERY test process, so
# importing torch globally would load torch's libomp into LightGBM-only processes (e.g. test_l3)
# and trigger the macOS dual-libomp segfault. torch-using test files pin threads themselves
# (test_l4 sets torch.set_num_threads(1); l5's GNN modules set OMP env vars on import).


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
