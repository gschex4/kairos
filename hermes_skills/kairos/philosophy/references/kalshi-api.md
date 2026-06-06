# Kalshi API Reference (Verified Jun 5, 2026)

## Base URL

```
https://api.elections.kalshi.com/trade-api/v2
```

**DO NOT** use `external-api.kalshi.com` — that host returns 401 "API has been moved."
Despite the "elections" subdomain, this serves ALL Kalshi markets (elections, sports, etc.).

### Also Supported
- `https://external-api.kalshi.com/trade-api/v2` — legacy, may redirect
- `https://external-api.demo.kalshi.co/trade-api/v2` — demo environment
- `https://demo-api.kalshi.co/trade-api/v2` — demo (also supported)

## Ticker Hierarchy (CRITICAL)

```
{SERIES}{EVENT}-{MARKET}
```

| Component | Series | Event | Market | Example |
|---|---|---|---|---|
| Match winner | KXWCGAME | -26{MMMDD}{T1}{T2} | -{T1}, -{T2}, -TIE | KXWCGAME-26JUN11MEXRSA-MEX |
| Group qualifier | KXWCGROUPQUAL | -26{A..L} | -{TEAM} | KXWCGROUPQUAL-26A-MEX |
| Reach round | KXWCROUND | -26{RO16/QUAR/SEMI/FINAL} | -{TEAM} | KXWCROUND-26SEMI-USA |
| Furthest stage | KXWCSTAGE | (varies) | -{TEAM} | (per-team stage dist) |

### Match Market Detail

Each KXWCGAME event has EXACTLY 3 mutually-exclusive markets:
- `{TEAM1}` — team listed first in the event ticker wins
- `{TEAM2}` — team listed second wins
- `TIE` — draw after 90+extra time (if applicable)

Example event: `KXWCGAME-26JUN25TURUSA` ("Turkiye vs USA")
- Market: `KXWCGAME-26JUN25TURUSA-TUR` (Turkiye wins)
- Market: `KXWCGAME-26JUN25TURUSA-USA` (USA wins)
- Market: `KXWCGAME-26JUN25TURUSA-TIE` (draw)

### Knockout Game Tickers: DO NOT PRECOMPUTE

Knockout match events appear ONLY after the feeding matches resolve and the pairing is known. The ticker `KXWCGAME-26{MMMDD}{T1}{T2}` requires both 3-letter FIFA codes. Guessing a knockout ticker WILL 404 — this is design, not a bug.

**Correct pattern:** re-run series discovery on a schedule via `GET /events?series_ticker=KXWCGAME...`. New knockout game events appear automatically as pairings lock in. Re-list after every matchday.

## Market Data (PUBLIC — no auth needed)

### Discover Markets by Series (RECOMMENDED)

```
GET /events?series_ticker=KXWCGAME&with_nested_markets=true&limit=200
GET /events?series_ticker=KXWCGROUPQUAL&with_nested_markets=true&limit=200
GET /events?series_ticker=KXWCROUND&with_nested_markets=true&limit=200
```

Pagination: response has a top-level `"cursor"` string. Pass it as `&cursor=...` on the next request. Stop when `"cursor"` is empty (`""`).

Alternative (flat, no nesting):
```
GET /markets?series_ticker=KXWCGAME&limit=1000
```

### Get Single Market

```
GET /markets/{ticker}
```

Returns 200 with full market data (prices, volume, status, etc.).

### Get Orderbook

```
GET /markets/{ticker}/orderbook
```

For depth/resting liquidity — use this when `yes_bid_dollars` is null (thin markets).

### Market Response Shape

```json
{
  "ticker": "KXWCGAME-26JUN25TURUSA-USA",
  "event_ticker": "KXWCGAME-26JUN25TURUSA",
  "title": "Turkiye vs USA Winner?",
  "yes_sub_title": "Yes",
  "no_sub_title": "No",
  "yes_bid_dollars": "0.3700",
  "yes_ask_dollars": "0.3800",
  "no_bid_dollars": "0.6200",
  "no_ask_dollars": "0.6300",
  "last_price_dollars": "0.3900",
  "volume_24h_fp": "621.27",
  "open_interest_fp": "500.00",
  "close_time": "2026-06-25T21:00:00Z",
  "status": "active"
}
```

**Handle nulls:** Many individual game lines have null `yes_bid_dollars` / `yes_ask_dollars` / `last_price_dollars` / `volume_24h_fp`. Treat null bid/ask as "no liquidity → skip or flag." Group and advancement markets are more liquid.

### Timezones
All timestamps are in **ISO 8601 UTC**.

## Auth (for Trading / Portfolio Endpoints)

### Headers

| Header | Value |
|---|---|
| `KALSHI-ACCESS-KEY` | API key UUID (`${KALSHI_API_KEY}`) |
| `KALSHI-ACCESS-TIMESTAMP` | Current Unix time in milliseconds (e.g. `1780688162337`) |
| `KALSHI-ACCESS-SIGNATURE` | RSA-PSS-SHA256 signature of message = `{timestamp}{METHOD}{path}` (no query params) |

### Signing Algorithm (VERIFIED Jun 5 2026)

**The signed message is NOT just the path.** It is `{timestamp}{METHOD}{path}` concatenated.

✅ Correct: sign `"1780687732145GET/trade-api/v2/portfolio/balance"`
❌ Wrong: sign `"/trade-api/v2/portfolio/balance"` alone

**Salt length:** Both `-1` (auto) and `32` work. `-1` is simpler. Use whichever leads to clean signing.

#### Verified Working: Python3 via bash heredoc

This is the most reliable approach on this Windows/git-bash Hermes setup.
Use a `python3 << 'PYEOF'` heredoc inside a terminal() call with workdir="/tmp":

```python
import subprocess, base64, time, urllib.request, json

ts = str(int(time.time() * 1000))
method = "GET"
path = "/trade-api/v2/portfolio/balance"
message = f"{ts}{method}{path}".encode()

key_file = '/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem'

proc = subprocess.run(
    ['openssl', 'dgst', '-sha256',
     '-sigopt', 'rsa_padding_mode:pss',
     '-sigopt', 'rsa_pss_saltlen:-1',
     '-sign', key_file],
    input=message, capture_output=True
)
sig = base64.b64encode(proc.stdout).decode()

req = urllib.request.Request(
    'https://api.elections.kalshi.com/trade-api/v2/portfolio/balance',
    headers={
        'KALSHI-ACCESS-KEY': '${KALSHI_API_KEY}',
        'KALSHI-ACCESS-TIMESTAMP': ts,
        'KALSHI-ACCESS-SIGNATURE': sig
    }
)
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
```

### Auth Helper Script

A reusable Python helper lives at `references/kalshi_auth.py`. Usage:
```bash
python3 references/kalshi_auth.py GET /trade-api/v2/portfolio/balance
```
Returns JSON with the three auth headers. Co-located with the skill so it
survives sessions.

### Key File Path (PERSISTENT)

Store at:
```
/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem
```
This is on the Windows host filesystem and survives sessions. Do NOT use `/tmp`.

## Trading Endpoints (Need Auth)

### Place Order (VERIFIED Jun 5 2026)
```json
POST /portfolio/events/orders
{
  "ticker": "KXWCGAME-26JUN12USAPAR-PAR",
  "side": "bid",
  "count": "43",
  "price": "0.2400",
  "time_in_force": "good_till_canceled",
  "self_trade_prevention_type": "taker_at_cross",
  "client_order_id": "bee9f6f2-c047-4820-b8d6-d19aa5636ca8"
}
```

**Required fields:**
- `side`: `"bid"` (buy YES) or `"ask"` (sell YES)
- `count`: MUST be a string (e.g. `"43"`), NOT integer
- `price`: string in dollars (e.g. `"0.2400"`)
- `time_in_force`: `"good_till_canceled"`
- `self_trade_prevention_type`: `"taker_at_cross"`
- `client_order_id`: recommended — use `str(uuid.uuid4())` for dedup

**Endpoint:** `POST /portfolio/events/orders` (NOT `/orders`)

Expected success (201):
```json
{
  "average_fee_paid": "0.0127",
  "average_fill_price": "0.2400",
  "fill_count": "43.00",
  "order_id": "85a5b21b-760c-4260-8cdf-7147a8dfdbde",
  "remaining_count": "0.00",
  "ts_ms": 1780688162337
}
```
`remaining_count: "0.00"` = fully filled. Non-zero = partial fill, order resting.

### Cancel Orders
```
DELETE /portfolio/events/orders/{order_id}
```

### Portfolio
| Endpoint | Description |
|---|---|
| `GET /portfolio/balance` | Account balance (cash, available, locked) |
| `GET /portfolio/positions` | Open positions |
| `GET /portfolio/settlements` | Settlement history |

### Orders
| Endpoint | Description |
|---|---|
| `GET /portfolio/orders` | List orders (NOT `/portfolio/events/orders` — that 404s) |
| `DELETE /portfolio/events/orders/{order_id}` | Cancel an order |

### Reconciliation — Check Resolved Markets & P&L (Kalshi API)

The Polymarket-based `kairos_reconcile_positions` and `kairos_performance` tools require `POLYMARKET_PRIVATE_KEY` — not configured (we use Kalshi). Use a single Python heredoc to reconcile via the Kalshi REST API directly:

```python
import subprocess, base64, time, urllib.request, json

key_file = '/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem'
api_key = '${KALSHI_API_KEY}'
BASE = 'https://api.elections.kalshi.com'   # DO NOT append /trade-api/v2 here

def sign_and_call(method, path):
    """path = full path starting with /trade-api/v2/..."""
    ts = str(int(time.time() * 1000))  # fresh timestamp per call!
    msg = f"{ts}{method}{path}".encode()
    proc = subprocess.run(
        ['openssl', 'dgst', '-sha256',
         '-sigopt', 'rsa_padding_mode:pss',
         '-sigopt', 'rsa_pss_saltlen:-1',
         '-sign', key_file],
        input=msg, capture_output=True
    )
    sig = base64.b64encode(proc.stdout).decode()
    req = urllib.request.Request(
        f'{BASE}{path}',
        headers={
            'KALSHI-ACCESS-KEY': api_key,
            'KALSHI-ACCESS-TIMESTAMP': ts,
            'KALSHI-ACCESS-SIGNATURE': sig
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

# All three in one call — each gets a fresh ts
bal = sign_and_call('GET', '/trade-api/v2/portfolio/balance')
pos = sign_and_call('GET', '/trade-api/v2/portfolio/positions')
sett = sign_and_call('GET', '/trade-api/v2/portfolio/settlements')
```

**URL construction pitfall:** The signed message is `{ts}GET/trade-api/v2/portfolio/balance`, but the URL must be `BASE + '/trade-api/v2/portfolio/balance'` where `BASE = 'https://api.elections.kalshi.com'`. If you set `BASE = 'https://api.elections.kalshi.com/trade-api/v2'`, concatenating with `path` doubles the prefix → 404.

**Key reconciliation patterns:**
- `ts` must be fresh per call — reusing one `ts` across multiple endpoints causes 401 on all but the first
- `kairos_*` tools are Polymarket-only. For Kalshi, always use direct REST calls
- Pre-matchday (before Jun 11): expect all positions open, P&L=0
- Post-matchday: run reconciliation to capture settled markets and compute real-time P&L
- `realized_pnl_dollars` in the positions response tracks settled P&L per event
- The settlements endpoint shows resolved market history with `revenue` and `value` fields (revenue appears to be in cents: e.g., `revenue=500` for a $5.00 win on 5 contracts)

## Complete Active Series (Jun 5, 2026) — 55 Series, 928 Events, ~7,555 Markets

All verified live. Skip these 3: KXMWORLDCUP (dead dup of KXMENWORLDCUP), KXWCHOSTSTAGE, KXWCTEAMTOTAL.

### Tournament Winner & Outright Specials
| Series | Title | Events | Active Mkts | Notes |
|---|---|---|---|---|
| KXMENWORLDCUP | Men's World Cup winner | 1 | 48 | Top liquid: ES .165, FR .162, BR .082, ENG .074, AR .064 |
| KXWC1STTIMEWIN | First time winner | 1 | 1 | Y .28/.29 |
| KXWC3RDPLACE | 3rd place finisher | 1 | 48 | Per-team market |
| KXWCBESTHOST | Best performing host | 1 | 3 | MEX .41, USA .37, CAN .26 |
| KXWCCONTINENT | Winning continent | 1 | 5 | EU .71, SA .23, AF .04, NA .02, AS .01 |
| KXWCFIFATOP10 | FIFA top 10 queries | 3 | 3 | Thin |
| KXWCNOEURSA | Non-EU/SA winner | 1 | 1 | Y .07/.09 |
| KXWCAWARD | Tournament awards | 6 | 239 | See Awards section below |

### Knockout & Stage Advancement
| Series | Title | Events | Active Mkts |
|---|---|---|---|
| KXWCROUND | Reach round (RO16/QUAR/SEMI/FINAL) | 4 | 192 |
| KXWCSTAGE | Furthest stage advanced | 5 | 35 |
| KXWCSTAGEOFELIM | Stage of elimination (per team) | 48 | 336 |
| KXWCFURTHESTADVANCING | Furthest advancing from region | 4 | 42 |
| KXWCHOSTKO | All hosts reach KO | 1 | 1 |
| KXWCREGIONKO | Region teams reach KO | 7 | 54 |
| KXWCGROUPWINELIM | Group winners eliminated in RO32 | 1 | 12 |

### Group Stage
| Series | Events | Mkts |
|---|---|---|
| KXWCGROUPQUAL (qualify) | 12 | 48 |
| KXWCGROUPWIN (win group) | 12 | 48 |
| KXWCGROUPWINNER (which group wins WC) | 1 | 12 |
| KXWCWINGROUP (type wins group) | 5 | 5 |
| KXWCGROUPORDER (exact order) | 12 | 288 |
| KXWCGROUPBOTTOM (finish bottom) | 12 | 48 |
| KXWCGSGOALS (most/fewest) | 2 | 96 |
| KXWCGROUPGOALS (group totals) | 2 | 24 |

### Match Markets (72 per-game events each)
KXWCGAME (216 mkts), KXWCSPREAD (288), KXWCTOTAL (432), KXWCBTTS (72), KXWC1H (216), KXWC1HSPREAD (144), KXWC1HTOTAL (288), KXWC1HBTTS (72), KXWCLOCATION (2), KXWCWINNERTRAIL (1), KXWCKOPENALTIES (22)

### Team Props
KXWCTEAMGOALS (106), KXWCTEAMLEADGOAL (1153), KXWCTEAM1STGOAL (1162), KXWCEVERYTEAMGOAL (1), KXWCGOALEVERYGAME (2), KXWCTOTALGOAL (91), KXWCIRAN (1), KXWCCONGO (1)

### Player Props
KXWCPLAYERGOALS (1081), KXWCGOALLEADER (33 — Golden Boot), KXWCHATTRICK (5), KXWCSQUAD (179), KXWCGOALCOMBO (154), KXWCGOLDENBOOTCLEAT (4), KXPLAYWC (1), KXSOCCERPLAYMESSI (1), KXSOCCERPLAYCRON (1), KXWCMESSIRONALDO (3)

### Awards Detail (KXWCAWARD)
- Golden Ball (GBALL): 57 players. Top: Kane .13 (1.4k), Yamal .12 (2.2k), Mbappe .11 (1.5k)
- Silver Ball (SBALL): 57 players. Messi .30, Saka .29
- Bronze Ball (BBALL): 57 players. Kane .39, Yamal .36
- Golden Glove (GGLOVE): 10 keepers. Maignan .16, Costa .11, Courtois .06
- Best Young Player (BYP): 12. Yamal .48, Guler .20, Cubarsi .15
- Fair Play (FPA): 49 teams. Spain .65 (510 vol)

### Golden Boot (KXWCGOALLEADER — 33 players)
Mbappe .16 (4.4k), Kane .12 (5.3k), Messi .05 (32k), Gyokeres .04, Haaland .04, Isak .03, Vinicius Jr .03, Salah .02, Raphinha .02, Dembele .02, Yamal .01

### Tournament Winner Prices (KXMENWORLDCUP-26-{CODE})
ES .165, FR .162, BR .082, GB .074, AR .064, DE .054, PT .031, CO .023, NL .022, IT .020, BE .019, HR .017, MA .013, MX .010, DK .009, UY .009, JP .009, NO .008

### Group Qualifier Prices (notable BUY edges from Elo model)
Haiti (C) .12, Curacao (E) .09, Iraq (I) .14, Panama (L) .30, Jordan (J) .20, Uzbekistan (K) .31, NZ (G) .33

### KXWCROUND Prices (most liquid)
SEMI: MEX .12 (10k), USA .09 (4.3k), ENG .32 (3.1k), BRA .28 (2.9k), JPN .08 (2.1k)
QUAR: POR .48 (4.8k), JPN .20 (3.7k), MEX .24 (3.6k), USA .23 (3k), ARG .51 (2.5k)
RO16: AUT .28 (7k), POR .69 (6.7k), BIH .21 (6.4k), JPN .38 (5.8k), ARG .68 (5.5k), BRA .70 (4.2k)

### Round Series Tickers (KXWCROUND)
- `KXWCROUND-26RO16` — Will team reach Round of 16?
- `KXWCROUND-26QUAR` — Will team reach Quarterfinals?
- `KXWCROUND-26SEMI` — Will team reach Semifinals?
- `KXWCROUND-26FINAL` — Will team reach Final?

Markets = event + `-{TEAM}`, e.g. `KXWCROUND-26SEMI-USA`.

**Edge before knockout matchups lock:** Simulate bracket from Elo probabilities to get each team's reach-stage probability, compare to KXWCROUND price, compute edge. Once a specific KXWCGAME event appears for a knockout match, switch to the head-to-head line.

## Rate Limits
- Bursting returns 429
- Add a short delay between paginated calls
- For cron scanning: 1 call per minute per series is sufficient for pre-match analysis

## Team Code Map (Country → 3-letter Kalshi ticker suffix)

See `references/wc-2026-elo-ratings.md` for the full 48-team table with both Elo ratings and FIFA codes. The ticker suffix for a team is its 3-letter FIFA code (e.g. USA, MEX, ARG, ESP, FRA, etc.).

Note: **Turkiye = TUR** (not TURKEY or TKY). The FIFA code for Turkiye/Turkey is TUR.

## Special Cases
- **Turkiye vs USA** — Ticker uses `TUR` for Turkiye, `USA` for United States
- **Congo DR** — Uses `COD` (not DRC or CON)
- **Korea Republic** — Uses `KOR`
- **Bosnia and Herzegovina** — Uses `BIH`
- **Cape Verde** — Uses `CPV`
- **Curacao** — Uses `CUW`
- **Haiti** — Uses `HTI`
- **Saudi Arabia** — Uses `KSA`
- **South Africa** — Uses `RSA`
- **Kosovo** — Uses `KVX`

## Liquidity Notes (Jun 5, 2026)
- **Group qualifier markets** (KXWCGROUPQUAL): modest liquidity, some settling into favorites
- **KXWCROUND markets**: Some have decent liquidity for top teams
- **Individual game lines** (KXWCGAME): Mostly thin or null. Liquidity expected to build closer to June 11
- **Always check**: `yes_bid_dollars` and `yes_ask_dollars` before computing edge. Skip if either is null.
