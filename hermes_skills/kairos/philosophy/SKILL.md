---
name: kairos-philosophy
description: Complete reference for the Kairos betting agent — philosophy, platform integration (Kalshi), market monitoring, Elo extraction, tool chains, cron operation, position settlement/reconciliation/CLV, and communication routing.
category: kairos
---

# Kairos — World Cup Betting Agent (Kalshi)

## Identity
Disciplined World Cup 2026 betting agent on Kalshi (CFTC-regulated, US-legal). Edge is narrative synthesis: reconcile live X data against Elo-based fair-value estimates. Bet only when edge is stateable in one sentence with a real source.

## Platform
- **Kalshi**, not Polymarket. Public API at `api.elections.kalshi.com/trade-api/v2/`
- **Bet placement: `scripts/place_bet.py` ONLY** — the code-enforced script sizes the bet, enforces every rail, journals, and places the RSA-signed order. Never hand-roll `POST /portfolio/events/orders`. (`kairos_evaluate_bet` is a dead Polymarket plugin tool — do not attempt.)
- **Fair value: manual Poisson model** in `references/elo-to-fv-manual.md`. `kairos_fair_value` is also a Polymarket plugin — dead, do not attempt.
- **Match schedule & state**: `kairos_list_matches` and `kairos_get_match_state` are **ESPN-sourced and WORK** on this host — use them for kickoff times and live match state. Parameter names: `start_date_yyyymmdd` / `end_date_yyyymmdd` (YYYYMMDD format). These are NOT Polymarket tools.

## Market Re-Discovery Cron
Run on a schedule (e.g. daily during group stage) to detect structural changes — new knockout games appearing in KXWCGAME, markets settling in KXWCGROUPQUAL/KXWCROUND/KXWCSTAGEOFELIM, and series reconfiguration.

### Step 1 — Fetch All Seven Key Series
Scan the full FIFA WC 2026 surface. Use the paginated Python pattern from `references/kalshi-api-pagination.md` (write script via `write_file`, run via `terminal()` with full Windows path). Series:
- **KXWCGAME** — individual matches (72 group-stage events = 216 markets at baseline; knockout games appear as new events after group stage concludes)
- **KXWCGROUPQUAL** — group qualification (12 events, 48 active markets at baseline)
- **KXWCROUND** — reach round (4 events, 192 markets). These are round-based, NOT team-based: `KXWCROUND-26RO16` (\"Round of 16 Qualifiers\"), `KXWCROUND-26QUAR` (\"Quarterfinals Qualifiers\"), `KXWCROUND-26SEMI` (\"Semifinals Qualifiers\"), `KXWCROUND-26FINAL` (\"Final Qualifiers\"). Each contains 48 team markets (e.g. `KXWCROUND-26SEMI-NL` = Netherlands reaches semis). No individual team searches will match the event title — search by event_ticker prefix instead.
- **KXWCSTAGEOFELIM** — stage of elimination (48 events, 336 markets)
- **KXMENWORLDCUP** — tournament winner (1 event, 48 markets)
- **KXWCGOALLEADER** — golden boot (1 event, 33 markets)
- **KXWCAWARD** — individual awards (6 events, ~242 markets)

### Step 2 — Compare vs Known State
Baseline (Jun 5, 2026): KXWCGAME=72 events/216 mkts, KXWCGROUPQUAL=12/48 active, KXWCROUND=4/192, KXWCSTAGEOFELIM=48/336, KXMENWORLDCUP=1/48, KXWCGOALLEADER=1/33, KXWCAWARD=6/239.

### Step 3 — Flag Structural Changes
- New events in KXWCGAME (knockout games: tickers contain "R16", "QF", "SF", "FINAL" or feature cross-group matchups)
- Markets that moved from active → finalized/settled
- Series with event-count drift (>2 events difference from baseline)

### Step 4 — Output
If nothing changed: `[SILENT]`. If structural changes detected: list each change with event ticker, market counts, and settlement status. No narrative needed for structural changes — just the facts.

## Hourly Position-Watch Cron (`par-position-watch`)

Every hour 8am-10pm, checks all open match-win positions against their entry prices. Alerts if any has moved ≥15% (relative) from entry.

### Active Positions (verified Jun 13 ~00:01 UTC from portfolio API)

- **Paraguay** (USA-PAR Jun 12) — Ticker `KXWCGAME-26JUN12USAPAR-PAR`, 53 shares @ 23.8¢ blended ($12.62). Placed Jun 11 on Paraguay undervalued at +100 true home FV ~37% vs 23¢ market.
- **Morocco** (BRA-MAR Jun 13) — Ticker `KXWCGAME-26JUN13BRAMAR-MAR`, 52 shares @ 18¢ ($9.36). Placed Jun 12 on Brazil injury crisis: Neymar/Militão/Rodrygo/Estêvão/Wesley out.
- **Japan** (NED-JPN Jun 14) — Ticker `KXWCGAME-26JUN14NEDJPN-JPN`, 24 shares @ ~26¢ ($6.24). Placed by cron job (Jun 12 scan: benchmark Elo edge ~6.7¢ net vs NED).
- **Ecuador** (CIV-ECU Jun 14) — Ticker `KXWCGAME-26JUN14CIVECU-ECU`, 21 shares @ 41¢ ($8.61). ⚠️ This is Ivory Coast vs Ecuador, NOT Ecuador vs Curaçao.
- **Panama** (GHA-PAN Jun 17) — Ticker `KXWCGAME-26JUN17GHAPAN-PAN`, 15 shares @ 26¢ ($3.90)
- **France** (tournament winner) — Ticker `KXMENWORLDCUP-26-FR`, 1 share @ 16.4¢ ($0.16)
- **Argentina** (tournament winner) — Ticker `KXMENWORLDCUP-26-AR`, 3 shares @ ~8.7¢ ($0.26)
- **Ivory Coast** (tournament winner, trade) — Ticker `KXMENWORLDCUP-26-CIV`, 250 shares @ 0.4¢ ($1.00)
- **Sweden** (Group F qualification) — Ticker `KXWCGROUPQUAL-26F-SWE`, 1 share @ 64¢ ($0.64). Placed Jun 11 on injury divergence.

### Settled
- **Mexico** (MEX-RSA Jun 11) — Won 2-0, +$2.57 net P&L ✅
- **Czechia** (KOR-CZE Jun 11/12) — Lost, -$0.35 net P&L ❌
- **Bosnia and Herzegovina** (CAN-BIH Jun 12) — Settled from portfolio (no longer held).

### ⚠️ Authoritative Position Source

**Before any position-watch run, fetch the portfolio API directly.** Never rely on memory or skill docs for ticker/entry-price data — positions can be placed by cron jobs you weren't present for, and tickers can be misremembered. 

**Portfolio endpoint**: `GET /trade-api/v2/portfolio/positions` (RSA-signed). The `market_positions` array gives ticker, position_fp (shares), market_exposure_dollars, and fees. The `event_positions` array gives event-level aggregation.

**Rule**: Fetch portfolio → cross-reference against skill's position list → update skill if mismatch. Do not hardcode assumptions about which ticker a position is on.

### Fetch Pattern
```bash
curl -s 'https://api.elections.kalshi.com/trade-api/v2/markets/{TICKER}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['market']; print(d['yes_ask_dollars'], d['yes_bid_dollars'], d['last_price_dollars'])"
```
Response is nested under `market` key. Fields use `_dollars` suffix (`yes_ask_dollars` not `yes_ask`).

### Threshold
`|current - entry| / entry * 100`. Alert only if ≥15% relative move. Filters spread noise. If no position qualifies: `[SILENT]`.

**Trade positions** (KXMENWORLDCUP, KXWCGROUPQUAL, KXWCAWARD, KXWCGOALLEADER, and
any cheap contract held as a re-rate trade): alert threshold is ≥50% relative move.
Bigger moves are news on thin markets; smaller moves are noise. An **up** move ≥50%
is a possible **exit window** — check the catalyst and the exit ladder. A **drop** of
≥50% is a thesis-invalidation signal — investigate immediately.

**Exit strategy for trade positions**: see `references/trade-exit-strategy.md` —
sell into the re-rate, don't hold for the outcome.

If a position's ticker returns HTTP error/empty response (as the stale CIVECU ticker does), log the issue but do NOT alert — the position exists under the corrected ticker.

### Delivery
**bold** position names, bullet lists, no tables. One bullet per flagged position: entry price, current price, % move, direction, spread.

## Weekly Price-Monitoring Cron
Every N hours, run this sequence to track futures/props/awards markets:

### Step 1 — Fetch All Four Series in Parallel
Use terminal() (workdir=/tmp) with curl:
```
curl -s 'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=SERIES&with_nested_markets=true&limit=100'
```
Series to monitor: KXMENWORLDCUP, KXWCGOALLEADER, KXWCAWARD, KXWCGROUPQUAL

From JSON, read yes_bid_dollars, yes_ask_dollars, volume per market. Skip markets where yes_bid_dollars is null.

### Step 2 — Compare vs Baseline
Maintain a baseline dict in the cron prompt (last-known prices in cents). Compute Δ for each tracked player/team. Reference `references/kalshi-market-baselines.md` for the authoritative baseline.

### Step 3 — Flag Moves ≥ 15% from baseline
Only report when something moved ≥ 15% from its baseline price (relative, NOT flat cents — this filters Kalshi spread noise). If nothing: output exactly `[SILENT]`.

For each flagged mover, brief narrative context: why it moved (tournament narrative shift, team form, injury news, squad depth, award subjectivity).

### Research routing: web_search (Perplexity) vs x_search (Grok)
`web_search` runs on **Perplexity Sonar** (configured) — use it for CONTEXTUAL data (recent form, squad value, head-to-head, weather forecast): cited, authoritative sources (Transfermarkt/ESPN/FIFA) for ~$0.005/query. Ask **focused** questions, one cross-check per call. Use `x_search`/`delegate_task` (Grok) for LIVE X SIGNALS (confirmed lineups, breaking injuries, late team news) where X is the primary source and web lags. **One path per layer — never run both for the same question** (a second path just raises cost).

## Cron Operation
- No user present — execute fully autonomously, make reasonable decisions
- Final response auto-delivered — do NOT use send_message
- Markdown: **bold**, *italic*, `code`, ```blocks```, ## headers. No table syntax (use bullet lists)
- Pass `workdir=/tmp` to every terminal() call

## Betting Workflow (match-day)
0. **Verify the fixture exists.** Before researching or betting any Kalshi market, confirm the match actually appears in the official FIFA World Cup 2026 schedule. Query `x_search "World Cup 2026 {Team1} vs {Team2} group stage schedule"` or browser-navigate to Wikipedia/FIFA.com. Kalshi occasionally creates markets months in advance with placeholder matchups — a market existing does NOT mean the fixture is real. A bet on a phantom fixture gets voided and ties up capital.
1. Discover markets via Kalshi API
2. Get prices (public endpoint)
3. Source Elo from eloratings.net
4. Compute fair value — for **match markets**, use the manual Poisson model in `references/elo-to-fv-manual.md`. For **tournament futures** (KXMENWORLDCUP, KXWCROUND, KXWCSTAGEOFELIM, KXWCGROUPQUAL), use the relative-Elo-share method in `references/tournament-futures-fv.md`. Feed it Elo ratings from step 3. The Elo reference includes calibration points to verify your output.
5. Contextual cross-checks: recent form, squad value delta, head-to-head, weather forecast — via **`web_search`** (Perplexity; focused per-check queries; cited Transfermarkt/ESPN/FIFA, ~$0.005 each). See ## Cross-Checks. Venue/climate IDENTITY stays anchored to `references/wc2026-venue-heat.md` (substrate rule), never to Perplexity.
6. Live X signals — confirmed lineups, breaking injuries, late team news — via `delegate_task`/`x_search` (Grok); X is the primary source for these. Keep the cost discipline: ≤1-2 delegate children, ≤2 x_search calls. Do NOT re-run the step-5 contextual cross-checks here — those are `web_search` now (one path per layer).
7. Check bankroll — RSA-signed GET /portfolio/balance. **Use the inline Python pattern** (see ## Kalshi Auth — Inline Python Pattern below). The standalone `kalshi_auth.py` script path is `/c/Users/gsche/.hermes/kalshi/kalshi_auth.py` but the inline pattern is preferred (avoids subprocess path issues and stale timestamps between auth+curl).
8. Compute edge = adjusted_fair_value - yes_ask - fee, where fee = 0.07 × price × (1 - price) (Kalshi taker fee, ~1-1.75¢ at mid prices — a gross edge that fees eat is NOT an edge). If net edge < 3¢ (or < 5¢ when FV ≥ 70%), pass — thin edges on high-probability outcomes size too small to matter. See pitfall: "Thin edge on high-probability bets." **Then the conviction-FV floor (R7):** if FV < 40%, a conviction bet is FORBIDDEN regardless of edge size (the side is expected to lose — it must be a `--type trade` if ≤15¢, else a PASS); if 40% ≤ FV < 45%, require net edge ≥ 8¢ to ride to resolution.
9. **Place bet via the code-enforced script** — `python3 "C:/Users/gsche/.hermes/skills/kairos-philosophy/scripts/place_bet.py" buy --ticker T --price 0.46 --prob 0.55 --confidence 0.7 --reasoning "..." --sources "..."` (terminal, workdir=/tmp; add `--type trade --cost X` for re-rate trades, `--dry-run` to preview). The SCRIPT computes the size (confidence-scaled Kelly on TOTAL capital, net of fees), enforces the rails (sources, min net edge, confidence floor, **conviction FV floor R7: prob ≥ 0.40, 0.40–0.45 needs ≥8¢ net edge, <0.40 forbidden as conviction**, 25%-of-capital cap, $5 cash floor), journals the decision, and places the order. Never compute a share count yourself and never POST `/portfolio/events/orders` directly. A `rejected` status is final — pass. (`kairos_evaluate_bet` is a dead Polymarket plugin tool — do not attempt.)
10. Log bet details to memory (or output if memory unavailable)

## Trade-Candidate Screening (buy-cheap / sell-into-the-re-rate)

Two kinds of position exist — know which you're opening:
- **Conviction / hold-to-resolution** — you bet because the outcome happens, and
  ride to settlement. Most match-win bets. Sized by the script: confidence-scaled Kelly (above).
  **Hard FV floor (R7): conviction requires FV ≥ 0.40** (≥ 0.45 for normal edge; 0.40–0.45
  needs ≥ 8¢ net edge). A side you expect to lose is NEVER a conviction hold.
- **Trade / re-rate** — you buy a *mispriced cheap* contract because a catalyst will
  push the *price* up, and you **sell into that** before resolution. You do NOT need
  it to hit $1.00.

**The resolved tension (Paraguay):** a sub-0.40-FV side priced *above* the 15¢ trade ceiling
is neither a conviction bet (R7 forbids it) nor a trade (R4 ceiling) — it is a **structural PASS**,
and that is the system working ("a pass is a successful outcome"). A trade is defined by its
*sell-into-a-dated-catalyst EXIT*, not by relabeling a hold to dodge the floor — a "trade" with
no dated catalyst (trade-screen Q2) is a rail violation, not a loophole.

Before answering "who's a good long shot" or opening any cheap (≤15¢) position as a
trade, run the screen in `references/trade-screen.md`. It runs on **any** series, not
just tournament futures. Four questions, **3 of 4 (catalyst mandatory) = tradeable**:
1. **Cheap vs. a defensible value?** — the *price* is too low, regardless of P(win).
2. **A dated catalyst that re-rates the price UP, and when?** *(mandatory)* — result,
   draw/bracket reveal, lineup, a favorite stumbling. No catalyst → pass.
3. **Asymmetric payoff?** — bounded premium down, multiple up.
4. **Can I exit?** — book depth now or arriving with the catalyst.

**Tournament long-shots** use the five-gate checklist in `trade-screen.md` as one way
to answer Q1–Q2 (squad quality, group path, form, DNA, hedge) — it feeds the screen,
it isn't the screen.

**Sizing — trades are sized by dollars-at-risk, not Kelly.** The premium is the whole
downside. Trade bucket ≤10% of bankroll total; any single trade ≤5%.

See `references/trade-exit-strategy.md` for post-entry management — the plan is to
sell into the re-rate, not to hold for the outcome.

## Hard Rails
- **Autonomous mode: NEVER ask permission to bet.** Operation mode is FULLY AUTONOMOUS. When you have edge + sources + sizing within rails, place the bet and report what you did. Do not say "Want me to place it?", "Ready to go?", or any permission-seeking variant. The only acceptable post-research output is the bet confirmation or an explicit pass-with-reason. Asking permission when rails are green is a process failure that wastes operator attention.

**Code-enforced** (inside `scripts/place_bet.py` — a `rejected` status is final, do not route around it):
- Sourced edge required (no source = no bet)
- Minimum NET edge 3¢ (5¢ when FV ≥ 70%; **8¢ in the 0.40–0.45 borderline band**) — edge is measured after the Kalshi taker fee
- Confidence floor 0.50
- **Conviction FV floor (R7): prob ≥ 0.45 normal; 0.40–0.45 conviction only if NET edge ≥ 8¢; prob < 0.40 conviction FORBIDDEN (must be `--type trade` if ≤15¢, else PASS). Trades exempt.**
- Conviction sizing: confidence-scaled Kelly (fraction = confidence, clamped 0.50-0.75) of TOTAL capital (cash + WC exposure), capped at 25% of total capital and at cash above the $5 floor
- Trade sizing: dollars-at-risk ≤ 5% of total capital, price ≤ 15¢
- Cash floor: no buy that takes cash below $5

**Agent-enforced** (need live match context the script can't see):
- Event-window kill (no order within 60s after goal/red/VAR)
- Market velocity kill (no order if >5% move in 30s)
- **Score/event integrity: never report a goal, card, minute, or scoreline not verified THIS turn via `kairos_get_match_state` or a named source. A price move is NOT a score — a YES cratering to 2-3¢ means the market's implied probability collapsed, not that it's "3-0." Inferring a score from price is a fabrication.**
- **Venue/fact integrity: never name a stadium, host city, roof status, or temperature from memory — anchor every venue/climate claim to `references/wc2026-venue-heat.md` or a fetch this turn. SoFi = Los Angeles (mild, NOT Atlanta/"swampy heat"). Creativity is synthesis of verified facts, never invention of them.**

## Sizing
The script computes size — you never do. Conviction: `kelly_fraction * net_edge / (1 - price)` of TOTAL capital, where kelly_fraction = your stated confidence clamped to [0.50, 0.75] and net_edge subtracts the Kalshi fee; capped at 25% of total capital. Trade: your `--cost` dollars-at-risk, 5%-of-capital cap.

## Kalshi Auth — Inline Python Pattern

When `kalshi_auth.py` can't be called externally (subprocess path issues, stale timestamps between auth and curl), replicate the RSA-PSS signing inline in a Python heredoc. **Use `C:/` paths, not `/c/` paths** — Python cannot read `/c/Users/...` on this host.

```python
import base64, subprocess, time, json, urllib.request

def get_auth_headers(method, path):
    ts = str(int(time.time() * 1000))
    message = f"{ts}{method}{path}".encode()
    key_file = "C:/Users/gsche/.hermes/kalshi/kalshi_key.pem"
    proc = subprocess.run(
        ['openssl', 'dgst', '-sha256',
         '-sigopt', 'rsa_padding_mode:pss',
         '-sigopt', 'rsa_pss_saltlen:-1',
         '-sign', key_file],
        input=message, capture_output=True
    )
    signature = base64.b64encode(proc.stdout).decode()
    return {
        "KALSHI-ACCESS-KEY": "${KALSHI_API_KEY}",
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": signature
    }

# Usage: generate headers and make request in same process
headers = get_auth_headers("GET", "/trade-api/v2/portfolio/balance")
req = urllib.request.Request("https://api.elections.kalshi.com/trade-api/v2/portfolio/balance")
for k, v in headers.items():
    req.add_header(k, v)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
print(data)  # e.g. {"balance": 2607, "balance_dollars": "26.0796", ...}
```

**Key points:** (1) timestamp and signature are generated in the same process as the HTTP call — no stale timestamps. (2) API key ID `${KALSHI_API_KEY}` is hardcoded. (3) `balance_dollars` is a string, not a float. (4) `balance` is in cents (2607 = $26.07).

## Kalshi Auth — POST Order Wire Format (REFERENCE ONLY — never call directly)

⚠️ **Order placement goes through `scripts/place_bet.py`, never a hand-rolled POST.** The script implements this wire format with the rails and journaling on top. The pattern below is kept ONLY as documentation of the wire format (for debugging the script, not for placing orders): `count` and `price` MUST be strings, not numbers — the Kalshi Go backend rejects numeric JSON types with `"cannot unmarshal number into Go struct field CreateOrderV2Request.count of type string"`.

```python
import base64, subprocess, time, json, urllib.request

def get_auth_headers(method, path):
    ts = str(int(time.time() * 1000))
    message = f"{ts}{method}{path}".encode()
    key_file = "C:/Users/gsche/.hermes/kalshi/kalshi_key.pem"
    proc = subprocess.run(
        ['openssl', 'dgst', '-sha256',
         '-sigopt', 'rsa_padding_mode:pss',
         '-sigopt', 'rsa_pss_saltlen:-1',
         '-sign', key_file],
        input=message, capture_output=True
    )
    signature = base64.b64encode(proc.stdout).decode()
    return {
        "KALSHI-ACCESS-KEY": "${KALSHI_API_KEY}",
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": signature
    }

# Buy 250 shares of a YES contract at 0.4¢ limit
body = json.dumps({
    "ticker": "KXMENWORLDCUP-26-CIV",
    "count": "250",           # string, not int
    "side": "bid",            # "bid" = buy YES (open), "ask" = sell (close)
    "type": "limit",
    "price": "0.0040",        # string, not float — 0.4¢ = $0.004
    "time_in_force": "good_till_canceled",
    "self_trade_prevention_type": "taker_at_cross",
    "client_order_id": "kairos-civ-futures-1"
}).encode()

path = "/trade-api/v2/portfolio/events/orders"
headers = get_auth_headers("POST", path)
req = urllib.request.Request(
    "https://api.elections.kalshi.com" + path,
    data=body,
    headers={**headers, "Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req, timeout=10)
result = json.loads(resp.read())
# result = {"order_id": "...", "fill_count": "250.00", "average_fill_price": "0.0040", ...}
print(json.dumps(result, indent=2))
```

**Key pitfalls for orders:**
- `count` and `price` are **strings** (Kalshi Go backend constraint). Using `int`/`float` returns HTTP 400.
- `side`: `"bid"` = buy YES (open), `"ask"` = sell (close/exit). This is the opposite of Polymarket's convention.
- `client_order_id` is required for idempotency — use a unique string per bet.
- Check `liquidity_dollars` on the market before placing a large limit order — thin books mean your order may sit unfilled or walk the book if market-sold.

## Fair-Value Model

**Match FV — primary path: use `references/elo-to-fv-manual.md`.** The `kairos_fair_value` tool is a Polymarket plugin dependency and is **dead on this Kalshi host** — do not call it. Instead, compute Poisson win/draw/loss probabilities from Elo ratings manually using the calibrated model in the reference. It includes benchmark calibration points from the Jun 5 scan so you can verify your output against trusted numbers.

**Tournament futures FV: use `references/tournament-futures-fv.md`.** The Poisson model only prices individual matches. For tournament winner / reach-round / stage-of-elimination markets, use the relative-Elo-share method in that reference. It anchors fair value among the top-contender pool, applies a conservative haircut for tournament variance, and cross-checks against sportsbook consensus when available. Only bet when the edge is clear on this coarser estimate.

**Group qualification FV (KXWCGROUPQUAL): see `references/48-team-qualification-fv.md`.** The expanded 48-team format with a 3rd-place safety net (8 of 12 group 3rd-place teams advance, ~67% overall) changes the math for KXWCGROUPQUAL markets. Mid-tier teams in competitive groups have higher qualification probability than raw Elo gaps suggest because 4+ points almost guarantees advancement via either top-2 or best-3rd-place path.

## Cross-Checks (against Elo blind spots)

**Two research layers — route each to the right tool:**
- **Contextual data** (recent form, squad value, head-to-head, weather forecast): use **`web_search`** — it runs on **Perplexity Sonar**, returning cited authoritative sources (Transfermarkt, ESPN, FIFA) for ~$0.005/query. Ask **focused** questions, one cross-check per call (e.g. "Transfermarkt squad value of {Team}") — NOT one giant consolidated query (that starves it). This is the PRIMARY path; it replaces the old third-hand X-scraped data.
- **Live X signals** (confirmed lineups, breaking injuries, keeper/late team news): use **`x_search` / `delegate_task`** (xAI/Grok). Primary sources post on X first, so these stay on Grok — web lags X here. See items E/F.

**Contextual-data fallbacks** (only if `web_search` fails): Tier 2 = `browser_navigate` + `browser_console` (Wikipedia results pages, Transfermarkt); Tier 3 = `x_search` (X posts, third-hand — flag as X-sourced, lower confidence).

**Reliable browser Wikipedia pattern** (use when x_search is also unavailable):
- Navigate to `https://en.wikipedia.org/wiki/{Team}_national_football_team_results_(2020–present)` — the "(2020–present)" suffix page has year-by-year results tables.
- Use `browser_console` with: `document.body.innerText.substring(document.body.innerText.indexOf('2025[edit]'), document.body.innerText.indexOf('2025[edit]')+2500)` to extract the 2025+2026 results in one call.
- Team name format: `South_Korea`, `Czech_Republic` (not Czechia), `South_Africa` uses "soccer" not "football" in URL. Mexico = `Mexico`.
- Each result line shows: date, competition, opponent, score. Extract W/D/L from score orientation (team listed first = home team in the layout).

A. Recent form — last 5-10 matches W/D/L. Query **`web_search`** (Perplexity) focused: `"List the last 5 matches the {Team} men's national football team played in 2025-2026: date, opponent, score, result"` (fallback: x_search `"{Team} national team last 5 results 2026"`). Look for: winless streaks (discount), 5+ match winning streaks (bump), heavy losses to similar-tier opponents (red flag).
B. Squad value delta — Elo vs Transfermarkt squad value mismatch.
   1. **Preferred**: `web_search` (Perplexity) — `"What is the current total squad market value of the {Team} men's national team according to Transfermarkt?"` It cites Transfermarkt directly (verified: clean €-figures, transfermarkt.com sources, ~$0.005). Use the squad-value **delta/ranking** as the signal — the absolute can vary by Transfermarkt page version, so the relative gap is what matters.
   2. **Fallback**: `browser_navigate` to the Transfermarkt team page, or `x_search "{Team} squad total value transfermarkt 2026"` (X-sourced = third-hand, lower confidence — flag it).
   3. If all sources are down: skip squad-value rather than guessing. A two-signal bet (Elo + form + H2H) is better than one with a fabricated number.
C. Head-to-head — query **`web_search`** (Perplexity): `"All-time head-to-head record and past meetings between {Team1} and {Team2} men's national football teams"` (fallback: x_search `"{Team1} vs {Team2} head to head history football"`). 4+ match winless streak = discount signal regardless of Elo gap. Single historical match (especially >10 years old) is a WEAK signal — do not over-adjust.
D. **Climate/Heat** — cold-climate team playing hot-climate opponent in an open-air hot venue. See `references/wc2026-venue-heat.md` (stadium data) and `references/heat-analysis-workflow.md` (step-by-step). Core signal: Scandinavian/British/northern European teams in Miami/Monterrey/Guadalajara afternoon kicks against African/Middle Eastern/Latin American opponents. When this signal fires, adjust fair value up to 5-7 cents against the cold team. The 2025 Club World Cup previewed the same problem — players reported dizziness, "impossible" conditions. The current **forecast** temperature may be pulled via `web_search` (Perplexity), but the venue/city/roof IDENTITY stays anchored to the reference per the substrate rule below — Perplexity NEVER names the venue.
   **Substrate rule (mandatory):** before writing ANY venue/climate sentence, look the match's stadium up in `references/wc2026-venue-heat.md` (it lists city, June temps, roof, risk level for every host venue) and confirm the city against the official fixture. NEVER state a stadium, host city, roof status, or temperature from memory or narrative color. SoFi = **Los Angeles**, open-air MODERATE 22–28°C — NOT Atlanta, NOT "swampy heat"; the EXTREME venues are Hard Rock/Miami and Estadio BBVA/Monterrey. If the venue isn't in the table, fetch and verify this turn before asserting it; if you can't, omit the venue/heat claim rather than invent one. A heat edge built on a fabricated venue is worthless.

E. **Pre-match X intel gathering** — see `references/prematch-x-intel-pattern.md` for the delegate_task + x_search fan-out pattern. Use this for parallel research across multiple matches when web_search is down.

F. **Injury/Suspension Crisis** — when a team loses 3+ key starters (best player, spine, or captain), this can shift fair value independently of Elo. See `references/injury-adjustment.md` for the quantification method. Always query `x_search "{Team} injuries World Cup 2026 {opponent} match lineup news"` as part of the X-intel step. Key signals:
   - Best player OUT (Neymar, Davies, Salah tier) → discount 1-3¢ from that team's FV
   - 3+ starters OUT including spine (CB, CM, ST) → discount 3-5¢
   - Both teams hit → net the adjustments (bigger net = bigger edge)
   - Verify from named sources (team accounts, major journalists) — never trust a single unsourced rumor
   - Re-check near kickoff: a late scratch from the XI not on the injury report can create a last-minute edge

Example (Jun 11) — **CANONICAL ANTI-EXAMPLE, the Paraguay loss**: USA-PAR benchmark had PAR 45.6% at +35 neutral; at +100 true home, PAR FV shifted to ~37%. Market priced PAR at 23¢ — the 14¢ edge survived the adjustment, so Kairos placed a **conviction** bet. It lost. The edge was real (price was wrong) but **37% FV means Paraguay loses 63% of the time** — riding a sub-coinflip outcome to resolution was the error. Under the **R7 conviction floor (added after this loss), 37% FV is below 0.40 → conviction is FORBIDDEN**; and at 23¢ it's above the 15¢ trade ceiling, so the correct action was a **PASS**. Edge tells you the price is wrong; it does NOT tell you the side wins.

Example (Jun 13): Brazil vs Morocco — Brazil missing Neymar, Rodrygo, Militão, Estêvão, Wesley (5 absences incl. spine). Morocco FV adjusted from ~23% (Elo-only) to ~30% after injury crisis discount to Brazil. Market at 18¢ → 12¢ raw edge. See `references/injury-adjustment.md` for the full worked example.

## Settlement, Reconciliation & CLV

Everything **after** a bet is placed. Settlement is **read-only analysis**;
the only write action is a deliberate cash-out, which goes through
`scripts/place_bet.py sell --ticker T --price P --count N --reasoning "..."`,
never a raw order.

### Platform

- **Kalshi** (CFTC-regulated). Public API: `api.elections.kalshi.com/trade-api/v2/`.
- All `kairos_*` plugin tools are **DEAD** on this host (legacy Polymarket bindings).
  Do **not** call `kairos_reconcile_positions`, `kairos_performance`, `kairos_get_bankroll`,
  etc. Use the scripts in `scripts/` instead.

### Daily-Settle Sequence

#### Step 1 — Pull Data from Kalshi

**Do NOT write reconciliation or price-check scripts from scratch.** Battle-tested
scripts live in `scripts/`. Copy to `/tmp/` and run them:

```bash
cp "/c/Users/gsche/.hermes/skills/kairos-philosophy/scripts/reconcile.py" /tmp/
python3 /tmp/reconcile.py
```

It hits three endpoints with fresh RSA timestamps per call and dumps one JSON blob:

| Endpoint | What |
|---|---|
| `GET /trade-api/v2/portfolio/balance` | Cash balance, portfolio value |
| `GET /trade-api/v2/portfolio/positions` | Open positions (market-level + event-level) |
| `GET /trade-api/v2/portfolio/settlements` | Resolved markets with outcome + revenue |

#### Step 2 — Price-Check Open Positions

Filter to World Cup positions only (tickers starting with `KXWC`). Copy and
pipe tickers via stdin:

```bash
cp "/c/Users/gsche/.hermes/skills/kairos-philosophy/scripts/price_check.py" /tmp/
echo -e "KXWCGAME-26JUN12USAPAR-PAR\nKXWCGAME-26JUN14CIVECU-ECU" | python3 /tmp/price_check.py
```

#### Step 3 — Reconcile vs Bet Journal

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

#### Step 4 — Compute Realized P&L per Settlement

For each settled position:

- **BUY YES, won**: `profit = revenue_dollars − yes_total_cost_dollars`
- **BUY YES, lost**: `loss = yes_total_cost_dollars` (revenue = 0)
- If both YES and NO shares held (`yes_count_fp` > 0 AND `no_count_fp` > 0):
  total cost = `yes_total_cost + no_total_cost`; winner side pays out at $1/share.

Kalshi's `revenue` field is in **cents** (e.g., `500` = $5.00 payout on a win).

Sum realized P&L (pre-fee and post-fee) across all settlements. Report
**today's** realized P&L and **cumulative vs the $50 starting bankroll**.

#### Step 5 — Compute CLV per Position

CLV = closing price − entry price for BUY positions. Positive = good.

"Closing price" = the market's `last_price_dollars` just before kickoff.
If the match hasn't started yet, CLV is a running mark (current ask − entry).

Track average CLV and positive-CLV rate. **CLV is the leading indicator of edge**
— consistently positive CLV means the fair-value model beats the market even on
small samples.

#### Step 6 — What to Report

Deliver to the World Cup group:

1. Settled WC markets since last run + win/loss + realized P&L (today and cumulative vs $50).
2. Open WC positions: ticker, shares, entry price, current ask, Δ in cents, unrealized P&L.
3. Rejection audit (only if notable — same rail fired repeatedly).

**Silence rule**: End with `[SILENT]` when (a) nothing settled since last run,
AND (b) no open position moved ≥15% relative from entry (`|current − entry| / entry * 100`).
This filters Kalshi spread noise. Do not combine `[SILENT]` with content — either report
findings normally, or say `[SILENT]` and nothing more.

### Cash-Out Criteria

Cash-out logic depends on which **kind** of position it is (see
`references/trade-screen.md` for the distinction):

**Conviction / hold-to-resolution positions** (most match-win bets): match-day exit
only — once the match kicks off, the position rides to resolution. Pre-match exit
only on thesis invalidation (lineup news, injury to key player).

**Trade / re-rate positions** (bought cheap to sell into a price rise — futures,
props, awards, or any cheap contract held as a trade): the thesis is to **sell
into the re-rate, not to hold for the outcome**. The exit ladder, catalyst-timed
selling mechanic, stop-losses, and liquidity rules live in ONE place:
`references/trade-exit-strategy.md` — read it before any trade exit. Execute each
tranche via `scripts/place_bet.py sell` after checking order-book depth (limit-sell
thin books, trickle large exits).

### Settlement Pitfalls

- **Never write reconciliation/price-check scripts from scratch.** The
  `scripts/` directory has working, battle-tested versions that handle Windows
  paths, RSA signing, and Kalshi schemas correctly. Copy them to `/tmp/` and run
  them. Inline scripts invite path bugs (`/c/Users/…` in Python on Windows) and
  auth drift.
- **The Polymarket-bound `kairos_*` tools are dead on this host** (`kairos_reconcile_positions`, `kairos_performance`, `kairos_get_bankroll`, `kairos_evaluate_bet`, `kairos_fair_value`, `kairos_find_markets`, `kairos_get_market_price`, `kairos_check_velocity`, `kairos_vet_signal`). Use the scripts in `scripts/` instead. **ESPN-sourced tools** (`kairos_list_matches`, `kairos_get_match_state`) work fine.
- **Never report a price move from memory.** Always fetch the current price
  from Kalshi (`GET /markets/{ticker}`) before claiming a position has moved.
  If you can't fetch the price, say so explicitly.
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

## Communication

**All cron outputs go to the World Cup group** (`telegram:World Cup (group)`, chat_id `<group chat_id>`), not the operator's DM. Both Grant (operator) and the co-financier (co-financier) see everything. the co-financier has equal standing — respond to him directly with the same autonomous style, no deferring to Grant.

When the operator asks you to respond to a group message: the session architecture means you cannot see group messages that don't trigger a session. If a group message went unanswered, the operator will forward it to your DM — respond immediately in the group (not the DM) via `send_message(target='telegram:World Cup (group)')`.

- Markdown: bullet lists (no tables)
- Concise reporting, flag only actionable moves
- **bold** position names in position summaries
## Pitfalls

- **Cron delivery defaults to DM — verify target.** New cron jobs default `deliver='telegram'` (the home DM channel), not the group. When creating or updating cron jobs, explicitly set `deliver='telegram:World Cup (group)'`. Use `cronjob(action='list')` to audit delivery targets periodically — a job silently routing to DM means the co-financier misses the output.
- **Telegram `require_mention` must be false for group responsiveness.** By default, Hermes's Telegram integration only processes messages that mention the bot. To respond to all group messages, run: `/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config set telegram.require_mention false`. The bot may also need privacy mode disabled via @BotFather (`/setprivacy` → Disable). The hermes gateway needs a restart to pick up config changes.
- **Hermes CLI location on this host**: `/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe`. It is NOT on PATH and NOT installed via npm globally. The `npx hermes` cache at `node_modules/hermes/bin/hermes` is unreliable (argument-parsing issues). Use the venv-installed binary directly.

- **Never report a price move from memory.** Always fetch the current price from Kalshi (`GET /markets/{ticker}`) before claiming a position has moved. Sessions expire and memory can be stale — a false move alert erodes operator trust. If the API returns an error, report the error, not an assumed move.\n- **Position summaries to the user require live fetches.** Any message that includes a current price for an active position must be preceded by a live `GET /markets/{ticker}` call in the same session. Do not carry prices forward from cron output or prior turns — the user sees your message and may act on it. If you can't fetch (API down, rate-limited), say so explicitly rather than quoting a possibly-stale price.\n- **Disambiguate when a team has multiple active markets.** Group-stage teams appear in 3+ Kalshi markets (one per group match). If you report "Ecuador at 81¢" while the user is looking at a different Ecuador market (CIVECU at 41¢), the numbers appear wrong and erode trust. Every position summary must include date + opponent + ticker — e.g. "Ecuador (vs Curaçao, Jun 20 — ECUCUW)". Never use team name alone as a price label.
- **Kalshi `with_nested_markets=true` returns null/unreliable fields**: When fetching events with nested markets, `yes_bid`, `yes_ask`, `volume`, `last_price`, AND `liquidity_dollars` are all unreliable from the nested objects. Prices are `null`; `liquidity_dollars` often shows `"0.0000"` even when the orderbook API has substantial depth. The nesting gives tickers and subtitles only. For price data, discover markets via the events endpoint, then fetch prices individually via `GET /markets/{ticker}`. For liquidity, always use the orderbook API (`GET /markets/{ticker}/orderbook`) — it is the authoritative liquidity source, not the `liquidity_dollars` field from nested events. See `references/kalshi-api-pagination.md` for the full pagination pattern.
- ⚠️ **Empty orderbooks on pre-match markets — check the book, but small orders can still fill.** Kalshi markets may show `yes_ask`/`yes_bid` prices but return empty yes/no arrays from `GET /markets/{ticker}/orderbook`. **Before betting, always check the orderbook.** An empty-looking book means only indicative prices are visible — but **small limit orders at the displayed ask CAN fill immediately** (market maker provides hidden liquidity that doesn't appear as resting orders). Jun 11 session confirmed: two limit orders (10 shares at 23¢, 2 shares at 21¢) filled instantly despite empty orderbooks. For larger orders (>$5), an empty book is still a warning — hidden depth may not extend to larger sizes. Use small-lot limit orders and verify fills. The displayed prices ARE tradeable for small size even with an empty-looking book. The inverse also happens: `liquidity_dollars` may read `"0.0000"` from the events endpoint while the orderbook API shows real resting orders — trust the orderbook API, not the field.
- `skill_view` may fail to load plugin-provided skills that appear in the listing — fall back to the cron prompt's embedded instructions
- Windows host: terminal runs git-bash (POSIX), not PowerShell. MSYS paths work alongside C:\ paths. `write_file` to `/tmp/foo.py` lands at `C:\tmp\foo.py` — use the full Windows path in `terminal()` calls.
- Cron jobs: `execute_code` may be blocked (`approvals.cron_mode` restriction) — use `terminal()` with inline python instead. For multi-step scripts, `write_file` the script first, then `terminal("python3 C:/tmp/script.py")`.
- **Auth signature failure (`INCORRECT_API_KEY_SIGNATURE`)**: If the `kalshi_auth.py` script returns headers that Kalshi rejects with 401/INCORRECT_API_KEY_SIGNATURE, try: (1) verify `kalshi_key.pem` exists and is a valid RSA PRIVATE KEY, (2) re-run from the script's own directory (`cd /c/Users/gsche/.hermes/kalshi && python3 kalshi_auth.py ...`), (3) check if the API key (`KALSHI-ACCESS-KEY`) was rotated — the key ID is `${KALSHI_API_KEY}` as of Jun 5. The `kalshi_key.pem` at `/c/Users/gsche/.hermes/kalshi/` is the persistent key file (NOT `/tmp`). Do NOT capture this as a permanent "auth is broken" rule — it is a diagnostic checklist for transient signature issues.
- **Python terminal() calls cannot read `/c/Users/...` paths**: Python's `open()`, `os.path.exists()`, and subprocess file arguments fail with `/c/Users/...` paths on this Windows git-bash host. Use `C:/Users/gsche/...` (forward-slashed Windows path) instead. Example: `key_file = "C:/Users/gsche/.hermes/kalshi/kalshi_key.pem"` NOT `/c/Users/gsche/.hermes/kalshi/kalshi_key.pem`. This applies to all Python code inside terminal() heredocs and subprocess calls.
- **Order placement is script-only**: every buy/sell goes through `scripts/place_bet.py` — it owns the wire format (string `count`/`price`, `client_order_id`, limit type), the rails, and the journal. If an order needs to happen and the script can't do it, fix the script; do not hand-roll a POST.
- **Never ask "Want me to place it?"** — operation mode is FULLY AUTONOMOUS. If the research is done and the edge is stateable, place the bet and report the confirmation. If the edge isn't there, state the pass and why. Permission-seeking is a rail violation identical to betting without sources.
- **X data gathering when web tools are down**: `web_search` and `web_extract` require Firecrawl (may be unconfigured). `x_search` (xAI/Grok) works independently — both from the parent agent AND from `delegate_task` subagents. Subagents only fail on `web_search`/`web_extract`. Use `delegate_task` with `toolsets: [\"x_search\"]` to fan out parallel X research across multiple matches in one turn. For non-X data (Wikipedia, ESPN, Transfermarkt), use `browser_navigate` + `browser_console` as fallback from the parent — subagent browser snapshots are often truncated.
- **Kalshi events endpoint uses `event_ticker`, not `ticker`.** When parsing `GET /events?...` responses, the event-level key is `event_ticker` (e.g. `\"event_ticker\": \"KXWCGROUPQUAL-26F\"`). Accessing `event['ticker']` raises `KeyError`. Markets within events DO use `ticker`. Affects all series-discovery code. Subagents with `toolsets: [\"web\"]` or `[\"browser\"]` cannot reliably fetch eloratings.net because web tools require Firecrawl and browser snapshots are truncated. Elo ratings are stable during tournament periods (no competitive matches between group-stage game days), so the benchmark table in `references/elo-to-fv-manual.md` is the primary fallback. Only re-fetch Elo from the parent's browser if several matchdays have passed or the benchmark table doesn't cover the teams. Never delegate Elo fetching — it will fail silently and return no data.
- **Kalshi ticker team ordering doesn't follow a fixed convention — always discover, never guess.** The team order in Kalshi event tickers (e.g. `KXWCGAME-26JUN13QATSUI` = Qatar first, `KXWCGAME-26JUN13HTISCO` = Haiti first) does not reliably match the "home @ away" convention from ESPN's `kairos_list_matches`. Never guess a ticker prefix from match listing order — always discover the actual event ticker via `GET /events?series_ticker=KXWCGAME&limit=100` and extract the correct prefix before constructing individual market tickers. A guessed ticker (e.g. `KXWCGAME-26JUN13SUIQAT` instead of `KXWCGAME-26JUN13QATSUI`) returns HTTP 404.
- **Not every match has both sides listed on Kalshi.** Some KXWCGAME events only have markets for one team. Example: `KXWCGAME-26JUN13HTISCO-SCO` existed but `KXWCGAME-26JUN13HTISCO-HAI` returned 404. After discovering an event ticker, verify both individual market tickers exist before trying to price both sides. A missing side is a data point (no tradeable market), not a bug.
- **Elo data provenance — two tiers, two thresholds.** Elo ratings have a quality tier that directly affects confidence: (a) **Benchmark Elo** — from the calibrated table in `references/elo-to-fv-manual.md`. Trusted, stable, Dixon-Coles validated. Standard 3¢/5¢ edge thresholds apply. (b) **X-sourced Elo** — approximate rankings or point estimates scraped from X posts. Directional but imprecise (often ±50 points off). When FV rests on X-sourced Elo, raise the net-edge threshold to **6¢** to compensate for the FV-uncertainty. Additionally, an X-sourced Elo-only bet (no injury/form/H2H edge) should pass regardless of computed edge — two weak signals don't make a strong one. Example from Jun 12 scan: TUN FV ~28% on X-sourced Elo gave ~5¢ net edge vs 22¢ ask → passed. JPN FV ~34% on benchmark Elo gave ~6.7¢ net edge → bet placed. The Elo source was the deciding factor.
- **eloratings.net is JS-rendered — static curl fetches return no ratings.** The `en.teams.tsv` file provides team-code→name mappings (useful for decoding) but contains no Elo values. The actual ratings load dynamically. See `references/eloratings-data-structure.md` for the full breakdown of what's fetchable and what's not. Benchmark table is the primary fallback; X-sourced Elo is the backup. Never burn more than 2-3 curl attempts on eloratings.net before falling back.
