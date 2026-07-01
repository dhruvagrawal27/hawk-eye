"""M2.4 — Per-model kill-switch (FREE-AI / draft-MRMF: instant model halt without a redeploy).

A runtime DISABLED state per model. When a model is disabled the inference runtime SKIPS it (the
layer degrades gracefully to the remaining layers), so an operator can halt a misbehaving scorer in
seconds without shipping code. ALERT-ONLY invariant preserved: this halts a *scorer*, never money —
and **L1 rules are never disableable** (they don't run through this runtime), so an alert always
survives even if every ML layer is disabled.

State is in-process here; persisting to the governance DB (cross-restart durability) is SCAFFOLD —
the store exposes ``snapshot()``/``restore()`` seams so a DB writer can bind without changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DisableRecord:
    model_id: str
    disabled: bool
    reason: str = ""
    actor: str = ""
    ts: str = ""


@dataclass
class ModelStateStore:
    _disabled: dict[str, DisableRecord] = field(default_factory=dict)

    def disable(self, model_id: str, *, actor: str, reason: str, ts: str) -> DisableRecord:
        rec = DisableRecord(model_id=model_id, disabled=True, reason=reason, actor=actor, ts=ts)
        self._disabled[model_id] = rec
        return rec

    def enable(self, model_id: str, *, actor: str, ts: str) -> DisableRecord:
        rec = DisableRecord(model_id=model_id, disabled=False, reason="re-enabled", actor=actor, ts=ts)
        self._disabled.pop(model_id, None)
        return rec

    def is_disabled(self, model_id: str) -> bool:
        rec = self._disabled.get(model_id)
        return bool(rec and rec.disabled)

    def state(self, model_id: str) -> DisableRecord:
        return self._disabled.get(model_id) or DisableRecord(model_id=model_id, disabled=False)

    def all_disabled(self) -> list[DisableRecord]:
        return [r for r in self._disabled.values() if r.disabled]

    # --- persistence seams (SCAFFOLD: a governance-DB writer can bind here) ---
    def snapshot(self) -> list[dict]:
        return [vars(r) for r in self._disabled.values()]

    def restore(self, rows: list[dict]) -> None:
        for row in rows:
            self._disabled[row["model_id"]] = DisableRecord(**row)

    def reset(self) -> None:
        self._disabled.clear()


MODEL_STATE = ModelStateStore()
