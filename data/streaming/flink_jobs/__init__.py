"""Flink job scaffolds: base keyed-window job + windowed-feature jobs (DATA-4/22)."""
from data.streaming.flink_jobs.base_job import (  # noqa: F401
    KeyedWindowJob,
    WindowSpec,
    SlidingWindow,
    TumblingWindow,
    flink_available,
)
from data.streaming.flink_jobs.windowed_features import (  # noqa: F401
    velocity_1h,
    tumbling_count,
    compute_windowed_features,
)
