# Market Finding — Reference

## Platform: Kalshi (US-Regulated, ACTIVE)

This agent trades on **Kalshi** via the public/RSA-signed REST API. The legacy
Hermes `kairos_*` plugin tools were built for Polymarket and are **NON-FUNCTIONAL
on this Kalshi host** — they require `POLYMARKET_PRIVATE_KEY` (absent) and error
out. Use the Kalshi-native REST methods below. Full API reference in
`references/kalshi-api.md`.

### Discovering Markets (Kalshi-native)
To find markets / list matches, query the public events endpoint (no auth):
```
GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true
```
Swap `series_ticker` for any of the 52 live WC series (KXWCGROUPQUAL, KXWCROUND, etc.).
This is the source of truth for which markets exist. A 404 on a hand-built ticker
means the string is malformed, not that the market is absent — list the series instead.

### If Discovery Returns Empty or Thin
1. Ask the user what match and market type they see in the Kalshi app
2. Ask the user for the current YES price from the app
3. Use manual price + Elo model to compute edge
4. Re-run series discovery at the start of each new session — don't assume persistent failure

### Reading a Discovered Market
The events response (with `with_nested_markets=true`) returns, per market:
- event_ticker, market ticker, title
- yes_bid_dollars / yes_ask_dollars / last_price_dollars
- volume_24h_fp / open_interest_fp, close_time, status

For a single market, `GET .../markets/{ticker}`; for depth, `GET .../markets/{ticker}/orderbook`.
(`kairos_find_markets`, `kairos_get_market_price`, `kairos_check_velocity`, `kairos_evaluate_bet`
are NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; use the Kalshi API instead.)

## Platform Notes (Kalshi)

Kalshi has verified World Cup 2026 markets. Full API reference in `references/kalshi-api.md`.

**Key facts:**
- RSA-PSS signature auth on portfolio/order endpoints (market data is public, no auth)
- REST API base: `https://api.elections.kalshi.com/trade-api/v2`
  (DO NOT use `external-api.kalshi.com` — it 401s "API has been moved")
- No pre-built Hermes tools — build raw signed REST calls (see `references/kalshi-api.md`)
- RSA key persists at the skills-dir path (see `references/auth-persistence.md`)

## Chain of Steps for a Full Bet Sequence (Kalshi)

The legacy `kairos_*` plugin tools below are NON-FUNCTIONAL on this Kalshi host
(Polymarket plugin, require `POLYMARKET_PRIVATE_KEY`). Use the Kalshi-native step
in each row instead.

| Step | Dead Polymarket tool | Kalshi-native method |
|------|----------------------|----------------------|
| Bankroll | `kairos_get_bankroll` | RSA-signed `GET /trade-api/v2/portfolio/balance` |
| Find markets / list matches | `kairos_find_markets` / `kairos_list_matches` | public `GET /events?series_ticker=KXWCGAME&with_nested_markets=true` (or user-reported price) |
| Fair value (Elo) | — | Elo model (`references/fair-value-model.md`); the data-source-based `kairos_fair_value` may still work — test it |
| Signals / lineup / injuries | — | `delegate_task` / `x_search` |
| Live match state | `kairos_get_match_state` | ESPN scoreboard fetch (data-source based) |
| Velocity (trajectory bets) | `kairos_check_velocity` | derive from successive `GET .../markets/{ticker}` snapshots |
| Evaluate / size a bet | `kairos_evaluate_bet` | half-Kelly math in the kairos skill, then signed `POST /trade-api/v2/portfolio/events/orders` |

**Note:** The entire Kalshi path bypasses the Polymarket `kairos_*` tools. Only
the data-source-based helpers (Elo fair-value, ESPN match state) might be reusable
since they're not platform-specific — test each before relying on it.
