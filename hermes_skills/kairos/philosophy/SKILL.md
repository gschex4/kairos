---
name: kairos-philosophy
title: Kairos Betting Agent — Philosophy, Platform Reference & Operation
description: > 
  Complete reference for the Kairos betting agent — philosophy, platform
  integration (Kalshi), Elo extraction, tool chains, cron operation,
  and communication routing.
domain: betting, kalshi, reference
---

# ⚠️ CRITICAL: Terminal Workdir on Windows Native Git-Bash

The Hermes host is Windows (C:\\Users\\gsche) running **native git-bash (MSYS2)**.
Git-bash mounts your Windows C drive at `/c/` — so `C:\Users\gsche\.hermes`
is accessible at `/c/Users/gsche/.hermes/` from within git-bash.
The terminal's default `cwd` is `C:\Windows\System32` — a Windows path that
does NOT exist in git-bash's filesystem namespace.
- Every terminal call WITHOUT an explicit `workdir=` parameter will fail with:

```
/bin/bash: line 2: cd: C:\\Users\\gsche: No such file or directory
```

**ALWAYS pass `workdir="/tmp"` to terminal calls.**

This applies to:
- Direct `terminal()` tool calls
- `terminal()` calls inside `execute_code()` blocks

**The Hermes write_file and patch tools also route through the same broken shell** when writing to `/c/Users/...`. They fail identically to terminal() because they share the CWD.

### Harmless Hermes error messages (ignore)

Every `terminal()` call produces these two stderr messages on this host:
```
/bin/bash: line 5: C:/Users/gsche/.hermes/cache/terminal/hermes-snap-2392a45e9c26.sh: No such file or directory
/bin/bash: line 6: C:/Users/gsche/.hermes/cache/terminal/hermes-cwd-2392a45e9c26.txt: No such file or directory
```
They are Hermes' internal session-state snapshots trying to write to a path that
doesn't exist. **These do not affect command execution.** The exit code, stdout,
and stderr of your actual command are all reliable. The Hermes errors appear
AFTER your command's output and with a separate bash exit_code=0. Ignore them.

### Hidden dependency: git-bash /c/ mount

The git-bash environment mounts `C:\` at `/c/`. Use `/c/Users/gsche/`
to reference anything under the Windows home directory from within terminal() calls.
Example: `cat /c/Users/gsche/.hermes/config.yaml`. Do NOT use `/home/gsche/`
(doesn't exist on the Linux side). Do NOT use `C:\Users\gsche\` directly in
bash commands.

**Reliable workaround** for writing files:
- Use `skill_manage(action='patch')` — this calls patch internally through its own file I/O that does NOT route through the shell. Preferred for editing skills.
- Use `terminal()` with shell heredoc (`cat > /path/to/file << 'EOF' ...`) with `workdir="/tmp"` — works for creating arbitrary files.
- Use `execute_code()` to run Python that writes files directly (the execute_code sandbox runs in its own context).

## What Works vs What's Blocked

### Working (Kalshi, public endpoints)
- 🔹 `GET /events?series_ticker=KXWCGAME` — discover all World Cup game markets
- 🔹 `GET /events?series_ticker=KXMENWORLDCUP` — tournament winner market
- 🔹 `GET /markets/{ticker}` — live price (yes_ask, yes_bid, last_price)
- 🔹 `GET /markets/{ticker}/orderbook` — depth
- 🔹 `kairos_fair_value(elo_home, elo_away)` — Elo-based model, platform-agnostic
- 🔹 `kairos_get_match_state(event_id)` (NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; requires POLYMARKET_PRIVATE_KEY. For live state use ESPN directly or `GET .../markets/{ticker}` for current price.)
- 🔹 List matches / find markets — use `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true` (public, no auth). The `kairos_list_matches` / `kairos_find_markets` plugin tools require POLYMARKET_PRIVATE_KEY (absent) and error on this Kalshi host.
- 🔹 Elo ratings from eloratings.net via browser_console

### Working (Kalshi, authenticated endpoints — RSA signing required)
- 🔹 `GET /portfolio/balance` — account balance
- 🔹 `POST /portfolio/events/orders` — place orders
- 🔹 `GET /portfolio/settlements` — settlement history

### Legacy: Polymarket Gamma API (historical only)

The `kairos_find_markets` tool (NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; requires POLYMARKET_PRIVATE_KEY, absent) queries Polymarket's Gamma API. This was the original platform before the US CFTC action made Polymarket view-only. Kalshi is now the active platform — find markets via `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true` (public, no auth).

## Data Sources & Extraction Techniques

### Elo Ratings (eloratings.net)

Elo ratings are the **anchor** for `kairos_fair_value`. The site renders ratings in a custom table that does not use standard `<table>/<tr>/<td>` elements, so standard DOM queries fail.

**Working extraction method (browser console):**
1. Navigate to https://eloratings.net/
2. Call `browser_console` with expression that reads `document.body.innerText.substring(0, 12000)`
3. The output is a flat text dump of the full rankings table — every team's rank, name, and Elo rating in order. No parsing needed beyond scanning the lines.
4. Works without scrolling because the full table is in the DOM; the 12k char limit captures the top ~120-140 teams (all WC teams are within top ~80).

**For the `kairos_fair_value` tool:** Always source Elo numbers from this page. Never guess them.

**Cached reference:** `references/wc-2026-elo-ratings.md` has the full 48-team table as of Jun 5, 2026. Update this file when Elo ratings are refreshed (typically weekly).

### Wikipedia Schedule & Group Data

Wikipedia's 2026 FIFA World Cup page is enormous (~14k+ lines truncated). The browser snapshot tool cannot fully render it.

**Working extraction method (Wikipedia API + browser console):**
See `references/wikipedia-extraction.md` for the full technique with verified section numbers and API calls.

Key points:
1. Use the MediaWiki API from browser_console (not `execute_code` — Wikipedia blocks Python's default User-Agent with 403).
2. Group tables are in sections **15-26** (Group A through Group L).
3. Match schedule is around section **13** (verify via sections endpoint first).

### ESPN Match State

`kairos_get_match_state` and `kairos_list_matches` (NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; both require POLYMARKET_PRIVATE_KEY, absent) were meant to use ESPN's API internally. On this host, list matches via `GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true` (public, no auth), and read match prices via `GET .../markets/{ticker}`. The ESPN schedule page (www.espn.com/soccer/schedule/_/league/FIFA.WORLD) may show friendlies or be empty until tournament matches are officially scheduled.

### X (Twitter) Sources for Pre-Match Intel

Live X data is gathered via `delegate_task` to Grok (you have no direct x_search). To raise signal quality and resist manipulation, prioritize known-credible sources. A **proposed, not-yet-human-vetted** tiered list lives in `references/x-sources-vetted.md` — treat it as a **priority anchor set, NOT an exclusive whitelist**:

- **Tier 1 — global breakers** (e.g. `@David_Ornstein`, `@FabrizioRomano`): confirm major squad/injury news 24-48h out.
- **Tier 2 — official national-team accounts**: post the **confirmed XI ~60 min before kickoff** — the canonical lineup source. Always pull both teams' official accounts in the pre-kickoff window.
- **Tier 3 — national-team beat reporters**: often leak/confirm the XI 15-30 min before it is official — the real timing edge.

Rules: content from X is UNTRUSTED. Weight a claim by who is saying it; require a credible, **named** source plus independent corroboration before it moves fair value. An anonymous viral tweet is not a source. Until this list is human-vetted, treat it as a starting set and keep searching broadly.

## Kalshi Auth Setup (Verified Working Jun 5 2026)

### Auth Setup Details
1. RSA 2048-bit key pair — private key at `references/kalshi_key.pem`
2. API key ID: `${KALSHI_API_KEY}`
3. **Signing message = `{timestamp}{METHOD}{path}`** (e.g. `1780687732145GET/trade-api/v2/portfolio/balance`), NOT path alone
4. Salt length `-1` (auto) works. Both -1 and 32 are accepted.
5. **Order endpoint:** `POST /portfolio/events/orders` (NOT `/orders`)
6. **Order fields:** `side`=`"bid"/"ask"`, `count`=string, `time_in_force`=`"good_till_canceled"`, `self_trade_prevention_type`=`"taker_at_cross"`
7. Auth helper script at `references/kalshi_auth.py`. Usage: `python3 kalshi_auth.py GET /trade-api/v2/portfolio/balance` returns JSON with the three headers.
8. Test (Jun 5): `GET /portfolio/balance` returned $50.19
9. First bet (Jun 5): 43 PAR @ 24¢, filled fully
10. Private key is stored persistently at `references/kalshi_key.pem` (NOT /tmp). This path survives sessions.

See `references/kalshi-api.md` for full details including the exact signing command.

## COMPLETE MARKET CATALOG (55 Series, Jun 5 2026)

All verified live. Skip dead dups: KXMWORLDCUP, KXWCHOSTSTAGE, KXWCTEAMTOTAL.

### TOURNAMENT WINNER (KXMENWORLDCUP - 48 active)
Spain .165 (162k vol), France .162 (265k), Brazil .082 (192k), England .074, Argentina .064, Germany .054, Portugal .031, Colombia .023, Netherlands .022, Italy .020, Belgium .019, Croatia .017, Morocco .013, Mexico .010, others below .008

### GOLDEN BOOT (KXWCGOALLEADER - 33 players)
Mbappe .16 (4.4k), Kane .12 (5.3k), Messi .05 (32k), Gyokeres .04, Haaland .04, Isak .03, Vinicius Jr .03, Salah .02, Raphinha .02, Dembele .02, Yamal .01, Olise .01

### AWARDS (KXWCAWARD - 6 events, 239 mkts)
Golden Ball (57 players): Kane .13 (1.4k), Yamal .12 (2.2k), Mbappe .11 (1.5k), Vinicius Jr .09, Bellingham .08, Olise .08, Dembele .05 (2.4k), Messi .03, Raphinha .02, Rodri .02, Nico Williams .02 | Golden Glove (10): Maignan .16, Costa .11, Courtois .06, Martinez ?, Alisson ?, Verbruggen ?, Simon ?, Pickford ?, Livakovic ? | Best Young (12): Yamal .48, Guler .20, Cubarsi .15, Mainoo, Doue, Endrick, Estevao, Huijsen, Vuskovic, Dowman, Zaire-Emery, Karl, O'Reilly | Fair Play (49): Spain .65 (510 vol), France .13, Germany .08

### CONTINENT WINNER (KXWCCONTINENT)
Europe .71, South America .23, Africa .04, NA .02, Asia .01

### BEST HOST (KXWCBESTHOST)
Mexico .41, USA .37, Canada .26

### GROUP QUALIFIERS (KXWCGROUPQUAL - 12 groups A-L, 48 mkts)
Best BUY edges: Haiti (Grp C) .12 (FV .19), Curacao (E) .09 (FV .25), Iraq (I) .14 (FV .17), Panama (L) .30 (FV .43), Jordan (J) .20 (FV .29), Uzbekistan (K) .31 (FV .34), NZ (G) .33 (FV .37)
Most overpriced SELLs: USA (D) .81 (FV .38), Ghana (L) .49 (FV .15), Ivory Coast (E) .77 (FV .25), Morocco (C) .87 (FV .56)

### MATCH MARKETS - 72 group games, all 3-way lines active
Opening: MEX vs RSA (Jun 11). Format: KXWCGAME-26{MMMDD}{T1}{T2} with markets -{T1}, -{T2}, -TIE.

### PER-GAME SERIES (72 events each)
KXWCSPREAD (288), KXWCTOTAL O/U (432), KXWCBTTS (72), KXWC1H (216), KXWC1HSPREAD (144), KXWC1HTOTAL (288), KXWC1HBTTS (72), KXWCKOPENALTIES (22 across KO rounds)

### KNOCKOUT ADVANCEMENT (KXWCROUND - 4 events, 192 mkts)
RO16/QUAR/SEMI/FINAL per-team. Most liquid: SEMI (MEX .12 10k vol, USA .09 4.3k), QUAR (POR .48 4.8k, MEX .24 3.6k, USA .23 3k), R16 (AUT .28 7k, POR .69 6.7k, BIH .21 6.4k)
KXWCSTAGEOFELIM (48 events, 336 mkts) - per-team stage of elimination. Very liquid.
KXWCFURTHESTADVANCING (4 region events). KXWCREGIONKO (7 events). KXWCGROUPWINELIM (12 mkts).

### TEAM PROPS
KXWCTEAMGOALS (106), KXWCTEAMLEADGOAL (1153 - team top scorer), KXWCTEAM1STGOAL (1162 - 1st goalscorer), KXWCTOTALGOAL (91 tournament thresholds)

### PLAYER PROPS
KXWCPLAYERGOALS (1081 - will X score), KXWCSQUAD (179 selections), KXWCGOALCOMBO (154 combo). KXSOCCERPLAYMESSI + KXSOCCERPLAYCRON: both play at .99/1.0.

### GROUP STAGE SERIES
KXWCGROUPWIN (48 mkts - win group), KXWCGROUPWINNER (12 - which group wins WC, C .11), KXWCGROUPORDER (288 exact order), KXWCGROUPBOTTOM (48 bottom), KXWCGSGOALS (96 most/fewest), KXWCGROUPGOALS (24 group totals)

### OUTRIGHT SPECIALS (that exist but may have thin liquidity)
KXWC1STTIMEWIN (1 mkt .28/.29), KXWC3RDPLACE (48), KXWCBESTHOST (3), KXWCFIFATOP10 (3), KXWCNOEURSA (1 .07/.09), KXWCBESTHOST (MEX .41, USA .37, CAN .26)

**Polymarket is discontinued** — view-only in the US (CFTC action). This agent runs on **Kalshi** (CFTC-regulated, fully operational).

World Cup 2026 markets ARE live on Kalshi's REST API. The platform was fully connected Jun 5, 2026.

### Integration Status (Jun 5, 2026)

| Capability | How |
|---|---|
| Elo-based fair value | kairos_fair_value tool (data-source, not platform-bound) |
| Live match state | ESPN directly, or GET /markets/{ticker} for current price (kairos_get_match_state / kairos_list_matches are NON-FUNCTIONAL — Polymarket plugin, need POLYMARKET_PRIVATE_KEY) |
| Market discovery | GET /events?series_ticker=KXWCGAME (public) |
| Price checking | GET /markets/{ticker} (public) |
| Auth'd endpoints | RSA-PSS signature headers |
| Order placement | POST /portfolio/events/orders with RSA sig |
| Bankroll/positions | GET /portfolio/... with RSA sig |

### See also

Before June 11 there are no World Cup matches. The pipeline should:
1. Scan KXWCGAME series for new markets (none added before matches)
2. Scan KXWCROUND series for bracket simulation edge
See `references/environment-topology.md` for the full environment layout (paths, credentials, cron jobs, open positions).

## Pre-tournament Phase (Before June 11)

The `kairos-prematch-scan` cron job runs every 4 hours but will find zero World Cup matches until June 11. Expected behavior:

1. **Confirm tournament date**: First match is June 11, 2026 (KOR vs CZE, MEX vs RSA).
2. **Kalshi-native (required)**: `kairos_list_matches` (NON-FUNCTIONAL on this Kalshi host — Polymarket plugin; requires POLYMARKET_PRIVATE_KEY, absent). Use `GET /events?series_ticker=KXWCGAME&with_nested_markets=true` directly (public, no auth) to verify no match events exist.
3. **Check previous runs**: Scan `cron/output/34f8e8d4b5c2/` for the most recent output before repeating full diagnostics.
4. **Output**: [SILENT] — no matches = nothing to evaluate or bet.

**Important**: The kairos Polymarket-plugin tools (kairos_find_markets, kairos_list_matches, kairos_evaluate_bet, kairos_reconcile_positions, kairos_get_bankroll, kairos_check_velocity, kairos_get_match_state) are NON-FUNCTIONAL on this Kalshi host — they require POLYMARKET_PRIVATE_KEY in the .env file (absent), so they error out. Use the Kalshi REST API instead: find markets / list matches -> `GET /events?series_ticker=KXWCGAME&with_nested_markets=true` (public); prices -> `GET /markets/{ticker}` (public); bankroll -> `GET /portfolio/balance` (RSA-signed); evaluate/size a bet -> the half-Kelly math in this skill, then `POST /portfolio/events/orders` (RSA-signed); reconcile/settle -> `GET /portfolio/positions` and `GET /portfolio/settlements` (RSA-signed).

## ⚠️ CRITICAL: Avoid Hermes ~50KB stdout truncation on large API responses

On native git-bash, `/tmp` is **shared** across `terminal()` calls — files written via `curl -o /tmp/foo.json` in one call persist and are visible in the next call. The real constraint is Hermes' ~50KB stdout cap: large API responses dumped to stdout get truncated, which breaks any piped parser reading that stdout.

**Two working patterns:**

**Pattern A (preferred for small responses — piped, no temp files):** Pipe curl directly into python within a SINGLE terminal() call:
```bash
curl -s "https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200" | python3 -c "import sys, json; d = json.load(sys.stdin); print(f'{len(d[\"events\"])} events')"
```
This keeps the response off your final stdout entirely. Works for responses up to ~50KB (Hermes stdout cap); larger responses need Pattern B.

**Pattern B (fetch-and-parse in ONE call):** Fetch and parse in the same terminal() call using a single heredoc:
```bash
python3 << 'PYEOF'
import urllib.request, json
url = "https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200"
d = json.loads(urllib.request.urlopen(urllib.request.Request(url)).read())
# process d directly — no intermediate files
PYEOF
```
This uses Python's `urllib` to fetch directly inside the parser, so the full response stays in Python memory and never hits the ~50KB stdout cap. Use this for large responses (>50KB).

## Series-Wide Market Rediscovery Scanning Pattern

The `wc-market-rediscovery` cron job (8am/8pm daily) needs to check ~52 Kalshi series for new events. Each scan must handle potentially large responses. Verified reliable approach:

### Recommended workflow (Workaround B — single terminal() call)

```
terminal()  # workdir="/tmp"
  python3 << 'PYEOF'
  import urllib.request, json
  
  BASE = "https://api.elections.kalshi.com/trade-api/v2"
  series_list = ["KXWCGAME", "KXWCROUND", "KXWCSTAGEOFELIM", ...]
  
  for series in series_list:
      url = f"{BASE}/events?series_ticker={series}&with_nested_markets=true&limit=200"
      d = json.loads(urllib.request.urlopen(urllib.request.Request(url)).read())
      events = d.get('events', [])
      total_mkts = sum(len(e.get('markets',[])) for e in events)
      # compare against baseline, flag changes
  PYEOF
```

### Why this approach

- **Python urllib** fetches directly into memory — no temp files, no stdout truncation risk
- **Single-terminal call** keeps the full response in Python memory, avoiding the ~50KB Hermes stdout truncation on large API responses (see `references/execute-code-pattern.md`)
- **Batch parsing** is efficient — all 30+ standard series parse in ~2 seconds
- **Event status tracking** reveals when markets move from open → finalized/settled
- **Multi-series scanning** is the norm for market-rediscovery; using one terminal() call with a loop over ALL series is more efficient than per-series curl calls

### What to check per series

| Check | How |
|---|---|
| New events | Count events, compare to baseline (see MARKET CATALOG above) |
| New knockout games | Check KXWCGAME for dates after JUN27 (group stage ends) |
| Settled markets | Check `market.result` or `market.status == "settled"` |
| Volume spikes | Aggregate `volume` across all markets in series |
| Price changes | Compare `yes_ask_dollars` against stored baseline |

### Zero-volume expected pattern

In the pre-tournament period (before Jun 11), ALL series show `vol=0` across every market. This is normal — Kalshi World Cup markets have no trading activity until closer to matchday. **Do not flag zero volume as a finding.**

### Baseline reference (from this session)

Standard series scan (Jun 5, 2026):
```
KXWC1STTIMEWIN           1        1         0  {'?': 1}
KXWC3RDPLACE             1       48         0  {'?': 1}
KXWCAWARD                6      242         0  {'?': 6}
KXWCBESTHOST             1        3         0  {'?': 1}
KXWCCONTINENT            1        5         0  {'?': 1}
KXWCFURTHESTADVANCING    4       42         0  {'?': 4}
KXWCGOALCOMBO           17      154         0  {'?': 17}
KXWCGOALLEADER           1       33         0  {'?': 1}
KXWCGROUPBOTTOM         12       48         0  {'?': 12}
KXWCGROUPGOALS           2       24         0  {'?': 2}
KXWCGROUPORDER          12      288         0  {'?': 12}
KXWCGROUPWIN            12       64         0  {'?': 12}
KXWCGROUPWINELIM         1       12         0  {'?': 1}
KXWCGROUPWINNER          1       12         0  {'?': 1}
KXWCGSGOALS              2       96         0  {'?': 2}
KXWCPLAYERGOALS         47     1081         0  {'?': 47}
KXWCREGIONKO             7       54         0  {'?': 7}
KXWCSQUAD                6      306         0  {'?': 6}
KXWCTEAM1STGOAL         48     1162         0  {'?': 48}
KXWCTEAMGOALS           12      106         0  {'?': 12}
KXWCTEAMLEADGOAL        48     1153         0  {'?': 48}
KXWCTOTALGOAL           13       91         0  {'?': 13}
```

Per-game series (all 72 events, matching KXWCGAME): KXWCSPREAD, KXWCTOTAL, KXWCBTTS, KXWC1H, KXWC1HSPREAD, KXWC1HTOTAL, KXWC1HBTTS.
KXWCKOPENALTIES: 3 events, 22 mkts (R32=10, R16=8, QF=4).

### Quick pagination check

Some series may have >200 events. Check for a `cursor` field in the response:
```python
cursor = data.get('cursor', '')
if cursor:
    # need to paginate — GET /events?series_ticker=X&cursor={cursor}&limit=200
```
KXWCGAME (72 events) and all current series fit in one page.

### `.hermes` Config Location

The Hermes config lives at `C:\\Users\\gsche\\.hermes\\` on the Windows host. In git-bash terminal sessions, access it via `/c/Users/gsche/.hermes/`. Do NOT look for it at `/home/gsche/.hermes/` on the Linux side — it doesn't exist there.

### Model / Provider Switching

The default model is set in `config.yaml` at `/c/Users/gsche/.hermes/config.yaml`:

```yaml
model:
  provider: deepseek
  default: deepseek-reasoner    # change this line to switch models
```

**deepseek-chat** = v4 Fast (cheap, good for routine cron checks and data collection)
**deepseek-reasoner** = v4 Pro (stronger reasoning, use for active betting decisions and edge analysis)

Switch by editing the `default:` value with `sed`:
```bash
sed -i 's/  default: deepseek-chat/  default: deepseek-reasoner/' /c/Users/gsche/.hermes/config.yaml
```

## Cron Job Operations

### Cron with Model Override

Cron jobs can use a cheaper model than the active session. Pass `model={provider, model}` on creation:

```python
cronjob(action='create',
    name='par-position-watch',
    schedule='0 8-22 * * *',
    script='position_watch.sh',            # runs before prompt, output injected as context
    prompt='Evaluate the data and alert if notable...',
    model={'provider': 'deepseek', 'model': 'deepseek-chat'},
    deliver='telegram:World Cup (group)')
```

**Pattern:** Use deepseek-chat (Fast) for routine data-collection cron jobs. Save deepseek-reasoner (Pro) for active betting decisions.

### Script Data Pipeline

Cron scripts must live in `~/.hermes/scripts/` (bare filename, no path). The script runs each tick and its stdout is injected into the agent's prompt as context. The agent then decides whether to alert or stay silent.

**Design principle:** Scripts should output structured key=value data. The agent prompt should define clear thresholds for alerting. If nothing notable, the agent says nothing — zero group chat noise.

### ⚠️ Critical: Cron Job Path Resolution on Windows

Cron jobs on this host **must** set two fields in the jobs.json entry for the script to execute correctly. The default bare-name resolution (`script=position_watch.sh`) produces a mangled Windows path (`C:Usersgsche.hermesscriptsposition_watch.sh`) because the cron runner concatenates the script name to a broken CWD.

**Required fix for every script-based cron job:**

1. **`workdir` must be set to `"/tmp"`** — prevents the cron runner from using the broken default CWD
2. **`script` must be an absolute MSYS path** — e.g. `"/c/Users/gsche/.hermes/scripts/position_watch.sh"`

Correct Python configuration when creating a cron job via the tool:
```python
cronjob(action='create',
    name='my-position-watch',
    schedule='0 8-22 * * *',
    script='/c/Users/gsche/.hermes/scripts/my_script.sh',  # absolute MSYS path
    workdir='/tmp',  # always required
    prompt='Evaluate...',
    deliver='...')
```

To fix an existing cron job in `cron/jobs.json`:
```python
for j in data['jobs']:
    if j['name'] == 'my-cron-job':
        j['workdir'] = '/tmp'
        j['script'] = '/c/Users/gsche/.hermes/scripts/my_script.sh'
```

Both `par-position-watch` and `futures-weekly-watch` already have this fix applied (as of Jun 5, 2026). Any new script-based cron job must include both fields.

### Script stdout: structured data only

Output structured key=value data from scripts. The agent prompt defines clear thresholds for alerting. If nothing notable, the agent says nothing — zero group chat noise.

### Reliable Script Writing (Base64 Technique)

Writing bash scripts to `~/.hermes/scripts/` on this Windows/git-bash setup is fragile because heredocs containing Python string literals (single quotes, backticks, f-strings) get mangled by shell interpretation. The most reliable workaround:

1. **In `execute_code`**, base64-encode the script content:
```python
import base64
script_content = """#!/bin/bash
curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/{TICKER}"
...
"""
b64 = base64.b64encode(script_content.encode()).decode()
print(b64)  # copy the base64 string
```

2. **In `terminal()`** with workdir="/tmp", base64-decode to file:
```bash
echo '<base64>' | base64 -d > /c/Users/gsche/.hermes/scripts/myscript.sh
chmod +x /c/Users/gsche/.hermes/scripts/myscript.sh
```

This avoids all heredoc escaping issues because the content is pure base64 — no quotes, backticks, or special characters to escape.

**Pitfall: Python `r"""..."""` raw strings corrupt f-strings with double quotes.** If the script contains `python3 -c '...'` where the Python code uses f-strings with double quotes (e.g. `f"{m.get("title")}"`), the raw string `r"""..."""` preserves the `\"` escape sequences literally as backslash-double-quote in the base64 output. The decoded script then has literal `\"` in the Python code, which causes syntax errors at runtime. **Fix:** Do NOT use `r"""..."""` for the outer Python string in execute_code. Use `"""..."""` (without `r`) and test that the escaped sequences resolve correctly, OR structure the embedded Python code to avoid needing `\"` entirely: use single-quoted Python strings (`python3 -c '...'`) so double quotes inside don't need escaping at all.

### Existing Cron Jobs

| Name | Schedule | Model | Script | Purpose |
|---|---|---|---|---|---|
| `wc-market-rediscovery` | 8am/8pm daily | default (Pro) | None (prompt-only) | Scans all 55 series for new events, alerts if new knockout markets appear |
| `par-position-watch` | Every hour 8am-10pm | deepseek-chat (Fast) | `position_watch.sh` (abs MSYS path) | Monitors all 3 open positions price/volume, silent unless >3¢ move |
| `futures-weekly-watch` | Sundays 1am UTC | deepseek-chat (Fast) | `futures_watch.sh` (abs MSYS path) | Weekly snapshot of futures/props/awards. Silent unless >3¢ move. |

### Futures / Props / Awards Monitoring

These markets (tournament winner, golden boot, awards, group qualifiers) are less liquid than match lines but offer bigger edges mid-tournament when narrative overreaction hits. The `futures-weekly-watch` cron runs `futures_watch.sh` each Sunday and evaluates price changes against the baseline snapshot. Design:

- **Script:** `scripts/futures_watch.sh` — fetches live prices on all four series, outputs structured data
- **Agent prompt:** Compares current prices against stored baseline, flags any >3¢ move
- **Delivery pattern:** Silent if nothing notable — the group only hears about actionable changes
- **Entry timing:** Best entries come DURING the tournament, not before. A strong team loses one group game → their winner price crashes 40% → the path to the final is still open → edge emerges.

KXWCGAME events appear automatically as matchups lock. Discover them:

```
GET https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200
```

Returns: event_ticker, title, markets[] (each with ticker, prices, volume, status). Paginate with cursor; stop on empty.

Use the market ticker with:
- Direct HTTP GET for price (public, no auth)
- `GET /markets/{ticker}/orderbook` for depth
- RSA-signed `POST /orders` for trading

## Pre-Match Edge Scan Pipeline (Repeatable Workflow)

This is the exact pipeline used for scanning the opening-day slate. It works before any matches start and relies only on public Kalshi endpoints + the fair-value model.

### Step-by-step

0. **Three cross-checks (against Elo blind spots)** — After step 4 (run fair value) and BEFORE looking at price, run these:
  A. **Recent form** — Last 10 match results (W/D/L) for both teams via ESPN team page or Wikipedia. 2+ losses/draws in last 5 → discount FV. 5+ match unbeaten run → small bump.
  B. **Squad value delta** — Check Transfermarkt squad total value. If Elo rank vs squad-value rank is wildly mismatched (e.g., top-10 Elo but outside top-30 squad value), discount FV by 1-2¢. Elo lags behind squad composition changes.
  C. **Head-to-head** — Check H2H record (Wikipedia/ESPN). A 4+ match winless streak against the specific opponent is a discount signal regardless of Elo gap.
  
  Collect into a 2-3 line note that either confirms or adjusts the fair-value anchor. A clear contradiction (e.g. +20% Elo edge but 0 H2H wins in 10 years → pass).

1. **List upcoming matches** — Use the Kalshi KXWCGAME events API:
   ```
   curl -s "https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200"
   ```
   Parse the JSON to find events with `sub_title` containing match info. Key fields per event: `event_ticker`, `sub_title` (e.g. "USA vs PAR (Jun 12)"), and nested `markets[]` for each outcome.

2. **Extract Elo ratings** — Navigate to https://eloratings.net/, then:
   ```
   browser_console(expression="document.body.innerText.substring(0, 15000)")
   ```
   The output is a flat text table. Parse by scanning for team names — format is `Rank\nTeam\nRating` on consecutive lines. All 48 WC teams are within the top 80 rows.

3. **Run fair value model** — Call `kairos_fair_value(elo_home=N, elo_away=N)` for each match. Record `home_win`, `draw`, `away_win` probabilities.

4. **Get live Kalshi prices** — For each match market ticker (extracted from step 1), fetch current prices:
   ```
   curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/{TICKER}"
   ```
   Extract `yes_ask_dollars` and `yes_bid_dollars`. Public endpoint, no auth needed.

5. **Compute edge** — Use `execute_code` to compare fair value vs. ask price across all matches. This is the right tool because you loop over multiple matches and compute arithmetic. Edge formula:
   ```
   edge = estimated_probability - yes_ask_dollars
   ```
   Positive edge = market is undervaluing the outcome. Negative edge = overpriced.

6. **Rank by edge** — Sort findings by edge descending. Flag anything over +5% as a potential structural misprice (often caused by sentiment/home-team bias).

### Price check oneliner pattern

To extract specific fields from a Kalshi market response in one command:

```bash
curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/{TICKER}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin)['market']; \
  print(f\"{d['yes_ask_dollars']}, {d['yes_bid_dollars']}, {d['last_price_dollars']}\")"
```

### Common edge patterns found via this pipeline

| Pattern | Description | Example from scan |
|---------|-------------|-------------------|
| **Sentiment misprice** | Host nation or brand-name team priced above Elo-based fair value. The gap can exceed 20¢ — the strongest signal type for early tournament. | USA (1733 Elo) at **50¢** vs Paraguay (1832 Elo) at **24¢**. FV gives Paraguay 45.6% → edge of **+21.6¢**. USA overpriced by 23¢. Caused by casual bettors betting the home team. |
| **Narrow-favorite squeeze** | A strong favorite (Elo gap > 300) priced at 70¢ with FV of 71¢ — small edge but high confidence due to Elo disparity. | Mexico (1875) vs South Africa (1518): FV=71.0%, ask=70¢, edge=+1.0%. High confidence but low margin. Best for volume betting. |
| **Coin-flip mispricing** | Near-equal Elo teams where the market leans one side but the model sees ~34% for both sides. Small edges (1-2¢) but lower variance. | Korea Rep (1758) vs Czechia (1740): KOR FV=37.6% ask=37¢, CZE FV=34.2% ask=33¢. Thin but directional. |

### Pitfalls

- **Kalshi prices are stale between trades** — the `last_price_dollars` may be hours old. Always use `yes_ask_dollars` (the price you'd actually pay) for edge computation.
- **Liquidity check is critical** — a +20¢ edge means nothing if the `yes_ask_size_fp` is a few dollars. Filter out markets with negligible size.
- **Elo is not the whole story** — the model gives a defensible baseline but doesn't know about lineups, rest days, motivation, or weather. Adjust fair value down when the edge relies on a narrow <3¢ gap.
- **Large Kalshi API responses exceed terminal stdout limits** — Series with hundreds of markets (e.g., KXWCPLAYERGOALS at 2.4MB, KXWCTEAMLEADGOAL at 3MB) produce JSON that gets truncated by Hermes' 50KB terminal stdout cap, breaking piped `python3 -c "json.loads()"`. **Workaround:** use Python `urllib` inside a single terminal() heredoc — data stays in Python memory, no stdout truncation:
  ```bash
  python3 << 'PYEOF'
  import urllib.request, json
  url = "https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=KXWCPLAYERGOALS&with_nested_markets=true&limit=200"
  d = json.loads(urllib.request.urlopen(urllib.request.Request(url)).read())
  print(f"{len(d['events'])} events, {sum(len(e.get('markets',[])) for e in d['events'])} mkts")
  PYEOF
  ```
  Prefer the urllib heredoc over `curl -o` then a separate `python3` call — keeping fetch and parse in one terminal() call keeps the large response in Python memory and off the ~50KB stdout cap.

### See also

- `references/contest-strategy.md` — free-to-enter contest optimization vs betting
- `references/fair-value-model.md` — model details and tournament-level variants
- `references/kalshi-soccer-rules.md` — Kalshi settlement rules (90min+stoppage, no ET/pens)
- `references/pre-tournament-scanning.md` — what to scan when no matches are active
- `references/opening-day-edge-scan-2026-06-05.md` — concrete edge findings from the June 5 pre-match scan (opening-day prices, Elo data, and the Paraguay/USA +21.6% edge finding)
- `references/cross-checks-data-sources.md` — practical data-gathering playbooks for the three Elo blind-spot checks (recent form via Wikipedia API, squad values via x_search, H2H); includes known squad values, pitfalls, and adjustment rules
- `scripts/position_watch.sh` — multi-position watch script for cron (see Cron Job Operations)
- `scripts/kalshi_auth.py` — Python auth helper for RSA-PSS signing
- `scripts/futures_watch.sh` — weekly snapshot of tournament winner (KXMENWORLDCUP), golden boot (KXWCGOALLEADER), awards (KXWCAWARD), and group qualifiers (KXWCGROUPQUAL) prices. Designed for cron with silent-when-nothing pattern.

## Kalshi Order Placement (Verified)

> ⚠️ **DO NOT place orders by hand.** Bet placement is CODE-ENFORCED: call the
> `kairos_evaluate_bet` tool, which sizes the bet (half-Kelly), enforces every
> hard rail (sources, milestone floors, event/velocity kill-rails, position
> guard, net-of-cost, absolute ceiling) **and** submits the Kalshi order itself.
> Provide the intent (`token_id` = the market ticker, `side`, `price`,
> `estimated_probability`, `confidence`, `reasoning`, `sources`) and let the tool
> place it. The `POST` details below are REFERENCE ONLY — what the tool does
> internally. Hand-POSTing an order bypasses your safety rails and is forbidden
> (SOUL.md step 9).

### Endpoint

```
POST /portfolio/events/orders
```

NOT `/orders` (returns 404). Base URL: `https://api.elections.kalshi.com/trade-api/v2`

### Required Fields

| Field | Value | Notes |
|---|---|---|
| `ticker` | e.g. `KXWCGAME-26JUN12USAPAR-PAR` | Full market ticker from GET /markets |
| `side` | `"bid"` (buy YES) or `"ask"` (buy NO) | NOT `"yes"/"no"` like Polymarket |
| `count` | `"43"` (string!) | String-encoded integer, not a number |
| `price` | `"0.2400"` (string, 4 decimals) | String, 4 decimal places |
| `time_in_force` | `"good_till_canceled"` | Required |
| `self_trade_prevention_type` | `"taker_at_cross"` | Required |
| `client_order_id` | UUID v4 string | Optional but recommended for idempotent retries |

### Auth Headers

```python
headers = {
    'KALSHI-ACCESS-KEY': '${KALSHI_API_KEY}',
    'KALSHI-ACCESS-TIMESTAMP': ts,        # milliseconds, string
    'KALSHI-ACCESS-SIGNATURE': sig,       # RSA-PSS-SHA256 over {ts}{METHOD}{path}
    'Content-Type': 'application/json'
}
```

### Order Response (Success)

```json
{
  "average_fee_paid": "0.0127",
  "average_fill_price": "0.2400",
  "client_order_id": "bee9f6f2-c047-4820-b8d6-d19aa5636ca8",
  "fill_count": "43.00",
  "order_id": "85a5b21b-760c-4260-8cdf-7147a8dfdbde",
  "remaining_count": "0.00",
  "ts_ms": 1780688162337
}
```
`remaining_count: "0.00"` means fully filled. Partial fills are possible if liquidity is low.

### Price Improvement Pattern

Orders submitted at the `yes_ask` price may fill BELOW the ask if there are resting bids at better prices. Observed fills:

| Bet | Ask Price | Fill Price | Improvement |
|---|---|---|---|
| PAR 43 ct | 0.2400 | 0.2400 | None (at ask) |
| ECU 21 ct | 0.4200 | 0.4100 | -1¢ saved |
| PAN 15 ct | 0.2700 | 0.2600 | -1¢ saved |

**Recommendation:** Submit limit orders at the ask or slightly below. If there's depth in the orderbook, the fill may come back cheaper.

## Bankroll Deployment & Sizing

> The post-trade workflow — monitoring open positions, reconciliation, realized P&L, **CLV**, and cash-out criteria — now lives in the **kairos-settlement** skill. Load that skill for settle / reconcile / performance / cash-out tasks.

### Deployment Strategy

With a small bankroll (~$50), position sizing follows this priority:
1. **Biggest edge first** — deploy to the largest +edge% regardless of match date
2. **Diversify across match days** — don't put everything on one day's matches
3. **Leave powder dry** — keep ~40-50% of bankroll for new opportunities that emerge closer to kickoff

### Sizing in Practice (Jun 5 Deployment)

| Position | Edge | Bankroll % | $ Amount | Rationale |
|---|---|---|---|---|
| PAR (Jun 12) | +32% | 21% | $10.32 | Largest edge on opening slate, high vol |
| ECU (Jun 14) | +27% | 17% | $8.61 | Strong edge, decent vol, different match day |
| PAN (Jun 17) | +41% | 8% | $3.90 | Massive edge but thin market, conservative sizing |
| **Total** | | **45%** | **$22.83** | Leaves $27 for future plays |

Half-Kelly formula used: `bet% = 0.5 * (edge / (1 - price))`, capped at 25% of bankroll for high-confidence plays, lower for thin liquidity.

## Interacting with Kalshi via curl (Public Endpoints)

All Kalshi market data endpoints are public (no auth needed):

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `GET /events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200` | Find all game markets | Discover matches and their tickers |
| `GET /events?series_ticker=KXMENWORLDCUP&with_nested_markets=true` | Tournament winner market | Get prices on all 48 national teams |
| `GET /markets/{ticker}` | Single market detail + current price | Get specific yes/no ask/bid |
| `GET /markets/{ticker}/orderbook` | Liquidity depth | Check if size is real |

Base URL: `https://api.elections.kalshi.com/trade-api/v2`

Auth is only needed for: `GET /portfolio/balance`, `POST /orders`, `GET /portfolio/settlements`.

## Elo Ratings (eloratings.net) Extraction

The site renders a custom table not using standard `<table>/<tr>/<td>`. Standard DOM queries fail.

**Working method:**
1. Navigate to https://eloratings.net/
2. `browser_console` with expression: `document.body.innerText.substring(0, 12000)`
3. Output is flat text — every team's rank, name, Elo rating. All WC teams are within top ~80 entries.
4. **Never guess Elo numbers.** Always source from this page.

## Group Chat / Multi-User Patterns

Kairos does not auto-join Telegram group chats by default. To enable:
- Hermes config change needed: enable group listening + whitelist the specific chat ID
- Workaround: user relays signals from the group in DM, Kairos processes and responds back

### Communication Routing (Autonomous Operation)

Kairos operates **autonomously** — no permission needed for bets, cash-outs, or any position management. The group chat receives updates on actions taken, not requests for approval.

- **DM with Grant (Telegram DM)** = logistics, setup, ops, infrastructure, account configuration
- **"World Cup" Telegram group (Grant + Garrett)** = bet placement confirmations, position changes, cash-outs, performance summaries, edge findings that resulted in action. Only send what was DONE, not what is BEING CONSIDERED.
- Betting research, edge discovery, and monitoring happen without pinging the group — the group only hears about executed actions.

## Knowledge Management

When the user says "save this to your files" or sends reference material:
1. Save catalog data to SKILL.md, detailed docs to references/, compact facts to memory.
2. Fix any duplicates or orphan text you create. Don't leave stale assumptions.
3. Loaded skills should gain new sections for new knowledge — don't let learnings live only in memory.

### Memory Unavailability Fallback

If the `memory` tool returns `"not available"` or `"disabled in config"`, you cannot persist cross-session state. Act as follows:

- **All decision data goes into your final output.** The current session transcript captures everything — include the full chain: what matches were scanned, what tools failed/succeeded, what edges were evaluated, and the pass/act decision with reasoning. Make the output self-contained enough to stand alone if memory never comes back.
- **Note the gap explicitly.** State: `Memory unavailable — this session's findings will not persist automatically. See session transcript for full record.`
- **For cron jobs without a user present:** the output IS the record. Include enough context that a human reading the delivery (Telegram message, group chat, email) understands the full picture — match window scanned, tools status, edge evaluations, final decision — without needing to refer to prior sessions.
- **Do not skip or truncate the output because memory failed.** The response becomes the durable artifact. Write it as if it may be the only record.
- **Do not retry memory in the same session.** One failure is final for the turn. Proceed with the fallback.
