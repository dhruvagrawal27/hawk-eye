"""CMU-SEI CERT Insider-Threat loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): CERT (r4.2 / r5.2 / r6.2) is *the* canonical synthetic insider
benchmark -- ~1k-4k employees, ~18 months, multi-modal logs (logon, device/USB, file,
email, http, ldap) with injected scenarios (after-hours+USB+exfil, job-hunting+theft,
disgruntled sysadmin keylogger). Use it to prototype the UEBA / insider layers (L2/L4)
and to validate feature-engineering + imbalance handling BEFORE real data is wired.

Leakage caveats:
- CERT ships an `answers/` directory naming the malicious users/scenarios. Those answer
  files are LABELS, not features -- they must never enter the feature frame (see DATA-24
  remove_leaky_features). Keep labels in the Label store, keyed by event_id.
- Extreme class imbalance (a handful of insiders among thousands) -> evaluate with PR-AUC.

No drop-in pre-trained model exists for the bank (Part 5.3); CERT is for transfer/prototyping.

Mapping to L0: CERT `logon.csv` rows -> L0 `login` events; `device.csv` -> `usb` events;
`file.csv` -> `export` / data-layer events; `http.csv` -> `http` events. Each carries the
employee (Actor) and timestamp (Context). Labels live separately (Label objects).
"""
from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np
import pandas as pd

from data.config import SimConfig, make_id, is_off_hours
from data.schemas import L0Event, Actor, Action, ObjectRef, Context
from data.schemas.label import Label

# CERT activity file -> L0 verb/channel mapping.
_CERT_VERB = {
    "logon": ("login", "iam"),
    "device": ("usb", "dlp"),
    "file": ("export", "dlp"),
    "http": ("http", "dlp"),
    "email": ("email", "dlp"),
}


class CertLoader:
    """Loads a CERT release (r4.2/r5.2/r6.2) into L0 events; synthetic stand-in offline."""

    name = "cert"
    purpose = "insider UEBA L2/L4 (CMU-SEI CERT r4.2/r5.2/r6.2)"
    leakage_caveats = (
        "answers/ files are labels, not features; extreme imbalance -> PR-AUC."
    )

    def __init__(self, release: str = "r4.2") -> None:
        self.release = release

    # ---- real-file path -----------------------------------------------------
    def load(self, path: str) -> tuple[list[L0Event], list[Label]]:
        """Map a real CERT release directory to (events, labels) IF present.

        Expects CSVs like `logon.csv`, `device.csv`, `file.csv` with columns
        (id, date, user, pc, activity/...) and an optional `answers/` dir of insiders.
        Falls back to the synthetic stand-in when the directory is absent.
        """
        if not path or not os.path.isdir(path):
            return self.synthetic()

        malicious = self._read_answers(path)
        events: list[L0Event] = []
        labels: list[Label] = []
        for fname, (verb, channel) in _CERT_VERB.items():
            fpath = os.path.join(path, f"{fname}.csv")
            if not os.path.isfile(fpath):
                continue
            df = pd.read_csv(fpath)
            for _, row in df.iterrows():
                user = str(row.get("user", row.get("employee_id", "unknown")))
                ts = self._iso(row.get("date") or row.get("ts"))
                ev = self._to_event(user, verb, channel, ts, str(row.get("pc", "")))
                events.append(ev)
                if user in malicious:
                    labels.append(Label(
                        event_id=ev.event_id, is_fraud=True, scenario_id="cert_insider",
                        actor_id=ev.actor.employee_id, lane="slow",
                        label_source="gold", confidence=1.0,
                    ))
        return events, labels

    @staticmethod
    def _read_answers(path: str) -> set[str]:
        ans_dir = os.path.join(path, "answers")
        users: set[str] = set()
        if not os.path.isdir(ans_dir):
            return users
        for f in os.listdir(ans_dir):
            try:
                df = pd.read_csv(os.path.join(ans_dir, f))
            except Exception:
                continue
            for col in ("user", "employee_id"):
                if col in df.columns:
                    users.update(str(u) for u in df[col].tolist())
        return users

    @staticmethod
    def _iso(v: Any) -> str:
        if v is None:
            return "2024-01-01T00:00:00Z"
        s = str(v).replace(" ", "T")
        return s if s.endswith("Z") else s + "Z"

    @staticmethod
    def _to_event(user: str, verb: str, channel: str, ts: str, host: str) -> L0Event:
        # derive off-hours from the iso hour/weekday cheaply
        try:
            dt = pd.Timestamp(ts)
            offh = is_off_hours(int(dt.hour), int(dt.weekday()))
        except Exception:
            offh = None
        emp = user if user.startswith("EMP-") else make_id("employee", "cert", user)
        return L0Event(
            event_id=make_id("event", "cert", user, verb, ts, host),
            ts=ts,
            actor=Actor(employee_id=emp, role="cert_user", dept="cert"),
            action=Action(verb=verb, channel=channel),
            object=ObjectRef(table=host or None),
            context=Context(ts=ts, layer="application", is_off_hours=offh, host=host or None),
        )

    # ---- offline synthetic stand-in -----------------------------------------
    def synthetic(self, cfg: Optional[SimConfig] = None
                  ) -> tuple[list[L0Event], list[Label]]:
        """Tiny CERT-shaped insider sample: mostly benign logons + one after-hours
        USB-exfil insider, so the loader runs with no download."""
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        users = [f"u{i:03d}" for i in range(12)]
        insider = users[3]
        events: list[L0Event] = []
        labels: list[Label] = []
        for d in range(5):
            for u in users:
                hour = int(rng.integers(9, 18))
                ts = f"2024-01-0{d+1}T{hour:02d}:00:00Z"
                events.append(self._to_event(u, "login", "iam", ts, "PC-1"))
            # insider after-hours USB + file export (the CERT exfil scenario)
            ts_n = f"2024-01-0{d+1}T23:30:00Z"
            ev_usb = self._to_event(insider, "usb", "dlp", ts_n, "PC-9")
            ev_exp = self._to_event(insider, "export", "dlp", ts_n, "PC-9")
            events.extend([ev_usb, ev_exp])
            for ev in (ev_usb, ev_exp):
                labels.append(Label(
                    event_id=ev.event_id, is_fraud=True, scenario_id="cert_insider",
                    actor_id=ev.actor.employee_id, lane="slow",
                    label_source="gold", confidence=1.0,
                ))
        return events, labels


def demo() -> tuple[list[L0Event], list[Label]]:
    """Tiny runnable demo used by tests."""
    return CertLoader().synthetic()
