"""HR/HRMS JML + IGA entitlement/account-modification connectors (DATA-14).
SCAFFOLD: mock fixtures -> L0. HR JML is the highest-value context signal."""
from data.connectors.hr_iga.adapter import FIXTURE, SOURCES, HrIgaAdapter  # noqa: F401

__all__ = ["HrIgaAdapter", "SOURCES", "FIXTURE"]
