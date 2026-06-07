---
name: kairos-settlement
title: Kairos — Settlement, Reconciliation & CLV
description: >
  Post-trade workflow for the Kairos betting agent: monitoring open positions,
  reconciling Kalshi settlements, computing realized P&L and closing-line value
  (CLV), reading the bet journal, and cash-out decisions. Load this for settle /
  reconcile / performance / CLV / P&L / cash-out tasks (e.g. the daily-settle
  cron) — bet discovery, sizing, and placement live in the kairos-philosophy skill.
domain: betting, kalshi, settlement, clv, reconciliation
---

# Kairos — Settlement, Reconciliation & CLV

This skill covers everything **after** a bet is placed. Bet discovery, fair
value, sizing, and order placement live in **kairos-philosophy**. Settlement is
**read-only analysis** — the only write action here is a deliberate cash-out,
which still goes through `kairos_evaluate_bet` (rails enforced), never a raw order.

Host reminder: Windows native git-bash (MSYS2). Pass `workdir="/tmp"` to every
`terminal()` call; the Windows C: drive is mounted at `/c/`.

## Data sources (Kalshi, RSA-signed)

The `kairos_reconcile_positions` / `kairos_performance` plugin tools are
**NON-FUNCTIONAL** on this host (legacy Polymarket; they demand
POLYMARKET_PRIVATE_KEY). Do **not** call them. Reconcile via the Kalshi API
directly, RSA-signed, using the signing recipe in the **kairos-philosophy**
skill's `references/kalshi-api.md` (Reconciliation section). Base
`https://api.elections.kalshi.com`:

| Endpoint | Purpose |
|---|---|
| `GET /trade-api/v2/portfolio/balance` | Current cash balance |
| `GET /trade-api/v2/portfolio/positions` | Open positions (resting + settled) |
| `GET /trade-api/v2/portfolio/settlements` | Resolved markets + your win/loss result |

Call all three in **one** script with a **fresh RSA timestamp per call** (the
signed message is `{ts_ms}{METHOD}{path}`). Keeps you under the ~50KB Hermes
stdout cap and avoids re-auth churn.

## The bet journal — canonical machine-readable history

Every `kairos_evaluate_bet` outcome — **placed, dry_run, AND rejected** — is
appended to `~/.hermes/logs/bet_journal.jsonl` by a `post_tool_call` hook. One
JSON object per line:

```json
{"ts":"…Z","tool":"kairos_evaluate_bet","status":"placed|dry_run|rejected",
 "input":{"market_question":"…","token_id":"KXWCGAME-…","condition_id":"…",
 "side":"BUY","price":0.24,"estimated_probability":0.31,"confidence":0.7},
 "result":{…},"duration_ms":88}
```

This is the only place **rejected** bets are recorded (the markdown
`log_bet_decision` only fires for placed/dry_run — the rails reject before it
runs). Use it to:
- match placed bets to their settlements by `token_id`,
- compute realized P&L and CLV per bet,
- audit rejections — which rail fired, how often — to refine confidence/sizing.

Read pattern (workdir=/tmp):
```bash
cat /c/Users/gsche/.hermes/logs/bet_journal.jsonl \
  | python -c "import sys,json; [print(json.dumps(json.loads(l))) for l in sys.stdin if l.strip()]"
```
Filter `status=='placed'` for live positions; tally `status=='rejected'` reasons
for the rejection audit.

## Realized P&L (per settled position)

A BUY stakes `S` dollars at entry price `p`, buying `S/p` contracts that each pay
$1 on a win:

- **win** → profit = `S * (1 - p) / p`
- **loss** → `-S`

SELL is approximated as buying the complement at `(1 - p)`. The agent is steered
to BUY (express a negative view by buying the NO contract), so SELL P&L is an
estimate, not exact. Report **realized P&L today** and **cumulative vs the $50
starting bankroll**.

## Closing-line value (CLV) — the skill metric

CLV measures whether you beat the market's closing price. Positive = good:

- **BUY:**  `clv = closing_price − entry_price`  (you bought cheaper than the close)
- **SELL:** `clv = entry_price − closing_price`  (you sold richer than the close)

"Closing price" on Kalshi = the market's last YES price just before kickoff (or
before resolution). Pull it from `GET /markets/{ticker}` (`last_price` /
`previous_yes_ask`) as close to kickoff as you can, and record it against the
journal entry's `entry_price`.

**CLV is the leading indicator of edge.** Track it even before settlements land:
a bettor with consistently positive CLV is beating the market regardless of
short-run win/loss variance. A run of negative CLV means the fair-value model is
mispriced — flag it for review even if the bets happen to win.

## Monitoring open positions

`par-position-watch` cron runs hourly 8am–10pm: it fetches current prices on all
open positions and alerts the **World Cup** group **only** when a position has
moved **>3¢** from entry. Silent otherwise — no spam.

## Cash-out criteria

- **Price reaches 80%+ of fair value** → consider taking profit (diminishing edge).
- **Volume implodes** (open interest drops >50%) → liquidity risk, consider exiting.
- **Lineup news contradicts the thesis** → cut immediately (e.g. a key starter ruled out).
- **New, better edge emerges and bankroll is tight** → rotate out of the weakest position.

A cash-out is a real order — route it through `kairos_evaluate_bet` (sell side),
never a hand-placed `POST /portfolio/events/orders`.

## What to report (daily-settle)

Deliver to the **World Cup** group:
1. Settled markets since last run + win/loss + realized P&L (today and cumulative vs $50).
2. Open positions: current mark + unrealized P&L + CLV on recently-closed lines.
3. The rejection audit only if notable (e.g. the same rail fired repeatedly).

End with `[SILENT]` when nothing settled and no open position moved >3¢ — do not
spam. Report what **happened**, not what you are considering.
