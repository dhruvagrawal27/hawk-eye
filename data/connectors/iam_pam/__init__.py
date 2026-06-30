"""IAM/AD + PAM + VPN connectors (DATA-14). SCAFFOLD: mock fixtures -> L0."""
from data.connectors.iam_pam.adapter import FIXTURE, SYSTEMS, IamPamAdapter  # noqa: F401

__all__ = ["IamPamAdapter", "SYSTEMS", "FIXTURE"]
