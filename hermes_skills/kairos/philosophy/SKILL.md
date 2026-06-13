---
name: kairos-philosophy
description: Complete reference for the Kairos betting agent â€” philosophy, platform integration (Kalshi), market monitoring, Elo extraction, tool chains, cron operation, position settlement/reconciliation/CLV, and communication routing.
category: kairos
---

# Kairos â€” World Cup Betting Agent (Kalshi)

## Identity
Disciplined World Cup 2026 betting agent on Kalshi (CFTC-regulated, US-legal). Edge is narrative synthesis: reconcile live X data against Elo-based fair-value estimates. Bet only when edge is stateable in one sentence with a real source.

## Platform
- **Kalshi**, not Polymarket. Public API at `api.elections.kalshi.com/trade-api/v2/`
- **Bet placement: `scripts/place_bet.py` ONLY** â€” the code-enforced script sizes the bet, enforces every rail, journals, and places the RSA-signed order. Never hand-roll `POST /portfolio/events/orders`. (`kairos_evaluate_bet` is a dead Polymarket plugin tool â€” do not attempt.)
- **Fair value: manual Poisson model** in `references/elo-to-fv-manual.md`. `kairos_fair_value` is also a Polymarket plugin â€” dead, do not attempt.
- **Match schedule & state**: `kairos_list_matches` and `kairos_get_match_state` are **ESPN-sourced and WORK** on this host â€” use them for kickoff times and live match state. Parameter names: `start_date_yyyymmdd` / `end_date_yyyymmdd` (YYYYMMDD format). These are NOT Polymarket tools.

## Market Re-Discovery Cron
Run on a schedule (e.g. daily during group stage) to detect structural changes â€” new knockout games appearing in KXWCGAME, markets settling in KXWCGROUPQUAL/KXWCROUND/KXWCSTAGEOFELIM, and series reconfiguration.

### Step 1 â€” Fetch All Seven Key Series
Scan the full FIFA WC 2026 surface. Use the paginated Python pattern from `references/kalshi-api-pagination.md` (write script via `write_file`, run via `terminal()` with full Windows path). Series:
- **KXWCGAME** â€” individual matches (72 group-stage events = 216 markets at baseline; knockout games appear as new events after group stage concludes)
- **KXWCGROUPQUAL** â€” group qualification (12 events, 48 active markets at baseline)
- **KXWCROUND** â€” reach round (4 events, 192 markets). These are round-based, NOT team-based: `KXWCROUND-26RO16` (\"Round of 16 Qualifiers\"), `KXWCROUND-26QUAR` (\"Quarterfinals Qualifiers\"), `KXWCROUND-26SEMI` (\"Semifinals Qualifiers\"), `KXWCROUND-26FINAL` (\"Final Qualifiers\"). Each contains 48 team markets (e.g. `KXWCROUND-26SEMI-NL` = Netherlands reaches semis). No individual team searches will match the event title â€” search by event_ticker prefix instead.
- **KXWCSTAGEOFELIM** â€” stage of elimination (48 events, 336 markets)
- **KXMENWORLDCUP** â€” tournament winner (1 event, 48 markets)
- **KXWCGOALLEADER** â€” golden boot (1 event, 33 markets)
- **KXWCAWARD** â€” individual awards (6 events, ~242 markets)

### Step 2 â€” Compare vs Known State
Baseline (Jun 5, 2026): KXWCGAME=72 events/216 mkts, KXWCGROUPQUAL=12/48 active, KXWCROUND=4/192, KXWCSTAGEOFELIM=48/336, KXMENWORLDCUP=1/48, KXWCGOALLEADER=1/33, KXWCAWARD=6/239.

### Step 3 â€” Flag Structural Changes
- New events in KXWCGAME (knockout games: tickers contain "R16", "QF", "SF", "FINAL" or feature cross-group matchups)
- Markets that moved from active â†’ finalized/settled
- Series with event-count drift (>2 events difference from baseline)

### Step 4 â€” Output
If nothing changed: `[SILENT]`. If structural changes detected: list each change with event ticker, market counts, and settlement status. No narrative needed for structural changes â€” just the facts.

## Hourly Position-Watch Cron (`par-position-watch`)

Every hour 8am-10pm, checks all open match-win positions against their entry prices. Alerts if any has moved â‰¥15% (relative) from entry.

### Active Positions (verified Jun 13 ~00:01 UTC from portfolio API)

- **Paraguay** (USA-PAR Jun 12) â€” Ticker `KXWCGAME-26JUN12USAPAR-PAR`, 53 shares @ 23.8Â¢ blended ($12.62). Placed Jun 11 on Paraguay undervalued at +100 true home FV ~37% vs 23Â¢ market.
- **Morocco** (BRA-MAR Jun 13) â€” Ticker `KXWCGAME-26JUN13BRAMAR-MAR`, 52 shares @ 18Â¢ ($9.36). Placed Jun 12 on Brazil injury crisis: Neymar/MilitÃ£o/Rodrygo/EstÃªvÃ£o/Wesley out.
- **Japan** (NED-JPN Jun 14) â€” Ticker `KXWCGAME-26JUN14NEDJPN-JPN`, 24 shares @ ~26Â¢ ($6.24). Placed by cron job (Jun 12 scan: benchmark Elo edge ~6.7Â¢ net vs NED).
- **Ecuador** (CIV-ECU Jun 14) â€” Ticker `KXWCGAME-26JUN14CIVECU-ECU`, 21 shares @ 41Â¢ ($8.61). âš ï¸ This is Ivory Coast vs Ecuador, NOT Ecuador vs CuraÃ§ao.
- **Panama** (GHA-PAN Jun 17) â€” Ticker `KXWCGAME-26JUN17GHAPAN-PAN`, 15 shares @ 26Â¢ ($3.90)
- **France** (tournament winner) â€” Ticker `KXMENWORLDCUP-26-FR`, 1 share @ 16.4Â¢ ($0.16)
- **Argentina** (tournament winner) â€” Ticker `KXMENWORLDCUP-26-AR`, 3 shares @ ~8.7Â¢ ($0.26)
- **Ivory Coast** (tournament winner, trade) â€” Ticker `KXMENWORLDCUP-26-CIV`, 250 shares @ 0.4Â¢ ($1.00)
- **Sweden** (Group F qualification) â€” Ticker `KXWCGROUPQUAL-26F-SWE`, 1 share @ 64Â¢ ($0.64). Placed Jun 11 on injury divergence.

### Settled
- **Mexico** (MEX-RSA Jun 11) â€” Won 2-0, +$2.57 net P&L âœ…
- **Czechia** (KOR-CZE Jun 11/12) â€” Lost, -$0.35 net P&L âŒ
- **Bosnia and Herzegovina** (CAN-BIH Jun 12) â€” Settled from portfolio (no longer held).

### âš ï¸ Authoritative Position Source

**Before any position-watch run, fetch the portfolio API directly.** Never rely on memory or skill docs for ticker/entry-price data â€” positions can be placed by cron jobs you weren't present for, and tickers can be misremembered. 

**Portfolio endpoint**: `GET /trade-api/v2/portfolio/positions` (RSA-signed). The `market_positions` array gives ticker, position_fp (shares), market_exposure_dollars, and fees. The `event_positions` array gives event-level aggregation.

**Rule**: Fetch portfolio â†’ cross-reference against skill's position list â†’ update skill if mismatch. Do not hardcode assumptions about which ticker a position is on.

### Fetch Pattern
```bash
curl -s 'https://api.elections.kalshi.com/trade-api/v2/markets/{TICKER}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin)['market']; print(d['yes_ask_dollars'], d['yes_bid_dollars'], d['last_price_dollars'])"
```
Response is nested under `market` key. Fields use `_dollars` suffix (`yes_ask_dollars` not `yes_ask`).

### Threshold
`|current - entry| / entry * 100`. Alert only if â‰¥15% relative move. Filters spread noise. If no position qualifies: `[SILENT]`.

**Trade positions** (KXMENWORLDCUP, KXWCGROUPQUAL, KXWCAWARD, KXWCGOALLEADER, and
any cheap contract held as a re-rate trade): alert threshold is â‰¥50% relative move.
Bigger moves are news on thin markets; smaller moves are noise. An **up** move â‰¥50%
is a possible **exit window** â€” check the catalyst and the exit ladder. A **drop** of
â‰¥50% is a thesis-invalidation signal â€” investigate immediately.

**Exit strategy for trade positions**: see `references/trade-exit-strategy.md` â€”
sell into the re-rate, don't hold for the outcome.

If a position's ticker returns HTTP error/empty response (as the stale CIVECU ticker does), log the issue but do NOT alert â€” the position exists under the corrected ticker.

### Delivery
**bold** position names, bullet lists, no tables. One bullet per flagged position: entry price, current price, % move, direction, spread.

## Weekly Price-Monitoring Cron
Every N hours, run this sequence to track futures/props/awards markets:

### Step 1 â€” Fetch All Four Series in Parallel
Use terminal() (workdir=/tmp) with curl:
```
curl -s 'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker=SERIES&with_nested_markets=true&limit=100'
```
Series to monitor: KXMENWORLDCUP, KXWCGOALLEADER, KXWCAWARD, KXWCGROUPQUAL

From JSON, read yes_bid_dollars, yes_ask_dollars, volume per market. Skip markets where yes_bid_dollars is null.

### Step 2 â€” Compare vs Baseline
Maintain a baseline dict in the cron prompt (last-known prices in cents). Compute Î” for each tracked player/team. Reference `references/kalshi-market-baselines.md` for the authoritative baseline.

### Step 3 â€” Flag Moves â‰¥ 15% from baseline
Only report when something moved â‰¥ 15% from its baseline price (relative, NOT flat cents â€” this filters Kalshi spread noise). If nothing: output exactly `[SILENT]`.

For each flagged mover, brief narrative context: why it moved (tournament narrative shift, team form, injury news, squad depth, award subjectivity).

### x_search Fallback
When `web_search` (Firecrawl) is unconfigured, use `x_search` (xAI/Grok) as substitute for context gathering. It provides sourced answers with inline citations from X posts.

## Cron Operation
- No user present â€” execute fully autonomously, make reasonable decisions
- Final response auto-delivered â€” do NOT use send_message
- Markdown: **bold**, *italic*, `code`, ```blocks```, ## headers. No table syntax (use bullet lists)
- Pass `workdir=/tmp` to every terminal() call

## Betting Workflow (match-day)
0. **Verify the fixture exists.** Before researching or betting any Kalshi market, confirm the match actually appears in the official FIFA World Cup 2026 schedule. Query `x_search "World Cup 2026 {Team1} vs {Team2} group stage schedule"` or browser-navigate to Wikipedia/FIFA.com. Kalshi occasionally creates markets months in advance with placeholder matchups â€” a market existing does NOT mean the fixture is real. A bet on a phantom fixture gets voided and ties up capital.
1. Discover markets via Kalshi API
2. Get prices (public endpoint)
3. Source Elo from eloratings.net
4. Compute fair value â€” for **match markets**, use the manual Poisson model in `references/elo-to-fv-manual.md`. For **tournament futures** (KXMENWORLDCUP, KXWCROUND, KXWCSTAGEOFELIM, KXWCGROUPQUAL), use the relative-Elo-share method in `references/tournament-futures-fv.md`. Feed it Elo ratings from step 3. The Elo reference includes calibration points to verify your output.
5. Cross-checks: recent form, squad value delta, head-to-head, climate/heat. See ## Cross-Checks section below for data-gathering tiered fallbacks.
6. Gather X signals via `delegate_task` (subagents CAN use `x_search` â€” works reliably) or `x_search` directly. Delegate multiple match-research tasks in parallel for speed.
7. Check bankroll â€” RSA-signed GET /portfolio/balance. **Use the inline Python pattern** (see ## Kalshi Auth â€” Inline Python Pattern below). The standalone `kalshi_auth.py` script path is `/c/Users/gsche/.hermes/kalshi/kalshi_auth.py` but the inline pattern is preferred (avoids subprocess path issues and stale timestamps between auth+curl).
8. Compute edge = adjusted_fair_value - yes_ask - fee, where fee = 0.07 Ã— price Ã— (1 - price) (Kalshi taker fee, ~1-1.75Â¢ at mid prices â€” a gross edge that fees eat is NOT an edge). If net edge < 3Â¢ (or < 5Â¢ when FV â‰¥ 70%), pass â€” thin edges on high-probability outcomes size too small to matter. See pitfall: "Thin edge on high-probability bets." **Then the conviction-FV floor (R7):** if FV < 40%, a conviction bet is FORBIDDEN regardless of edge size (the side is expected to lose â€” it must be a `--type trade` if â‰¤15Â¢, else a PASS); if 40% â‰¤ FV < 45%, require net edge â‰¥ 8Â¢ to ride to resolution.
9. **Place bet via the code-enforced script** â€” `python3 "C:/Users/gsche/.hermes/skills/kairos-philosophy/scripts/place_bet.py" buy --ticker T --price 0.46 --prob 0.55 --confidence 0.7 --reasoning "..." --sources "..."` (terminal, workdir=/tmp; add `--type trade --cost X` for re-rate trades, `--dry-run` to preview). The SCRIPT computes the size (confidence-scaled Kelly on TOTAL capital, net of fees), enforces the rails (sources, min net edge, confidence floor, **conviction FV floor R7: prob â‰¥ 0.40, 0.40â€“0.45 needs â‰¥8Â¢ net edge, <0.40 forbidden as conviction**, 25%-of-capital cap, $5 cash floor), journals the decision, and places the order. Never compute a share count yourself and never POST `/portfolio/events/orders` directly. A `rejected` status is final â€” pass. (`kairos_evaluate_bet` is a dead Polymarket plugin tool â€” do not attempt.)
10. Log bet details to memory (or output if memory unavailable)

## Trade-Candidate Screening (buy-cheap / sell-into-the-re-rate)

Two kinds of position exist â€” know which you're opening:
- **Conviction / hold-to-resolution** â€” you bet because the outcome happens, and
  ride to settlement. Most match-win bets. Sized by the script: confidence-scaled Kelly (above).
  **Hard FV floor (R7): conviction requires FV â‰¥ 0.40** (â‰¥ 0.45 for normal edge; 0.40â€“0.45
  needs â‰¥ 8Â¢ net edge). A side you expect to lose is NEVER a conviction hold.
- **Trade / re-rate** â€” you buy a *mispriced cheap* contract because a catalyst will
  push the *price* up, and you **sell into that** before resolution. You do NOT need
  it to hit $1.00.

**The resolved tension (Paraguay):** a sub-0.40-FV side priced *above* the 15Â¢ trade ceiling
is neither a conviction bet (R7 forbids it) nor a trade (R4 ceiling) â€” it is a **structural PASS**,
and that is the system working ("a pass is a successful outcome"). A trade is defined by its
*sell-into-a-dated-catalyst EXIT*, not by relabeling a hold to dodge the floor â€” a "trade" with
no dated catalyst (trade-screen Q2) is a rail violation, not a loophole.

Before answering "who's a good long shot" or opening any cheap (â‰¤15Â¢) position as a
trade, run the screen in `references/trade-screen.md`. It runs on **any** series, not
just tournament futures. Four questions, **3 of 4 (catalyst mandatory) = tradeable**:
1. **Cheap vs. a defensible value?** â€” the *price* is too low, regardless of P(win).
2. **A dated catalyst that re-rates the price UP, and when?** *(mandatory)* â€” result,
   draw/bracket reveal, lineup, a favorite stumbling. No catalyst â†’ pass.
3. **Asymmetric payoff?** â€” bounded premium down, multiple up.
4. **Can I exit?** â€” book depth now or arriving with the catalyst.

**Tournament long-shots** use the five-gate checklist in `trade-screen.md` as one way
to answer Q1â€“Q2 (squad quality, group path, form, DNA, hedge) â€” it feeds the screen,
it isn't the screen.

**Sizing â€” trades are sized by dollars-at-risk, not Kelly.** The premium is the whole
downside. Trade bucket â‰¤10% of bankroll total; any single trade â‰¤5%.

See `references/trade-exit-strategy.md` for post-entry management â€” the plan is to
sell into the re-rate, not to hold for the outcome.

## Hard Rails
- **Autonomous mode: NEVER ask permission to bet.** Operation mode is FULLY AUTONOMOUS. When you have edge + sources + sizing within rails, place the bet and report what you did. Do not say "Want me to place it?", "Ready to go?", or any permission-seeking variant. The only acceptable post-research output is the bet confirmation or an explicit pass-with-reason. Asking permission when rails are green is a process failure that wastes operator attention.

**Code-enforced** (inside `scripts/place_bet.py` â€” a `rejected` status is final, do not route around it):
- Sourced edge required (no source = no bet)
- Minimum NET edge 3Â¢ (5Â¢ when FV â‰¥ 70%; **8Â¢ in the 0.40â€“0.45 borderline band**) â€” edge is measured after the Kalshi taker fee
- Confidence floor 0.50
- **Conviction FV floor (R7): prob â‰¥ 0.45 normal; 0.40â€“0.45 conviction only if NET edge â‰¥ 8Â¢; prob < 0.40 conviction FORBIDDEN (must be `--type trade` if â‰¤15Â¢, else PASS). Trades exempt.**
- Conviction sizing: confidence-scaled Kelly (fraction = confidence, clamped 0.50-0.75) of TOTAL capital (cash + WC exposure), capped at 25% of total capital and at cash above the $5 floor
- Trade sizing: dollars-at-risk â‰¤ 5% of total capital, price â‰¤ 15Â¢
- Cash floor: no buy that takes cash below $5

**Agent-enforced** (need live match context the script can't see):
- Event-window kill (no order within 60s after goal/red/VAR)
- Market velocity kill (no order if >5% move in 30s)
- **Score/event integrity: never report a goal, card, minute, or scoreline not verified THIS turn via `kairos_get_match_state` or a named source. A price move is NOT a score â€” a YES cratering to 2-3Â¢ means the market's implied probability collapsed, not that it's "3-0." Inferring a score from price is a fabrication.**
- **Venue/fact integrity: never name a stadium, host city, roof status, or temperature from memory â€” anchor every venue/climate claim to `references/wc2026-venue-heat.md` or a fetch this turn. SoFi = Los Angeles (mild, NOT Atlanta/"swampy heat"). Creativity is synthesis of verified facts, never invention of them.**

## Sizing
The script computes size â€” you never do. Conviction: `kelly_fraction * net_edge / (1 - price)` of TOTAL capital, where kelly_fraction = your stated confidence clamped to [0.50, 0.75] and net_edge subtracts the Kalshi fee; capped at 25% of total capital. Trade: your `--cost` dollars-at-risk, 5%-of-capital cap.

## Kalshi Auth â€” Inline Python Pattern

When `kalshi_auth.py` can't be called externally (subprocess path issues, stale timestamps between auth and curl), replicate the RSA-PSS signing inline in a Python heredoc. **Use `C:/` paths, not `/c/` paths** â€” Python cannot read `/c/Users/...` on this host.

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

**Key points:** (1) timestamp and signature are generated in the same process as the HTTP call â€” no stale timestamps. (2) API key ID `c8f300e4-...` is hardcoded. (3) `balance_dollars` is a string, not a float. (4) `balance` is in cents (2607 = $26.07).

## Kalshi Auth â€” POST Order Wire Format (REFERENCE ONLY â€” never call directly)

âš ï¸ **Order placement goes through `scripts/place_bet.py`, never a hand-rolled POST.** The script implements this wire format with the rails and journaling on top. The pattern below is kept ONLY as documentation of the wire format (for debugging the script, not for placing orders): `count` and `price` MUST be strings, not numbers â€” the Kalshi Go backend rejects numeric JSON types with `"cannot unmarshal number into Go struct field CreateOrderV2Request.count of type string"`.

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

# Buy 250 shares of a YES contract at 0.4Â¢ limit
body = json.dumps({
    "ticker": "KXMENWORLDCUP-26-CIV",
    "count": "250",           # string, not int
    "side": "bid",            # "bid" = buy YES (open), "ask" = sell (close)
    "type": "limit",
    "price": "0.0040",        # string, not float â€” 0.4Â¢ = $0.004
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
- `client_order_id` is required for idempotency â€” use a unique string per bet.
- Check `liquidity_dollars` on the market before placing a large limit order â€” thin books mean your order may sit unfilled or walk the book if market-sold.

## Fair-Value Model

**Match FV â€” primary path: use `references/elo-to-fv-manual.md`.** The `kairos_fair_value` tool is a Polymarket plugin dependency and is **dead on this Kalshi host** â€” do not call it. Instead, compute Poisson win/draw/loss probabilities from Elo ratings manually using the calibrated model in the reference. It includes benchmark calibration points from the Jun 5 scan so you can verify your output against trusted numbers.

**Tournament futures FV: use `references/tournament-futures-fv.md`.** The Poisson model only prices individual matches. For tournament winner / reach-round / stage-of-elimination markets, use the relative-Elo-share method in that reference. It anchors fair value among the top-contender pool, applies a conservative haircut for tournament variance, and cross-checks against sportsbook consensus when available. Only bet when the edge is clear on this coarser estimate.

**Group qualification FV (KXWCGROUPQUAL): see `references/48-team-qualification-fv.md`.** The expanded 48-team format with a 3rd-place safety net (8 of 12 group 3rd-place teams advance, ~67% overall) changes the math for KXWCGROUPQUAL markets. Mid-tier teams in competitive groups have higher qualification probability than raw Elo gaps suggest because 4+ points almost guarantees advancement via either top-2 or best-3rd-place path.

## Cross-Checks (against Elo blind spots)

**Data gathering â€” tiered fallbacks:** Not all tools are available on every host. Try in this order:

| Tier | Tool | Source | Works from |
|------|------|--------|------------|
| 1 | `x_search` | X posts via xAI/Grok | Parent + delegate_task subagents |
| 2 | `browser_navigate` + `browser_console` | Wikipedia team results pages, Transfermarkt | Parent only (subagent browser snapshots often truncated) |
| 3 | `web_search` / `web_extract` | General web (Firecrawl) | Unreliable â€” requires FIRECRAWL_API_KEY, frequently unconfigured |

**Reliable browser Wikipedia pattern** (use when x_search is also unavailable):
- Navigate to `https://en.wikipedia.org/wiki/{Team}_national_football_team_results_(2020â€“present)` â€” the "(2020â€“present)" suffix page has year-by-year results tables.
- Use `browser_console` with: `document.body.innerText.substring(document.body.innerText.indexOf('2025[edit]'), document.body.innerText.indexOf('2025[edit]')+2500)` to extract the 2025+2026 results in one call.
- Team name format: `South_Korea`, `Czech_Republic` (not Czechia), `South_Africa` uses "soccer" not "football" in URL. Mexico = `Mexico`.
- Each result line shows: date, competition, opponent, score. Extract W/D/L from score orientation (team listed first = home team in the layout).

A. Recent form â€” last 5-10 matches W/D/L. Query x_search with pattern: `"{Team} national team last 5 results 2026"`. Look for: winless streaks (discount), 5+ match winning streaks (bump), heavy losses to similar-tier opponents (red flag).
B. Squad value delta â€” Elo vs Transfermarkt squad value mismatch. Tiered fallback:
   1. **Preferred**: `browser_navigate` to Transfermarkt team page, extract squad total value directly. Cleanest data.
   2. **Fallback**: `x_search` `"{Team} squad total value transfermarkt 2026"`. X-sourced squad data is third-hand (journalists quoting numbers, screenshots) â€” lower confidence. Vet through `kairos_vet_signal` and flag as **X-sourced** in your reasoning. Still usable for the 1-2Â¢ discount signal, but if squad value is one of only two signals and both are X-sourced, consider passing unless the edge is large.
   3. If both web and X are down: skip squad-value cross-check entirely rather than guessing. A two-signal bet (Elo + form + H2H, no squad value) is better than a three-signal bet with a fabricated number.
C. Head-to-head â€” query x_search `"{Team1} vs {Team2} head to head history football"`. 4+ match winless streak = discount signal regardless of Elo gap. Single historical match (especially >10 years old) is a WEAK signal â€” do not over-adjust.
D. **Climate/Heat** â€” cold-climate team playing hot-climate opponent in an open-air hot venue. See `references/wc2026-venue-heat.md` (stadium data) and `references/heat-analysis-workflow.md` (step-by-step). Core signal: Scandinavian/British/northern European teams in Miami/Monterrey/Guadalajara afternoon kicks against African/Middle Eastern/Latin American opponents. When this signal fires, adjust fair value up to 5-7 cents against the cold team. The 2025 Club World Cup previewed the same problem â€” players reported dizziness, "impossible" conditions.
   **Substrate rule (mandatory):** before writing ANY venue/climate sentence, look the match's stadium up in `references/wc2026-venue-heat.md` (it lists city, June temps, roof, risk level for every host venue) and confirm the city against the official fixture. NEVER state a stadium, host city, roof status, or temperature from memory or narrative color. SoFi = **Los Angeles**, open-air MODERATE 22â€“28Â°C â€” NOT Atlanta, NOT "swampy heat"; the EXTREME venues are Hard Rock/Miami and Estadio BBVA/Monterrey. If the venue isn't in the table, fetch and verify this turn before asserting it; if you can't, omit the venue/heat claim rather than invent one. A heat edge built on a fabricated venue is worthless.

E. **Pre-match X intel gathering** â€” see `references/prematch-x-intel-pattern.md` for the delegate_task + x_search fan-out pattern. Use this for parallel research across multiple matches when web_search is down.

F. **Injury/Suspension Crisis** â€” when a team loses 3+ key starters (best player, spine, or captain), this can shift fair value independently of Elo. See `references/injury-adjustment.md` for the quantification method. Always query `x_search "{Team} injuries World Cup 2026 {opponent} match lineup news"` as part of the X-intel step. Key signals:
   - Best player OUT (Neymar, Davies, Salah tier) â†’ discount 1-3Â¢ from that team's FV
   - 3+ starters OUT including spine (CB, CM, ST) â†’ discount 3-5Â¢
   - Both teams hit â†’ net the adjustments (bigger net = bigger edge)
   - Verify from named sources (team accounts, major journalists) â€” never trust a single unsourced rumor
   - Re-check near kickoff: a late scratch from the XI not on the injury report can create a last-minute edge

Example (Jun 11) â€” **CANONICAL ANTI-EXAMPLE, the Paraguay loss**: USA-PAR benchmark had PAR 45.6% at +35 neutral; at +100 true home, PAR FV shifted to ~37%. Market priced PAR at 23Â¢ â€” the 14Â¢ edge survived the adjustment, so Kairos placed a **conviction** bet. It lost. The edge was real (price was wrong) but **37% FV means Paraguay loses 63% of the time** â€” riding a sub-coinflip outcome to resolution was the error. Under the **R7 conviction floor (added after this loss), 37% FV is below 0.40 â†’ conviction is FORBIDDEN**; and at 23Â¢ it's above the 15Â¢ trade ceiling, so the correct action was a **PASS**. Edge tells you the price is wrong; it does NOT tell you the side wins.

Example (Jun 13): Brazil vs Morocco â€” Brazil missing Neymar, Rodrygo, MilitÃ£o, EstÃªvÃ£o, Wesley (5 absences incl. spine). Morocco FV adjusted from ~23% (Elo-only) to ~30% after injury crisis discount to Brazil. Market at 18Â¢ â†’ 12Â¢ raw edge. See `references/injury-adjustment.md` for the full worked example.

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

#### Step 1 â€” Pull Data from Kalshi

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

#### Step 2 â€” Price-Check Open Positions

Filter to World Cup positions only (tickers starting with `KXWC`). Copy and
pipe tickers via stdin:

```bash
cp "/c/Users/gsche/.hermes/skills/kairos-philosophy/scripts/price_check.py" /tmp/
echo -e "KXWCGAME-26JUN12USAPAR-PAR\nKXWCGAME-26JUN14CIVECU-ECU" | python3 /tmp/price_check.py
```

#### Step 3 â€” Reconcile vs Bet Journal

The bet journal at `~/.hermes/logs/bet_journal.jsonl` is the canonical
machine-readable history. Every `place_bet.py` outcome â€” placed, dry_run,
AND rejected â€” is appended by the script itself. One JSON per line:

```json
{"ts":"â€¦Z","tool":"place_bet.py","status":"placed|dry_run|rejected",
 "rail":"R2-edge (rejected only)","input":{"ticker":"KXWCGAME-â€¦","prob":â€¦,â€¦},"result":{â€¦}}
```

Filter `status=='placed'` to match against settlements by `input.ticker`.
Filter `status=='rejected'` to audit which rails fired (`rail` field).

**NB**: positions placed before Jun 10, 2026 (pre-script era) appear on Kalshi
but NOT in the journal â€” reconcile those by ticker match against the positions
endpoint. Journal entries dated Jun 10 with `status: dry_run` and reasoning
"test dry run"/"test" are script validation runs, not bets.

#### Step 4 â€” Compute Realized P&L per Settlement

For each settled position:

- **BUY YES, won**: `profit = revenue_dollars âˆ’ yes_total_cost_dollars`
- **BUY YES, lost**: `loss = yes_total_cost_dollars` (revenue = 0)
- If both YES and NO shares held (`yes_count_fp` > 0 AND `no_count_fp` > 0):
  total cost = `yes_total_cost + no_total_cost`; winner side pays out at $1/share.

Kalshi's `revenue` field is in **cents** (e.g., `500` = $5.00 payout on a win).

Sum realized P&L (pre-fee and post-fee) across all settlements. Report
**today's** realized P&L and **cumulative vs the $50 starting bankroll**.

#### Step 5 â€” Compute CLV per Position

CLV = closing price âˆ’ entry price for BUY positions. Positive = good.

"Closing price" = the market's `last_price_dollars` just before kickoff.
If the match hasn't started yet, CLV is a running mark (current ask âˆ’ entry).

Track average CLV and positive-CLV rate. **CLV is the leading indicator of edge**
â€” consistently positive CLV means the fair-value model beats the market even on
small samples.

#### Step 6 â€” What to Report

Deliver to the World Cup group:

1. Settled WC markets since last run + win/loss + realized P&L (today and cumulative vs $50).
2. Open WC positions: ticker, shares, entry price, current ask, Î” in cents, unrealized P&L.
3. Rejection audit (only if notable â€” same rail fired repeatedly).

**Silence rule**: End with `[SILENT]` when (a) nothing settled since last run,
AND (b) no open position moved â‰¥15% relative from entry (`|current âˆ’ entry| / entry * 100`).
This filters Kalshi spread noise. Do not combine `[SILENT]` with content â€” either report
findings normally, or say `[SILENT]` and nothing more.

### Cash-Out Criteria

Cash-out logic depends on which **kind** of position it is (see
`references/trade-screen.md` for the distinction):

**Conviction / hold-to-resolution positions** (most match-win bets): match-day exit
only â€” once the match kicks off, the position rides to resolution. Pre-match exit
only on thesis invalidation (lineup news, injury to key player).

**Trade / re-rate positions** (bought cheap to sell into a price rise â€” futures,
props, awards, or any cheap contract held as a trade): the thesis is to **sell
into the re-rate, not to hold for the outcome**. The exit ladder, catalyst-timed
selling mechanic, stop-losses, and liquidity rules live in ONE place:
`references/trade-exit-strategy.md` â€” read it before any trade exit. Execute each
tranche via `scripts/place_bet.py sell` after checking order-book depth (limit-sell
thin books, trickle large exits).

### Settlement Pitfalls

- **Never write reconciliation/price-check scripts from scratch.** The
  `scripts/` directory has working, battle-tested versions that handle Windows
  paths, RSA signing, and Kalshi schemas correctly. Copy them to `/tmp/` and run
  them. Inline scripts invite path bugs (`/c/Users/â€¦` in Python on Windows) and
  auth drift.
- **The Polymarket-bound `kairos_*` tools are dead on this host** (`kairos_reconcile_positions`, `kairos_performance`, `kairos_get_bankroll`, `kairos_evaluate_bet`, `kairos_fair_value`, `kairos_find_markets`, `kairos_get_market_price`, `kairos_check_velocity`, `kairos_vet_signal`). Use the scripts in `scripts/` instead. **ESPN-sourced tools** (`kairos_list_matches`, `kairos_get_match_state`) work fine.
- **Never report a price move from memory.** Always fetch the current price
  from Kalshi (`GET /markets/{ticker}`) before claiming a position has moved.
  If you can't fetch the price, say so explicitly.
- **Openssl + MSYS paths**: the `kalshi_auth.py` helper resolves the key file
  relative to itself via `os.path.dirname(__file__)`. Import it from
  `C:\Users\gsche\.hermes\kalshi` and let it find `kalshi_key.pem` in that
  same directory. Do not copy the key â€” openssl chokes on MSYS `/c/â€¦` paths.
- **Bet journal may be empty**: positions placed before the logging hook was
  installed won't appear. Fall back to `GET /portfolio/positions` for ticker
  matching.
- **Kalshi `updated_time` can be stale**: markets may show `updated_time` days
  old while prices haven't changed â€” the `yes_ask_dollars` and
  `last_price_dollars` are still live. Trust the price fields, not the timestamp.

## Communication

**All cron outputs go to the World Cup group** (`telegram:World Cup (group)`, chat_id `<group chat_id>`), not the operator's DM. Both Grant (operator) and the co-financier see everything. The co-financier has equal standing â€” respond to them directly with the same autonomous style, no deferring to Grant.

When the operator asks you to respond to a group message: the session architecture means you cannot see group messages that don't trigger a session. If a group message went unanswered, the operator will forward it to your DM â€” respond immediately in the group (not the DM) via `send_message(target='telegram:World Cup (group)')`.

- Markdown: bullet lists (no tables)
- Concise reporting, flag only actionable moves
- **bold** position names in position summaries
## Pitfalls

- **Cron delivery defaults to DM â€” verify target.** New cron jobs default `deliver='telegram'` (the home DM channel), not the group. When creating or updating cron jobs, explicitly set `deliver='telegram:World Cup (group)'`. Use `cronjob(action='list')` to audit delivery targets periodically â€” a job silently routing to DM means the co-financier misses the output.
- **Telegram `require_mention` must be false for group responsiveness.** By default, Hermes's Telegram integration only processes messages that mention the bot. To respond to all group messages, run: `/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config set telegram.require_mention false`. The bot may also need privacy mode disabled via @BotFather (`/setprivacy` â†’ Disable). The hermes gateway needs a restart to pick up config changes.
- **Hermes CLI location on this host**: `/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe`. It is NOT on PATH and NOT installed via npm globally. The `npx hermes` cache at `node_modules/hermes/bin/hermes` is unreliable (argument-parsing issues). Use the venv-installed binary directly.

- **Never report a price move from memory.** Always fetch the current price from Kalshi (`GET /markets/{ticker}`) before claiming a position has moved. Sessions expire and memory can be stale â€” a false move alert erodes operator trust. If the API returns an error, report the error, not an assumed move.\n- **Position summaries to the user require live fetches.** Any message that includes a current price for an active position must be preceded by a live `GET /markets/{ticker}` call in the same session. Do not carry prices forward from cron output or prior turns â€” the user sees your message and may act on it. If you can't fetch (API down, rate-limited), say so explicitly rather than quoting a possibly-stale price.\n- **Disambiguate when a team has multiple active markets.** Group-stage teams appear in 3+ Kalshi markets (one per group match). If you report "Ecuador at 81Â¢" while the user is looking at a different Ecuador market (CIVECU at 41Â¢), the numbers appear wrong and erode trust. Every position summary must include date + opponent + ticker â€” e.g. "Ecuador (vs CuraÃ§ao, Jun 20 â€” ECUCUW)". Never use team name alone as a price label.
- **Kalshi `with_nested_markets=true` returns null/unreliable fields**: When fetching events with nested markets, `yes_bid`, `yes_ask`, `volume`, `last_price`, AND `liquidity_dollars` are all unreliable from the nested objects. Prices are `null`; `liquidity_dollars` often shows `"0.0000"` even when the orderbook API has substantial depth. The nesting gives tickers and subtitles only. For price data, discover markets via the events endpoint, then fetch prices individually via `GET /markets/{ticker}`. For liquidity, always use the orderbook API (`GET /markets/{ticker}/orderbook`) â€” it is the authoritative liquidity source, not the `liquidity_dollars` field from nested events. See `references/kalshi-api-pagination.md` for the full pagination pattern.
- âš ï¸ **Empty orderbooks on pre-match markets â€” check the book, but small orders can still fill.** Kalshi markets may show `yes_ask`/`yes_bid` prices but return empty yes/no arrays from `GET /markets/{ticker}/orderbook`. **Before betting, always check the orderbook.** An empty-looking book means only indicative prices are visible â€” but **small limit orders at the displayed ask CAN fill immediately** (market maker provides hidden liquidity that doesn't appear as resting orders). Jun 11 session confirmed: two limit orders (10 shares at 23Â¢, 2 shares at 21Â¢) filled instantly despite empty orderbooks. For larger orders (>$5), an empty book is still a warning â€” hidden depth may not extend to larger sizes. Use small-lot limit orders and verify fills. The displayed prices ARE tradeable for small size even with an empty-looking book. The inverse also happens: `liquidity_dollars` may read `"0.0000"` from the events endpoint while the orderbook API shows real resting orders â€” trust the orderbook API, not the field.
- `skill_view` may fail to load plugin-provided skills that appear in the listing â€” fall back to the cron prompt's embedded instructions
- Windows host: terminal runs git-bash (POSIX), not PowerShell. MSYS paths work alongside C:\ paths. `write_file` to `/tmp/foo.py` lands at `C:\tmp\foo.py` â€” use the full Windows path in `terminal()` calls.
- Cron jobs: `execute_code` may be blocked (`approvals.cron_mode` restriction) â€” use `terminal()` with inline python instead. For multi-step scripts, `write_file` the script first, then `terminal("python3 C:/tmp/script.py")`.
- **Auth signature failure (`INCORRECT_API_KEY_SIGNATURE`)**: If the `kalshi_auth.py` script returns headers that Kalshi rejects with 401/INCORRECT_API_KEY_SIGNATURE, try: (1) verify `kalshi_key.pem` exists and is a valid RSA PRIVATE KEY, (2) re-run from the script's own directory (`cd /c/Users/gsche/.hermes/kalshi && python3 kalshi_auth.py ...`), (3) check if the API key (`KALSHI-ACCESS-KEY`) was rotated â€” the key ID is `${KALSHI_API_KEY}` as of Jun 5. The `kalshi_key.pem` at `/c/Users/gsche/.hermes/kalshi/` is the persistent key file (NOT `/tmp`). Do NOT capture this as a permanent "auth is broken" rule â€” it is a diagnostic checklist for transient signature issues.
- **Python terminal() calls cannot read `/c/Users/...` paths**: Python's `open()`, `os.path.exists()`, and subprocess file arguments fail with `/c/Users/...` paths on this Windows git-bash host. Use `C:/Users/gsche/...` (forward-slashed Windows path) instead. Example: `key_file = "C:/Users/gsche/.hermes/kalshi/kalshi_key.pem"` NOT `/c/Users/gsche/.hermes/kalshi/kalshi_key.pem`. This applies to all Python code inside terminal() heredocs and subprocess calls.
- **Order placement is script-only**: every buy/sell goes through `scripts/place_bet.py` â€” it owns the wire format (string `count`/`price`, `client_order_id`, limit type), the rails, and the journal. If an order needs to happen and the script can't do it, fix the script; do not hand-roll a POST.
- **Never ask "Want me to place it?"** â€” operation mode is FULLY AUTONOMOUS. If the research is done and the edge is stateable, place the bet and report the confirmation. If the edge isn't there, state the pass and why. Permission-seeking is a rail violation identical to betting without sources.
- **X data gathering when web tools are down**: `web_search` and `web_extract` require Firecrawl (may be unconfigured). `x_search` (xAI/Grok) works independently â€” both from the parent agent AND from `delegate_task` subagents. Subagents only fail on `web_search`/`web_extract`. Use `delegate_task` with `toolsets: [\"x_search\"]` to fan out parallel X research across multiple matches in one turn. For non-X data (Wikipedia, ESPN, Transfermarkt), use `browser_navigate` + `browser_console` as fallback from the parent â€” subagent browser snapshots are often truncated.
- **Kalshi events endpoint uses `event_ticker`, not `ticker`.** When parsing `GET /events?...` responses, the event-level key is `event_ticker` (e.g. `\"event_ticker\": \"KXWCGROUPQUAL-26F\"`). Accessing `event['ticker']` raises `KeyError`. Markets within events DO use `ticker`. Affects all series-discovery code. Subagents with `toolsets: [\"web\"]` or `[\"browser\"]` cannot reliably fetch eloratings.net because web tools require Firecrawl and browser snapshots are truncated. Elo ratings are stable during tournament periods (no competitive matches between group-stage game days), so the benchmark table in `references/elo-to-fv-manual.md` is the primary fallback. Only re-fetch Elo from the parent's browser if several matchdays have passed or the benchmark table doesn't cover the teams. Never delegate Elo fetching â€” it will fail silently and return no data.
- **Elo data provenance â€” two tiers, two thresholds.** Elo ratings have a quality tier that directly affects confidence: (a) **Benchmark Elo** â€” from the calibrated table in `references/elo-to-fv-manual.md`. Trusted, stable, Dixon-Coles validated. Standard 3Â¢/5Â¢ edge thresholds apply. (b) **X-sourced Elo** â€” approximate rankings or point estimates scraped from X posts. Directional but imprecise (often Â±50 points off). When FV rests on X-sourced Elo, raise the net-edge threshold to **6Â¢** to compensate for the FV-uncertainty. Additionally, an X-sourced Elo-only bet (no injury/form/H2H edge) should pass regardless of computed edge â€” two weak signals don't make a strong one. Example from Jun 12 scan: TUN FV ~28% on X-sourced Elo gave ~5Â¢ net edge vs 22Â¢ ask â†’ passed. JPN FV ~34% on benchmark Elo gave ~6.7Â¢ net edge â†’ bet placed. The Elo source was the deciding factor.
