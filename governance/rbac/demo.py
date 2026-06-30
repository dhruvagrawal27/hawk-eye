#!/usr/bin/env python3
"""SoD demo (PLATFORM-33): log in as each persona, prove builder≠labeler≠actor≠admin.

Generates a token per persona and attempts EVERY duty, printing an allowed/denied matrix.
The diagonal is the only thing allowed — proof that SoD is enforced in software (Part 19.3).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import route_guards as rg


def main() -> int:
    users = {
        "u_builder": ["builder"],
        "u_labeler": ["labeler"],
        "u_actor": ["actor"],
        "u_admin": ["administrator"],
    }
    duties = ["build_model", "label_data", "act_on_alert", "administer_platform"]
    tokens = {u: rg.make_token(u, p) for u, p in users.items()}

    print("SoD enforcement matrix (✓ allowed, ✗ denied):\n")
    hdr = "persona".ljust(14) + "".join(d[:12].ljust(14) for d in duties)
    print(hdr)
    print("-" * len(hdr))
    ok = True
    for u, personas in users.items():
        row = u.ljust(14)
        for duty in duties:
            # exercise the real route-guard path: decode the persona's JWT + enforce
            try:
                rg.enforce(tokens[u], duty)
                allowed = True
            except rg.SoDViolation:
                allowed = False
            # the ONLY allowed cell is the persona's own duty
            expected = rg.DUTY_PERSONA[duty] in personas
            if allowed != expected:
                ok = False
            row += ("✓" if allowed else "✗").ljust(14)
        print(row)

    print(
        "\nToxic-combination check (an identity holding 2 conflicting personas is rejected):"
    )
    try:
        rg.assert_no_toxic_combo(["builder", "actor"])
        print("  FAIL — builder+actor was allowed")
        ok = False
    except rg.SoDViolation as e:
        print(f"  ✓ rejected: {e}")

    print(
        "\n"
        + (
            "SoD PASS — builder≠labeler≠actor≠administrator enforced."
            if ok
            else "SoD FAIL"
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
