#!/usr/bin/env python3
"""Fetch current prices for given Kalshi market tickers. Pipe tickers via stdin (one per line).
Outputs JSON per market. Run via terminal(workdir=/tmp)."""
import json, sys, urllib.request, os

KALSHI_DIR = r"C:\Users\gsche\.hermes\kalshi"
sys.path.insert(0, KALSHI_DIR)
from kalshi_auth import get_auth_headers

BASE = "https://api.elections.kalshi.com"

tickers = [line.strip() for line in sys.stdin if line.strip()]

for t in tickers:
    headers = get_auth_headers("GET", f"/trade-api/v2/markets/{t}")
    req = urllib.request.Request(f"{BASE}/trade-api/v2/markets/{t}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        data = {"error": str(e)}
    print(json.dumps({"ticker": t, "data": data}, indent=2))
    print("---")
