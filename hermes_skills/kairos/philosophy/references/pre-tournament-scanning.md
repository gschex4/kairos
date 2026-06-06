# Pre-Tournament & Live Scanning Pattern

The 2026 FIFA World Cup runs **June 11 – July 19, 2026**.
**Markets ARE live on Kalshi before the tournament starts** — this is NOT a reason to skip scanning.

## What EXISTS Before Kickoff (confirmed Jun 5)

| Series | What | Count |
|--------|------|-------|
| KXWCGAME | Group stage match markets | 72 events (216 markets) |
| KXWCSPREAD | Match spread lines | 72 events (288 markets) |
| KXWCTOTAL | Match total goals | 72 events (432 markets) |
| KXWCBTTS | Both teams to score | 72 events (72 markets) |
| KXWC1H | 1st half winner | 72 events |
| KXWCGROUPQUAL | Group qualifier (advance to RO32) | 12 events (48 markets) |
| KXWCGROUPWIN | Group winner | 12 events (48 markets) |
| KXWCROUND | Reach round (RO16 thru Final) | 4 events (192 markets) |
| KXWCSTAGEOFELIM | Team stage of elimination | 48 events (336 markets) |
| KXMENWORLDCUP | Tournament winner | 1 event (48 markets) |
| KXWCAWARD | Awards (Golden Ball, Glove, etc.) | 6 events (239 markets) |
| KXWCGOALLEADER | Golden Boot (top scorer) | 1 event (33 markets) |
| KXWCPLAYERGOALS | Player anytime goalscorer | 47 events (1081 markets) |
| KXWCTEAMLEADGOAL | Team top scorer | 48 events (1153 markets) |
| KXWCTEAM1STGOAL | Team first goalscorer | 48 events (1162 markets) |
| +35 more series | (see full catalog in kalshi-api.md references) | ~7000 total markets |

**Do NOT check ESPN or FIFA.com for match availability** — the Kalshi API is the source of truth for market existence.

## What DOESN'T Exist Yet (Correct)

- **Knockout game tickers** — `KXWCGAME-26{MMMDD}{T1}{T2}` for knockout rounds. These appear only AFTER feeding matches resolve and pairings are known. Do NOT precompute.
- **Golden Boot / Top Scorer futures** — KXWCGOALLEADER exists but may not have all players listed
- **Group order markets** — KXWCGROUPORDER exists with wide spreads, price discovery ongoing

## Pre-Tournament Scanning Behavior

- Markets ARE live — scan them daily
- Liquidity is thinner than match week — flag null books, don't skip the scan
- Cron scans should: discover KXWCGAME for new events → check KXWCROUND for settled/finalized → report any NEW knockout events
- Output [SILENT] only if absolutely nothing changed vs the last scan

## Post-Matchday Scanning (June 11 onward)

1. **After each match group finishes**, re-scan KXWCGAME — new knockout events appear
2. **After group stage ends**, KXWCROUND markets settle for eliminated teams, new KXWCGAME events appear for RO16
3. **Re-run series discovery after EVERY matchday** — do not assume the event list is static
4. The KXWCSTAGEOFELIM series settles in stages as teams get eliminated — monitor for newly finalized markets

## Key Dates

- **Jun 5** — Markets live, pipeline established, first snapshot taken
- **Jun 10** — Start 12-24h pre-match window scanning
- **Jun 11** — Tournament begins (Mexico vs South Africa, opening match)
- **Jun 11 onward** — Full daily scanning with pre-match windows
