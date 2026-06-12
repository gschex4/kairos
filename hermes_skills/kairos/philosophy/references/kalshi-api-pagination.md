# Kalshi API Pagination Pattern

Reusable Python pattern for fetching all events from a Kalshi series with cursor-based pagination. Copy this into a `write_file` call, then invoke via `terminal()`.

## Template

```python
import json, urllib.request, sys

BASE = "https://api.elections.kalshi.com/trade-api/v2"

def fetch_all_events(series_ticker):
    """Paginate through all events for a series. Returns list of event dicts."""
    all_events = []
    cursor = None
    while True:
        url = f"{BASE}/events?series_ticker={series_ticker}&with_nested_markets=true&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Kairos/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            break
        events = data.get('events', data.get('data', []))
        all_events.extend(events)
        cursor = data.get('cursor')
        if not cursor or len(events) == 0:
            break
    return all_events

# Usage
events = fetch_all_events("KXWCGAME")
print(f"Total events: {len(events)}")
```

## Windows Host Execution

On Windows, `write_file` to `/tmp/foo.py` resolves to `C:\tmp\foo.py`. The `terminal()` tool with `workdir=/tmp` won't find it at `./foo.py`. Use the full path:

```
terminal(command='python3 "C:/tmp/kairos_scan.py"', workdir="/tmp")
```

## Kalshi API Response Format

- Events array lives at `data['events']` (primary key) or `data['data']` (fallback)
- Pagination cursor at `data['cursor']` — `null` or missing means last page
- `limit` max is 200 for the events endpoint
- `with_nested_markets=true` returns markets inline but **prices are null** — see pitfall below

## Key Pitfall: Null Nested Market Prices

When using `with_nested_markets=true`, the nested market objects have `yes_bid`, `yes_ask`, `volume`, and `last_price` all set to `null`. The nesting gives you market tickers and subtitles but NOT prices. For price data, fetch individual markets via `GET /markets/{ticker}` separately after discovering them from the events endpoint.
