# Scheduled Change Windows (PLATFORM-19, Part 31.3)

Production changes deploy only within approved windows; enforced by
`python tools/release/release.py window-check` (and gated in CD).

| Window | When (UTC) | Use |
|---|---|---|
| Primary | Sat 18:00–23:00 | planned releases |
| Secondary | Sun 00:00–06:00 | overflow / long migrations |
| Emergency | any time | criticals only, via the emergency-patch path (still audited, CAB-expedited) |

Outside a window, non-emergency production changes are blocked. Error-budget freezes
(observability/slo-definitions.yaml) can additionally halt non-emergency changes.
