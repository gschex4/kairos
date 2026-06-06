#!/bin/bash
# Position watch script for cron job.
# Outputs structured data for LLM evaluation.
# Used by: par-position-watch cron job
# Output format: TICKER ask bid vol24

echo "TS=$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
for TICKER in "KXWCGAME-26JUN12USAPAR-PAR" "KXWCGAME-26JUN14CIVECU-ECU" "KXWCGAME-26JUN17GHAPAN-PAN"
do
  DATA=$(curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/$TICKER")
  ASK=$(echo "$DATA" | python3 -c "import sys,json; m=json.load(sys.stdin)['market']; print(m.get('yes_ask_dollars','N/A'),m.get('yes_bid_dollars','N/A'),m.get('volume_24h_fp','0'))")
  echo "$TICKER $ASK"
done