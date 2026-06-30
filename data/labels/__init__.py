"""Label sourcing (DATA-23). Overall status: MOCK.

Blueprint Part 5.4 (the four label sources) + Part 21.3 (real telemetry & PU/semi-sup).
Four complementary sources unified into one store:
  (1) gold historical (Vigilance/CBI/forensic) -- seeded MOCK fixtures (real bank labels
      are unavailable);
  (2) weak/heuristic -- Layer-1 rule hits via Snorkel-style programmatic labelling
      (snorkel optional; pure-python fallback);
  (3) synthetic -- red-team injection ground truth (from DATA-10 Label objects);
  (4) EDD feedback -- fraud/false_positive/inconclusive from BACKEND POST
      /alerts/{id}/disposition (BACKEND.md §5) -- STUB until the endpoint lands.
Plus PU-learning / semi-supervised entry-point hooks to exploit the unlabelled majority.
"""
from data.labels.label_store import (  # noqa: F401
    LabelStore,
    LabelingFunction,
    pu_reliable_negatives,
    self_training_pseudolabels,
    EDD_OUTCOME_TO_FRAUD,
)
