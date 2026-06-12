---
name: kairos-settlement
description: >
  Post-trade workflow: reconcile Kalshi settlements, compute realized P&L and
  closing-line value (CLV), monitor open positions, and decide cash-outs.
  Load this for settle / reconcile / performance / CLV / P&L / cash-out tasks.
  Bet discovery, sizing, and placement live in kairos-philosophy.
category: kairos
---

# Kairos — Settlement, Reconciliation & CLV

Everything **after** a bet is placed. Settlement is **read-only analysis**;
the only write action is a deliberate cash-out, which goes through
`place_bet.py sell --ticker T --price P --count N --reasoning "..."`
(kairos-philosophy `scripts/` — journals the exit), never a raw order.

## Platform

- **Kalshi** (CFTC-regulated). Public API: `api.elections.kalshi.com/trade-api/v2/`.
- All `kairos_*` plugin tools are **DEAD** on this host (legacy Polymarket bindings
  that demand `POLYMARKET_PRIVATE_KEY`). Do **not** call `kairos_reconcile_positions`,
  `kairos_performance`, `kairos_get_bankroll`, `kairos_get_market_price`, etc.
- Instead, run the scripts in this skill's `scripts/` directory via `terminal()`.

## Windows Host Execution

- Shell: git-bash (POSIX), not PowerShell. Pass `workdir="/tmp"` to every `terminal()` call.
- Write scripts to `/tmp/foo.py` (resolves to `C:\tmp\foo.py`) then run with `python3 "C:/tmp/foo.py"`.
- The RSA signing helper lives at `C:\Users\gsche\.hermes\kalshi\kalshi_auth.py`.
  Import it via `sys.path.insert(0, r"C:\Users\gsche\.hermes\kalshi")` — do NOT
  try to put `kalshi_key.pem` next to the calling script.

## Daily-Settle Sequence

### Step 1 — Pull Data from Kalshi

**⚠️ Do NOT write reconciliation or price-check scripts from scratch.** The
scripts in this skill's `scripts/` directory are battle-tested and handle
Windows paths, RSA signing, and the Kalshi response schema correctly.
Inline scripts waste time and introduce path/auth bugs.

Copy the script to `/tmp/` and run it:

```bash
cp "/c/Users/gsche/.hermes/skills/kairos-settlement/scripts/reconcile.py" /tmp/
python3 /tmp/reconcile.py
```

It hits three endpoints with fresh RSA timestamps per call and dumps one JSON blob:

| Endpoint | What |
|---|---|
| `GET /trade-api/v2/portfolio/balance` | Cash balance, portfolio value |
| `GET /trade-api/v2/portfolio/positions` | Open positions (market-level + event-level) |
| `GET /trade-api/v2/portfolio/settlements` | Resolved markets with outcome + revenue |

### Step 2 — Price-Check Open Positions

Filter to World Cup positions only (tickers starting with `KXWC`). Copy and
pipe tickers via stdin:

```bash
cp "/c/Users/gsche/.hermes/skills/kairos-settlement/scripts/price_check.py" /tmp/
echo -e "KXWCGAME-26JUN12USAPAR-PAR\nKXWCGAME-26JUN14CIVECU-ECU" | python3 /tmp/price_check.py
```

Or pipe from a temp file if there are many tickers. Do not write a new price
script — the existing one handles auth correctly.

### Step 3 — Reconcile vs Bet Journal

The bet journal at `~/.hermes/logs/bet_journal.jsonl` is the canonical
machine-readable history. Every `place_bet.py` outcome — placed, dry_run,
AND rejected — is appended by the script itself. One JSON per line:

```json
{"ts":"…Z","tool":"place_bet.py","status":"placed|dry_run|rejected",
 "rail":"R2-edge (rejected only)","input":{"ticker":"KXWCGAME-…","prob":…,…},"result":{…}}
```

Filter `status=='placed'` to match against settlements by `input.ticker`.
Filter `status=='rejected'` to audit which rails fired (`rail` field).

**NB**: positions placed before Jun 10, 2026 (pre-script era) appear on Kalshi
but NOT in the journal — reconcile those by ticker match against the positions
endpoint. Journal entries dated Jun 10 with `status: dry_run` and reasoning
"test dry run"/"test" are script validation runs, not bets.

### Step 4 — Compute Realized P&L per Settlement

For each settled position:

- **BUY YES, won**: `profit = revenue_dollars − yes_total_cost_dollars`
- **BUY YES, lost**: `loss = yes_total_cost_dollars` (revenue = 0)
- If both YES and NO shares held (`yes_count_fp` > 0 AND `no_count_fp` > 0):
  total cost = `yes_total_cost + no_total_cost`; winner side pays out at $1/share.

Kalshi's `revenue` field is in **cents** (e.g., `500` = $5.00 payout on a win).

Sum realized P&L (pre-fee and post-fee) across all settlements. Report
**today's** realized P&L and **cumulative vs the $50 starting bankroll**.

### Step 5 — Compute CLV per Position

CLV = closing price − entry price for BUY positions. Positive = good.

"Closing price" = the market's `last_price_dollars` just before kickoff.
If the match hasn't started yet, CLV is a running mark (current ask − entry).

Track average CLV and positive-CLV rate. **CLV is the leading indicator of edge**
— consistently positive CLV means the fair-value model beats the market even on
small samples.

### Step 6 — What to Report

Deliver to the World Cup group:

1. Settled WC markets since last run + win/loss + realized P&L (today and cumulative vs $50).
2. Open WC positions: ticker, shares, entry price, current ask, Δ in cents, unrealized P&L.
3. Rejection audit (only if notable — same rail fired repeatedly).

**Silence rule**: End with `[SILENT]` when (a) nothing settled since last run,
AND (b) no open position moved ≥15% relative from entry (`|current − entry| / entry * 100`).
This filters Kalshi spread noise — flat 3¢ was too tight for Kalshi's thinner order books
and was replaced Jun 5. Do not combine `[SILENT]` with content — either report findings
normally, or say `[SILENT]` and nothing more.

## Cash-Out Criteria

Cash-out logic depends on which **kind** of position it is (see
`trade-screen.md` for the distinction):

**Conviction / hold-to-resolution positions** (most match-win bets): match-day exit
only — once the match kicks off, the position rides to resolution. Pre-match exit
only on thesis invalidation (lineup news, injury to key player).

**Trade / re-rate positions** (bought cheap to sell into a price rise — futures,
props, awards, or any cheap contract held as a trade): the thesis is to **sell
into the re-rate, not to hold for the outcome**. The exit ladder, catalyst-timed
selling mechanic, stop-losses, and liquidity rules live in ONE place:
`references/trade-exit-strategy.md` (kairos-philosophy skill) — read it before
any trade exit; do not work from memory of it. Execute each tranche via
`place_bet.py sell` after checking order-book depth (limit-sell thin books,
trickle large exits).

## Pitfalls

- **Never write reconciliation/price-check scripts from scratch.** The
  `scripts/` directory in this skill has working, battle-tested versions that
  handle Windows paths, RSA signing, and Kalshi schemas correctly. Copy them to
  `/tmp/` and run them. Inline scripts invite path bugs (`/c/Users/…` in Python
  on Windows) and auth drift.
- **The `kairos_*` tools are ALL dead on this host.** They're Polymarket
  bindings. Use the `scripts/` in this skill instead.
- **Never report a price move from memory.** Always fetch the current price
  from Kalshi (`GET /markets/{ticker}`) before claiming a position has moved.
  Sessions expire and memory can be stale — a false move alert erodes operator
  trust. If you can't fetch the price (API error, rate limit, missing ticker),
  say so explicitly rather than assuming a move occurred.
- **Openssl + MSYS paths**: the `kalshi_auth.py` helper resolves the key file
  relative to itself via `os.path.dirname(__file__)`. Import it from
 
  `C:\Users\gsche\.hermes\kalshi` and let it find `kalshi_key.pem` in that
  same directory. Do not copy the key — openssl chokes on MSYS `/c/…` paths.
- **Bet journal may be empty**: positions placed before the logging hook was
  installed won't appear. Fall back to `GET /portfolio/positions` for ticker
  matching.
- **Kalshi `updated_time` can be stale**: markets may show `updated_time` days
  old while prices haven't changed — the `yes_ask_dollars` and
  `last_price_dollars` are still live. Trust the price fields, not the timestamp.

## Scripts

- `scripts/reconcile.py` — pull balance + positions + settlements in one shot.
- `scripts/price_check.py` — fetch current ask/bid/last for a list of tickers.
