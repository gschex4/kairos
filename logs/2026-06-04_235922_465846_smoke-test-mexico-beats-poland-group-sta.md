---
timestamp: 2026-06-04T23:59:22.465846+00:00
status: dry_run
market: "Smoke test — Mexico beats Poland (group stage)"
condition_id: 0xtest_condition_id
token_id: 0xtest_token_9
side: BUY
ask_price: 0.5
estimated_probability: 0.68
confidence: 0.82
computed_size_usd: 1.8
is_exotic: False
dry_run: True
---

# Smoke test — Mexico beats Poland (group stage)

**Decision:** BUY at $0.500 for $1.80
**Status:** `dry_run`
**Estimated probability:** 0.680
**Confidence:** 0.82

## Sizing audit

| Field | Value |
|---|---|
| Bankroll at decision | $18.00 |
| Confidence floor (milestone) | 0.80 |
| Tier ceiling (fraction) | 0.100 |
| Edge (est_prob − ask) | 0.180 |
| Full Kelly fraction | 0.360 |
| Half Kelly fraction | 0.180 |
| Final size fraction | 0.100 |
| Exotic-halved | False |

## Market velocity audit

| Field | Value |
|---|---|
| Source | `live` |
| Has market data | False |
| Trade samples (last 60s) | 0 |
| Net % change (30s) | n/a |
| Largest single-trade jump (60s) | n/a |
| Seconds since that jump | n/a |


## Reasoning

Edge: Mexico starting XI confirmed with full first-choice attack vs Poland resting two regulars. Mexico's Elo edge plus the lineup asymmetry justifies a higher win probability than the 0.50 ask.

## Sources cited

- https://x.com/seleccionmx/status/test1
- https://x.com/laczynasie/status/test2

## Raw result

```json
{}
```
