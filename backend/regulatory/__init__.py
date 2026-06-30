"""Regulatory generators (BACKEND-24/25): EWS / RFA / CRILC / FMR / CFR + DAMI + slow-lane.

SCAFFOLD: all logic runs REAL on synthetic data; only the live RBI submission channels are absent.
Alert-only / natural justice — the system flags + evidences, never auto-classifies.
"""

from regulatory import cfr, crilc, ews, fmr, rfa, slow_lane

__all__ = ["cfr", "crilc", "ews", "fmr", "rfa", "slow_lane"]
