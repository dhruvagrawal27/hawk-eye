"""Minimal Prometheus metrics (BACKEND-1, blueprint Part 24.2 l.915).

Hand-rolled, thread-safe, stdlib-only exposition (text format 0.0.4) so the control plane has
no extra runtime dependency. Supports Counter / Gauge / Histogram with labels — enough for
``GET /metrics`` and the latency-budget assertions (Part 18.1). If PLATFORM later standardizes
on ``prometheus_client`` the ``/metrics`` route can swap to it without changing call sites.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Literal

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

_LabelKey = tuple[tuple[str, str], ...]


def _labels_key(labels: dict[str, str] | None) -> _LabelKey:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


def _fmt_labels(key: _LabelKey, extra: tuple[tuple[str, str], ...] = ()) -> str:
    items = list(key) + list(extra)
    if not items:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in items)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class _Metric:
    def __init__(self, name: str, documentation: str, kind: str, labelnames: Iterable[str] = ()):
        self.name = name
        self.documentation = documentation
        self.kind = kind
        self.labelnames = tuple(labelnames)
        self._lock = threading.Lock()


class Counter(_Metric):
    def __init__(self, name: str, documentation: str, labelnames: Iterable[str] = ()):
        super().__init__(name, documentation, "counter", labelnames)
        self._values: dict[_LabelKey, float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with self._lock:
            key = _labels_key(labels)
            self._values[key] = self._values.get(key, 0.0) + amount

    def expose(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.documentation}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, val in self._values.items():
                lines.append(f"{self.name}{_fmt_labels(key)} {_num(val)}")
        return lines


class Gauge(_Metric):
    def __init__(self, name: str, documentation: str, labelnames: Iterable[str] = ()):
        super().__init__(name, documentation, "gauge", labelnames)
        self._values: dict[_LabelKey, float] = {}

    def set(self, value: float, **labels: str) -> None:
        with self._lock:
            self._values[_labels_key(labels)] = value

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        with self._lock:
            key = _labels_key(labels)
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        self.inc(-amount, **labels)

    def expose(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.documentation}", f"# TYPE {self.name} gauge"]
        with self._lock:
            for key, val in self._values.items():
                lines.append(f"{self.name}{_fmt_labels(key)} {_num(val)}")
        return lines


_DEFAULT_BUCKETS = (
    0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0,
)


class Histogram(_Metric):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Iterable[str] = (),
        buckets: Iterable[float] = _DEFAULT_BUCKETS,
    ):
        super().__init__(name, documentation, "histogram", labelnames)
        self.buckets = tuple(sorted(buckets)) + (math.inf,)
        self._counts: dict[_LabelKey, list[int]] = {}
        self._sums: dict[_LabelKey, float] = {}
        self._totals: dict[_LabelKey, int] = {}

    def observe(self, value: float, **labels: str) -> None:
        with self._lock:
            key = _labels_key(labels)
            counts = self._counts.setdefault(key, [0] * len(self.buckets))
            for i, edge in enumerate(self.buckets):
                if value <= edge:
                    counts[i] += 1
            self._sums[key] = self._sums.get(key, 0.0) + value
            self._totals[key] = self._totals.get(key, 0) + 1

    @contextmanager
    def time(self, **labels: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(time.perf_counter() - start, **labels)

    def expose(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.documentation}", f"# TYPE {self.name} histogram"]
        with self._lock:
            for key, counts in self._counts.items():
                cumulative = 0
                for edge, c in zip(self.buckets, counts):
                    cumulative += c
                    le = "+Inf" if math.isinf(edge) else _num(edge)
                    lines.append(
                        f"{self.name}_bucket{_fmt_labels(key, (('le', le),))} {cumulative}"
                    )
                lines.append(f"{self.name}_sum{_fmt_labels(key)} {_num(self._sums[key])}")
                lines.append(f"{self.name}_count{_fmt_labels(key)} {self._totals[key]}")
        return lines


def _num(value: float) -> str:
    if value == int(value) and not math.isinf(value):
        return str(int(value))
    return repr(value)


class Registry:
    """Process-wide metric registry."""

    def __init__(self) -> None:
        self._metrics: list[Counter | Gauge | Histogram] = []
        self._lock = threading.Lock()

    def register(self, metric: Counter | Gauge | Histogram) -> None:
        with self._lock:
            self._metrics.append(metric)

    def render(self) -> str:
        out: list[str] = []
        with self._lock:
            metrics = list(self._metrics)
        for metric in metrics:
            out.extend(metric.expose())
        return "\n".join(out) + "\n"


REGISTRY = Registry()


def _counter(name: str, doc: str, labels: Iterable[str] = ()) -> Counter:
    metric = Counter(name, doc, labels)
    REGISTRY.register(metric)
    return metric


def _gauge(name: str, doc: str, labels: Iterable[str] = ()) -> Gauge:
    metric = Gauge(name, doc, labels)
    REGISTRY.register(metric)
    return metric


def _histogram(name: str, doc: str, labels: Iterable[str] = (), buckets=_DEFAULT_BUCKETS) -> Histogram:
    metric = Histogram(name, doc, labels, buckets)
    REGISTRY.register(metric)
    return metric


# --- Control-plane metrics ---
HTTP_REQUESTS = _counter(
    "hawkeye_http_requests_total", "Total HTTP requests", ("method", "path", "status")
)
HTTP_LATENCY = _histogram(
    "hawkeye_http_request_duration_seconds", "HTTP request latency", ("method", "path")
)
ALERTS_EMITTED = _counter(
    "hawkeye_alerts_emitted_total", "Alerts emitted by the fusion/short-circuit path", ("severity", "path")
)
RULE_HITS = _counter("hawkeye_rule_hits_total", "L1 rule hits", ("rule",))
DISPOSITIONS = _counter("hawkeye_dispositions_total", "EDD dispositions written", ("outcome",))
UNMASK_EVENTS = _counter("hawkeye_pii_unmask_total", "Audited PII unmask events", ("role",))
DEGRADED_MODE = _gauge(
    "hawkeye_degraded_mode", "1 when the path is degraded to L1-rules-only (model server down)"
)
FUSION_LATENCY = _histogram(
    "hawkeye_fusion_duration_seconds",
    "L6 fusion latency (per stage)",
    ("stage",),
    buckets=(0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.3),
)


def render_latest() -> str:
    """Prometheus text exposition for ``GET /metrics``."""
    return REGISTRY.render()


Status = Literal["2xx", "3xx", "4xx", "5xx"]


def track_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record one served request (called by the metrics middleware)."""
    bucket = f"{status_code // 100}xx"
    HTTP_REQUESTS.inc(method=method, path=path, status=bucket)
    HTTP_LATENCY.observe(duration_seconds, method=method, path=path)
