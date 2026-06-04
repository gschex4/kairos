---
timestamp: 2026-06-04T23:59:23.151039+00:00
status: dry_run
market: "Smoke test — Mexico beats Poland (group stage)"
condition_id: 0xtest_condition_id
token_id: 0xtest_token_14
side: BUY
ask_price: 0.5
estimated_probability: 0.65
confidence: 0.8
computed_size_usd: 5.0
is_exotic: False
dry_run: True
---

# Smoke test — Mexico beats Poland (group stage)

**Decision:** BUY at $0.500 for $5.00
**Status:** `dry_run`
**Estimated probability:** 0.650
**Confidence:** 0.80

## Sizing audit

| Field | Value |
|---|---|
| Bankroll at decision | $50.00 |
| Confidence floor (milestone) | 0.60 |
| Tier ceiling (fraction) | 0.100 |
| Edge (est_prob − ask) | 0.150 |
| Full Kelly fraction | 0.300 |
| Half Kelly fraction | 0.150 |
| Final size fraction | 0.100 |
| Exotic-halved | False |

## Market velocity audit

| Field | Value |
|---|---|
| Source | `agent_override` |
| Has market data | True |
| Trade samples (last 60s) | 0 |
| Net % change (30s) | 1.00% |
| Largest single-trade jump (60s) | 2.00% |
| Seconds since that jump | 200 |


## Reasoning

Edge: Mexico starting XI confirmed with full first-choice attack vs Poland resting two regulars. Mexico's Elo edge plus the lineup asymmetry justifies a higher win probability than the 0.50 ask.

## Sources cited

- https://x.com/seleccionmx/status/test1
- https://x.com/laczynasie/status/test2

## Raw result

```json
{}
```
