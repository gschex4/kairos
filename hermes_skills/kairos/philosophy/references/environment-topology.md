# Environment Topology (June 2026)

## Host Architecture
- **Host OS**: Windows 11 (user: gsche)
- **Terminal runtime**: native git-bash (MSYS2) — runs bash, HOME=/home/gsche
- **Hermes installation**: Windows-side npm global, `C:\Users\gsche\AppData\Roaming\npm\hermes`
- **.hermes directory**: `/c/Users/gsche/.hermes/` (Windows filesystem mounted in git-bash)

## Path Quirks
- `terminal()` tool: use git-bash paths (`/c/Users/gsche/...`) and always set `workdir="/tmp"`
- `read_file`, `patch`, `search_files`, `write_file` tools: expect Windows native paths (`C:\Users\gsche\.hermes\...`)
- Cron job CWD defaults to whatever Hermes spawns — always set `workdir="/tmp"` in terminal calls

## Credentials
- **~/hermes/.env** contains: DEEPSEEK_API_KEY, XAI_API_KEY, TELEGRAM_BOT_TOKEN, GBRAIN_HOME
- **Missing**: POLYMARKET_PRIVATE_KEY (required for Polymarket plugin tools that are NON-FUNCTIONAL on this Kalshi host: kairos_list_matches, kairos_find_markets, kairos_evaluate_bet, kairos_get_bankroll, kairos_check_velocity — use the Kalshi API instead: list matches/find markets via `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true` (public), bankroll via `GET .../portfolio/balance` (RSA-signed via kalshi_auth.py), evaluate/size via the half-Kelly math then signed `POST /portfolio/events/orders`)
- **auth.json** only has: deepseek (env:DEEPSEEK_API_KEY), xai (env:XAI_API_KEY)
- **Kalshi auth**: Configured via RSA keys (referenced in kairos-gateway.cmd and config), works for Kalshi REST API

## Platforms
- **Kalshi**: Primary execution platform. RSA-authenticated. Series: KXWCGAME, KXWCGROUPQUAL, KXWCROUND, KXWCSTAGEOFELIM, KXWCMENWORLDCUP, KXWCGOALLEADER, KXWCAWARD
- **Polymarket**: Secondary. Plugin tools (kairos_*) (NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; use the Kalshi API instead) require POLYMARKET_PRIVATE_KEY. Currently non-functional.

## Cron Jobs
| ID | Name | Schedule | Platform |
|---|---|---|---|
| 34f8e8d4b5c2 | kairos-prematch-scan | 0 */4 * * * | Polymarket (blocked) + Kalshi fallback |
| b38d1395ac0f | kairos-daily-settle | 0 9 * * * | Polymarket (blocked) |
| 6a4d23030022 | wc-market-rediscovery | 0 8,20 * * * | Kalshi (works) |
| cee57bbde9aa | par-position-watch | 0 8-22 * * * | Kalshi (works) |
| 1cd25a1a8e7a | futures-weekly-watch | 0 1 * * 1 | Kalshi (works) |

## Open Kalshi Positions (as of June 5-6)
- PAR (USA vs PAR, Jun 12): 43 contracts @ 24¢
- ECU (CIV vs ECU, Jun 14): 21 contracts @ 41¢
- PAN (GHA vs PAN, Jun 17): 15 contracts @ 26¢

## Notes
- `memory()` tool is disabled in cron sandbox environments
- KAIROS_DRY_RUN=false in .env (live mode)
- Telegram channel: @Kairos_WorldCup_bot, chat_id <TELEGRAM_CHAT_ID>
- gbrain lives at `C:\Users\gsche\.kairos\.gbrain` (GBRAIN_HOME env var)
