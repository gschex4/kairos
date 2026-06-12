# Kairos Hermes Plugin

Wraps Kairos's market discovery, fair-value model, bet placement,
settlement, and sports feed as LLM-callable Hermes tools.

## Install

```bash
# Symlink this directory into Hermes' plugins folder, then enable.
ln -s ~/dev/kairos/hermes_plugin ~/.hermes/plugins/kairos
hermes plugins enable kairos
hermes plugins list   # verify "kairos" is enabled
```

You can also list it explicitly in `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - kairos
```

## Tools

| Tool | Purpose |
|---|---|
| `kairos_find_markets` | Discover open World Cup markets (Gamma API) — questions, ids, prices, liquidity. Call first to find what to bet on. |
| `kairos_fair_value` | The slow engine: model win/draw/over/BTTS probabilities from Elo via Dixon-Coles Poisson. Feed the output into `estimated_probability`. |
| `kairos_get_market_price` | Best bid/ask for a market. |
| `kairos_check_velocity` | Diagnostic: is this market currently in a reprice window? |
| `kairos_evaluate_bet` | Submit a bet. Runs all hard rails, sizes via half-Kelly + tier ceiling + milestone floor, places on Kalshi in live mode or logs in DRY_RUN. |
| `kairos_get_bankroll` | Current USD bankroll, % remaining, active confidence floor. |
| `kairos_list_matches` | World Cup matches in a date range (ESPN). |
| `kairos_get_match_state` | Live score, clock, status, last event for one match (ESPN). |
| `kairos_reconcile_positions` | Settle resolved positions, then return the performance summary (P&L, win rate, CLV). |
| `kairos_performance` | Running performance summary without re-checking resolutions. |
| `kairos_vet_signal` | Screen raw X / web content for prompt-injection before reasoning over it. |

## Architecture

```
~/.hermes/plugins/kairos    →    ~/dev/kairos/hermes_plugin   (symlink)
                                  ├── plugin.yaml             manifest
                                  ├── __init__.py             register(ctx)
                                  ├── schemas.py              JSON Schemas
                                  └── tools.py                handlers (thin shim)
                                                              ↓ imports
                                  ~/dev/kairos/src/           real logic
                                  ├── kalshi_tool.py          bet placement + rails (Kalshi)
                                  ├── gamma_client.py         market discovery (Gamma API)
                                  ├── fair_value.py           Dixon-Coles Poisson engine
                                  ├── sizing.py
                                  ├── market_velocity.py
                                  ├── settlement.py           P&L + CLV
                                  └── sports_feed.py          ESPN feed
```

Plugin handlers always return JSON strings and never raise. Failures
become `{"error": "..."}` responses so the agent can self-correct.

## Required env

Set in the project `.env` (or your shell):

- `KALSHI_API_KEY` — Kalshi API key id (live mode only)
- `KALSHI_KEY_PATH` — path to the RSA private key (`.pem`) that signs orders

Optional:

- `KAIROS_DRY_RUN=true` — paper trade (default)
- `KAIROS_STARTING_BANKROLL_USD=50`
- `KAIROS_FOOTBALL_DATA_KEY=...` — sports feed backup oracle

Full install flow: see `~/dev/kairos/docs/HERMES_WIRING.md`.
