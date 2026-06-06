#!/bin/bash
# futures_watch.sh — Weekly snapshot of futures/props/awards markets
# Fetches prices on tournament winner, golden boot, awards, group qualifiers
# Outputs structured data for cron agent to evaluate
# Usage: bash scripts/futures_watch.sh
# Designed for cron — no side effects, outputs to stdout

BASE="https://api.elections.kalshi.com/trade-api/v2"

echo "=== FUTURES WATCH $(date -u +'%Y-%m-%dT%H:%M:%SZ') ==="

# 1. Tournament Winner — KXMENWORLDCUP
echo "--- KXMENWORLDCUP ---"
curl -s "$BASE/events?series_ticker=KXMENWORLDCUP&with_nested_markets=true" | python3 -c '
import sys, json
data = json.load(sys.stdin)
if "events" in data and len(data["events"]) > 0:
    ev = data["events"][0]
    print(f"Event: {ev.get("title", "")} | Status: {ev.get("status", "")}")
    for m in ev.get("markets", []):
        t = m.get("title", "")
        yb = m.get("yes_bid_dollars", None)
        ya = m.get("yes_ask_dollars", None)
        lp = m.get("last_price_dollars", None)
        v = m.get("volume", 0)
        if yb is not None:
            print(f"{t} | Bid:{yb} Ask:{ya} Last:{lp} Vol:{v}")
else:
    print("No data")
'

# 2. Golden Boot — KXWCGOALLEADER
echo "--- KXWCGOALLEADER ---"
curl -s "$BASE/events?series_ticker=KXWCGOALLEADER&with_nested_markets=true" | python3 -c '
import sys, json
data = json.load(sys.stdin)
for ev in data.get("events", []):
    for m in ev.get("markets", []):
        t = m.get("title", m.get("sub_title", ""))
        yb = m.get("yes_bid_dollars", None)
        ya = m.get("yes_ask_dollars", None)
        v = m.get("volume", 0)
        if yb is not None:
            print(f"{t} | Bid:{yb} Ask:{ya} Vol:{v}")
'

# 3. Awards — KXWCAWARD (top 15 by volume per event)
echo "--- KXWCAWARD ---"
curl -s "$BASE/events?series_ticker=KXWCAWARD&with_nested_markets=true&limit=100" | python3 -c '
import sys, json
data = json.load(sys.stdin)
for ev in data.get("events", []):
    ev_title = ev.get("title", ev.get("sub_title", "Unknown"))
    markets = [m for m in ev.get("markets", [])]
    markets.sort(key=lambda m: m.get("volume", 0) or 0, reverse=True)
    for m in markets[:15]:
        t = m.get("title", "")
        yb = m.get("yes_bid_dollars", None)
        ya = m.get("yes_ask_dollars", None)
        lp = m.get("last_price_dollars", None)
        v = m.get("volume", 0)
        if yb is not None:
            print(f"{ev_title} / {t} | Bid:{yb} Ask:{ya} Last:{lp} Vol:{v}")
'

# 4. Group Qualifiers — KXWCGROUPQUAL
echo "--- KXWCGROUPQUAL ---"
curl -s "$BASE/events?series_ticker=KXWCGROUPQUAL&with_nested_markets=true" | python3 -c '
import sys, json
data = json.load(sys.stdin)
for ev in data.get("events", []):
    for m in ev.get("markets", []):
        t = m.get("title", m.get("sub_title", ""))
        yb = m.get("yes_bid_dollars", None)
        ya = m.get("yes_ask_dollars", None)
        lp = m.get("last_price_dollars", None)
        v = m.get("volume", 0)
        if yb is not None:
            print(f"{t} | Bid:{yb} Ask:{ya} Last:{lp} Vol:{v}")
'

echo "=== END FUTURES WATCH ==="
