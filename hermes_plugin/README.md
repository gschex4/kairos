# Kairos Hermes Plugin

Wraps Kairos's bet placement + sports feed as LLM-callable Hermes tools.

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
| `kairos_evaluate_bet` | Submit a bet. Runs all hard rails, sizes via half-Kelly + tier ceiling + milestone floor, places in live mode or logs in DRY_RUN. |
| `kairos_get_bankroll` | Current USD bankroll, % remaining, active confidence floor. |
| `kairos_get_market_price` | Best bid/ask for a Polymarket token. |
| `kairos_check_velocity` | Diagnostic: is this market currently in a reprice window? |
| `kairos_list_matches` | World Cup matches in a date range (ESPN). |
| `kairos_get_match_state` | Live score, clock, status, last event for one match. |

## Architecture

```
~/.hermes/plugins/kairos    →    ~/dev/kairos/hermes_plugin   (symlink)
                                  ├── plugin.yaml             manifest
                                  ├── __init__.py             register(ctx)
                                  ├── schemas.py              JSON Schemas
                                  └── tools.py                handlers (thin shim)
                                                              ↓ imports
                                  ~/dev/kairos/src/           real logic
                                  ├── polymarket_tool.py
                                  ├── sizing.py
                                  ├── market_velocity.py
                                  └── sports_feed.py
```

Plugin handlers always return JSON strings and never raise. Failures
become `{"error": "..."}` responses so the agent can self-correct.

## Required env

Set in `~/.hermes/.env` (or your shell):

- `POLYMARKET_PRIVATE_KEY` — wallet private key (live mode only)
- `POLYMARKET_FUNDER_ADDRESS` — wallet public address

Optional:

- `KAIROS_DRY_RUN=true` — paper trade (default)
- `KAIROS_STARTING_BANKROLL_USD=50`
- `KAIROS_FOOTBALL_DATA_KEY=...` — sports feed backup oracle

Full install flow: see `~/dev/kairos/docs/HERMES_WIRING.md`.
