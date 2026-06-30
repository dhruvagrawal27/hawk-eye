"""CBS posting-log connector (DATA-13). SCAFFOLD: mock fixtures -> L0 (channel=cbs)."""
from data.connectors.cbs.adapter import CbsPostingAdapter, FIXTURE  # noqa: F401

__all__ = ["CbsPostingAdapter", "FIXTURE"]
