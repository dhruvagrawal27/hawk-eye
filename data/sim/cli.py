"""Simulator CLI (DATA-7/10).

Blueprint Part 21.1. Runs the Simulator and writes events + labels to Parquet (pyarrow)
and JSONL under SimConfig.out_dir/<run>/. Runnable:

    python -m data.sim.cli --employees 100 --days 7

Status: REAL (synthetic-only). Writes locally via the eventbus sinks; a KafkaSink swaps in
when PLATFORM provisions Kafka (config change, not a rewrite).
"""
from __future__ import annotations

import argparse
import os
from dataclasses import replace

from data.config import SimConfig, Topics
from data.eventbus import JsonlSink, KafkaSink, ParquetSink
from data.sim.simulator import Simulator


def _run_id(cfg: SimConfig) -> str:
    return f"sim_e{cfg.n_employees}_d{cfg.days}_s{cfg.seed}"


def run(cfg: SimConfig, run_name: str | None = None, to_kafka: bool = False) -> dict:
    """Run the simulator and write events/labels to Parquet + JSONL. Returns a manifest."""
    sim = Simulator(cfg)
    event_dicts, label_dicts = sim.run_records()

    run_name = run_name or _run_id(cfg)
    out_dir = os.path.join(cfg.out_dir, run_name)
    os.makedirs(out_dir, exist_ok=True)

    paths = {
        "events_parquet": os.path.join(out_dir, "events.parquet"),
        "events_jsonl": os.path.join(out_dir, "events.jsonl"),
        "labels_parquet": os.path.join(out_dir, "labels.parquet"),
        "labels_jsonl": os.path.join(out_dir, "labels.jsonl"),
    }

    with ParquetSink(paths["events_parquet"]) as ep, JsonlSink(paths["events_jsonl"]) as ej:
        for row in event_dicts:
            ep.write(row)
            ej.write(row)
    with ParquetSink(paths["labels_parquet"]) as lp, JsonlSink(paths["labels_jsonl"]) as lj:
        for row in label_dicts:
            lp.write(row)
            lj.write(row)

    if to_kafka:
        ks = KafkaSink(Topics.EVENTS_RAW)
        if ks.available:
            for row in event_dicts:
                ks.write(row)
            ks.close()

    manifest = {
        "run": run_name,
        "out_dir": out_dir,
        "n_events": len(event_dicts),
        "n_labels": len(label_dicts),
        "n_fraud": sum(1 for r in label_dicts if r.get("is_fraud")),
        "paths": paths,
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Hawk-Eye synthetic insider-fraud simulator (DATA-7/10)")
    p.add_argument("--employees", type=int, default=100, help="number of employees")
    p.add_argument("--days", type=int, default=7, help="number of days to simulate")
    p.add_argument("--seed", type=int, default=SimConfig.seed, help="rng seed (determinism)")
    p.add_argument("--out-dir", type=str, default=SimConfig.out_dir, help="output base dir")
    p.add_argument("--run-name", type=str, default=None, help="optional run name")
    p.add_argument("--kafka", action="store_true", help="also publish events to Kafka if available")
    args = p.parse_args(argv)

    cfg = replace(
        SimConfig(),
        n_employees=args.employees,
        days=args.days,
        seed=args.seed,
        out_dir=args.out_dir,
    )
    manifest = run(cfg, run_name=args.run_name, to_kafka=args.kafka)
    print(
        f"[DATA-7] wrote {manifest['n_events']} events "
        f"({manifest['n_fraud']} fraud labels) to {manifest['out_dir']}"
    )
    for k, v in manifest["paths"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
