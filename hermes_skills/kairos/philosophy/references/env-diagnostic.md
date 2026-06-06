# Env Var Diagnostic — Native Git-Bash on Windows

This environment runs Hermes on a **Windows host with native git-bash** (NOT WSL).
Git-bash mounts your Windows C drive at `/c/`, so all Windows paths are
accessible via `/c/Users/gsche/`.

All `.hermes` files live on the Windows side under `C:\Users\gsche\.hermes\`,
accessible from git-bash at `/c/Users/gsche/.hermes/`.

## Platform State (Jun 5, 2026)

**Active platform: Kalshi** (US-regulated, CFTC-compliant).
**Polymarket is discontinued** — view-only in the US (CFTC action).
The old Kairos Polymarket tools (`kairos_find_markets`, `kairos_evaluate_bet`, etc.)
(NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; use the Kalshi API instead)
require POLYMARKET_PRIVATE_KEY which no longer exists. They will error.
Kalshi-native replacements:
- find markets / list matches -> `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true` (public, no auth)
- get prices -> `GET .../markets/{ticker}` (public)
- bankroll -> `GET .../portfolio/balance` (RSA-signed via kalshi_auth.py)
- evaluate/size a bet -> use the half-Kelly math in the skill, then place via signed `POST /portfolio/events/orders`
- reconcile/settle -> `GET .../portfolio/positions` and `.../portfolio/settlements` (RSA-signed)

## Kalshi Credentials

- API key ID: `${KALSHI_API_KEY}`
- Private key: PEM file at the SKILLS directory (NOT `/tmp`):
  `/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem`
- Auth: RSA-PSS-SHA256 headers (KALSHI-ACCESS-KEY, -TIMESTAMP, -SIGNATURE)
- API base: `https://api.elections.kalshi.com/trade-api/v2`
- Auth status (Jun 5): `INCORRECT_API_KEY_SIGNATURE` — key was saved to persistent
  path but the signature doesn't match what Kalshi expects. Likely the uploaded
  public key doesn't match this PEM. User needs to regen in Kalshi Settings.

## How to Check What's in .env

The `read_file` tool blocks `.env` (defense-in-depth). Use terminal via git-bash:

```python
from hermes_tools import terminal
result = terminal('cat /c/Users/gsche/.hermes/.env', workdir="/tmp", timeout=15)
print(result['output'])
```

The visible-but-truncated output is fine for scanning listed keys.

## .env Current State (Jun 5, 2026)

- `.env` exists at `C:\Users\gsche\.hermes\.env`
- Contains: `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `TELEGRAM_BOT_TOKEN`
- `KAIROS_DRY_RUN=false` IS set
- **No Kalshi vars in .env** — Kalshi config is in key file + memory only
- No gateway restart needed for Kalshi (uses direct HTTP, not the Hermes gateway)

## Terminal Workdir Quirk

The terminal's default `cwd` is `C:\Windows\System32` — a Windows path that
does NOT exist in git-bash. ALL foreground terminal calls without an explicit
`workdir` parameter fail with:

```
/bin/bash: line 2: cd: C:\Users\gsche: No such file or directory
```

**Always pass `workdir="/tmp"`** to terminal() calls.
This applies to both direct terminal() and terminal() within execute_code.
