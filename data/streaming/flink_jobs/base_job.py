"""Base stateful streaming job: keyed per-entity sliding/tumbling windows (DATA-4).

Blueprint Part 8 (stream processing, l.300) and Part 6 engineering note (l.259):
"Flink jobs compute features and signals, not L4/L5 models" (Part 18.1 hot-path rule).

Status: SCAFFOLD for live PyFlink (pyflink optional; goes live on PLATFORM-1's Flink
1.20 cluster), REAL pure-python fallback that runs a keyed sliding/tumbling window
over any iterable of L0 events with PER-ENTITY STATE and an explicit CHECKPOINTING
concept (snapshot/restore of keyed state). The pure-python path lets DATA-22 windowed
features run with only numpy/pandas/pyarrow.

Determinism: window math is purely a function of (event ts, key) — no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

# --- optional pyflink ---------------------------------------------------------
try:  # pragma: no cover - only when pyflink is installed
    from pyflink.datastream import StreamExecutionEnvironment  # type: ignore

    _HAVE_FLINK = True
except Exception:  # pragma: no cover
    StreamExecutionEnvironment = None  # type: ignore
    _HAVE_FLINK = False


def flink_available() -> bool:
    """True only when pyflink is importable (a live Flink cluster is still required)."""
    return _HAVE_FLINK


def _parse_ts(ts: str) -> float:
    """ISO-8601 '...Z' -> epoch seconds. Tolerant of a trailing Z or an offset."""
    s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@dataclass(frozen=True)
class WindowSpec:
    """A window definition over event-time seconds."""
    size_s: float
    slide_s: Optional[float] = None   # None => tumbling (slide == size)
    kind: str = "sliding"

    @property
    def effective_slide(self) -> float:
        return self.slide_s if self.slide_s is not None else self.size_s


def SlidingWindow(size_s: float, slide_s: float) -> WindowSpec:
    return WindowSpec(size_s=size_s, slide_s=slide_s, kind="sliding")


def TumblingWindow(size_s: float) -> WindowSpec:
    return WindowSpec(size_s=size_s, slide_s=size_s, kind="tumbling")


@dataclass
class _KeyState:
    """Per-entity keyed state: event (ts, payload) buffer + a running counter."""
    events: list[tuple[float, dict]] = field(default_factory=list)
    count: int = 0


class KeyedWindowJob:
    """Pure-python stand-in for a keyed Flink window operator.

    - key_fn(event)        -> partition/state key (default: actor.employee_id)
    - ts_fn(event)         -> event-time seconds (default: parse top-level ts)
    - window               -> WindowSpec (sliding or tumbling)
    - aggregate(key, evs)  -> the feature value over the events currently in-window

    process(event) returns (key, window_end, value). Keyed state is retained so a
    sliding window can look back; old events are evicted once outside the largest
    window. snapshot()/restore() model Flink checkpointing of keyed state.
    """

    def __init__(
        self,
        window: WindowSpec,
        aggregate: Callable[[str, list[dict]], Any],
        key_fn: Optional[Callable[[dict], str]] = None,
        ts_fn: Optional[Callable[[dict], float]] = None,
    ) -> None:
        self.window = window
        self.aggregate = aggregate
        self.key_fn = key_fn or self._default_key
        self.ts_fn = ts_fn or self._default_ts
        self._state: dict[str, _KeyState] = {}

    @staticmethod
    def _default_key(ev: dict) -> str:
        actor = ev.get("actor") or {}
        return str(actor.get("employee_id", "UNKNOWN"))

    @staticmethod
    def _default_ts(ev: dict) -> float:
        ts = ev.get("ts") or (ev.get("context") or {}).get("ts")
        return _parse_ts(ts) if ts else 0.0

    def _evict(self, st: _KeyState, now: float) -> None:
        horizon = now - self.window.size_s
        st.events = [(t, e) for (t, e) in st.events if t > horizon]

    def process(self, event: dict) -> tuple[str, float, Any]:
        """Ingest one event, update keyed state, return (key, window_end, value)."""
        key = self.key_fn(event)
        ts = self.ts_fn(event)
        st = self._state.setdefault(key, _KeyState())
        st.events.append((ts, event))
        st.count += 1
        self._evict(st, ts)
        in_window = [e for (_, e) in st.events]
        value = self.aggregate(key, in_window)
        return key, ts, value

    def run(self, stream: Iterable[dict]) -> list[tuple[str, float, Any]]:
        """Process a finite stream; return all (key, window_end, value) emissions."""
        return [self.process(ev) for ev in stream]

    def latest(self, key: str) -> Any:
        """Aggregate value for `key` over its currently-buffered window."""
        st = self._state.get(key)
        if not st:
            return self.aggregate(key, [])
        return self.aggregate(key, [e for (_, e) in st.events])

    # ---- checkpointing concept (Flink keyed-state snapshot/restore) ----------
    def snapshot(self) -> dict[str, Any]:
        """Serializable snapshot of keyed state (a 'checkpoint barrier' result)."""
        return {
            "window": {"size_s": self.window.size_s,
                       "slide_s": self.window.effective_slide,
                       "kind": self.window.kind},
            "state": {k: {"count": v.count,
                          "events": [(t, e) for (t, e) in v.events]}
                      for k, v in self._state.items()},
        }

    def restore(self, snap: dict[str, Any]) -> None:
        """Restore keyed state from a checkpoint snapshot (recovery semantics)."""
        self._state = {}
        for k, v in (snap.get("state") or {}).items():
            self._state[k] = _KeyState(
                events=[(float(t), e) for (t, e) in v.get("events", [])],
                count=int(v.get("count", 0)),
            )
