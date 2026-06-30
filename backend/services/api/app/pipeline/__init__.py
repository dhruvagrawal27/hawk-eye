"""Online inference topology (BACKEND-13). Python reference impl of the Rust hot path."""

from app.pipeline.online import ONLINE, OnlinePipeline

__all__ = ["ONLINE", "OnlinePipeline"]
