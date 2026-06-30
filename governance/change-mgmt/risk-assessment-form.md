# Change Risk-Assessment Form (PLATFORM-19, Part 31.3)

| Dimension | Score (1-5) | Notes |
|---|---|---|
| Blast radius (services affected) | | |
| Detection impact (could it blind detection?) | | rule/threshold changes score high |
| Data/PII exposure | | |
| Reversibility (rollback ease) | | |
| Regulatory impact (RBI/DPDP) | | |

**Risk class** = max-weighted of the above → low / medium / high.
- **high** → CAB + CRO sign-off + change window + rehearsed rollback.
- **medium** → CAB approval + window.
- **low** → standard change, peer review.

Four-eyes mandatory for any rule/threshold/model/config change (Part 24.1 / 19.5).
