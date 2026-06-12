#!/usr/bin/env python3
"""Pull Kalshi balance + positions + settlements with RSA-signed auth.
Outputs one JSON blob to stdout. Run via terminal(workdir=/tmp)."""
import json, sys, time, urllib.request, os

# ── Auth (Windows-safe: import from the canonical kalshi dir) ──
KALSHI_DIR = r"C:\Users\gsche\.hermes\kalshi"
sys.path.insert(0, KALSHI_DIR)
from kalshi_auth import get_auth_headers

BASE = "https://api.elections.kalshi.com"

def fetch(path, method="GET"):
    headers = get_auth_headers(method, path)
    req = urllib.request.Request(f"{BASE}{path}", headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}

results = {}
results["balance"]     = fetch("/trade-api/v2/portfolio/balance")
results["positions"]   = fetch("/trade-api/v2/portfolio/positions")
results["settlements"] = fetch("/trade-api/v2/portfolio/settlements")

print(json.dumps(results, indent=2))
