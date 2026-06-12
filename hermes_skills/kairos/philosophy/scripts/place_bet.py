#!/usr/bin/env python3
"""Kairos code-enforced bet placement for Kalshi.

THE ONLY SANCTIONED WAY TO PLACE OR EXIT A POSITION. The agent supplies its
estimate, confidence, reasoning, and sources; THIS SCRIPT decides the size,
enforces every hard rail, journals the decision (placed, dry_run, AND
rejected) to ~/.hermes/logs/bet_journal.jsonl, and places the RSA-signed
order. The agent never picks share counts and never calls
POST /portfolio/events/orders directly.

BUY (conviction bet) — size computed by confidence-scaled Kelly, rails enforced:
  python3 place_bet.py buy --ticker KXWCGAME-26JUN12USAPAR-PAR \
      --price 0.24 --prob 0.31 --confidence 0.7 \
      --reasoning "one-sentence edge" --sources "url1,url2" [--dry-run]

BUY (re-rate trade, e.g. cheap futures) — sized by dollars at risk:
  python3 place_bet.py buy --type trade --ticker KXMENWORLDCUP-26-CIV \
      --price 0.004 --cost 1.00 --prob 0.02 --confidence 0.5 \
      --reasoning "..." --sources "..." [--dry-run]

SELL (exit / cash-out / trade-ladder tranche) — explicit count required:
  python3 place_bet.py sell --ticker KXMENWORLDCUP-26-CIV \
      --price 0.015 --count 62 --reasoning "trade-exit ladder: +275% tranche" \
      [--dry-run]

Rails enforced in code (buy):
  R1 sources required (non-empty)
  R2 NET edge = prob - price - fee >= 0.03 (>= 0.05 when prob >= 0.70),
     where fee = 0.07 * price * (1 - price) (Kalshi taker fee per contract)
  R3 conviction size = confidence-scaled Kelly of TOTAL capital (cash + WC
     exposure): fraction = confidence clamped to [0.50, 0.75], applied to
     net edge / (1 - price); capped at 25% of total capital and at
     available cash above the $5 floor
  R4 trade size = --cost, capped at 5% of total capital (cash + WC exposure);
     trades also require price <= 0.15
  R5 confidence floor 0.50; below that, no bet
  R6 minimum cash floor: a buy may not take cash below $5.00
Sells skip R2-R6 (exits are always allowed) but still journal.

Event-window and market-velocity kills remain the agent's responsibility
pre-call (they need live match context). Liquidity check: the script warns
when the order book is thin but does not block.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

KALSHI_DIR = r"C:\Users\gsche\.hermes\kalshi"
sys.path.insert(0, KALSHI_DIR)
from kalshi_auth import get_auth_headers  # noqa: E402

BASE = "https://api.elections.kalshi.com"
JOURNAL = Path(r"C:\Users\gsche\.hermes\logs\bet_journal.jsonl")

MIN_EDGE = 0.03
MIN_EDGE_HIGH_FV = 0.05
HIGH_FV = 0.70
KELLY_FRACTION_MIN = 0.50
KELLY_FRACTION_MAX = 0.75
FEE_RATE = 0.07  # Kalshi taker fee: 0.07 * price * (1 - price) per contract
MAX_PCT_OF_CAPITAL = 0.25
TRADE_MAX_PCT_OF_CAPITAL = 0.05
TRADE_MAX_PRICE = 0.15
MIN_CONFIDENCE = 0.50
CASH_FLOOR_DOLLARS = 5.00


def _api(method: str, path: str, body: dict | None = None) -> dict:
    headers = get_auth_headers(method, path)
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} on {method} {path}: {e.read().decode()[:500]}")


def _journal(record: dict) -> None:
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        record["ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record["tool"] = "place_bet.py"
        with JOURNAL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # journaling failure must not mask the result
        print(f"WARNING: journal write failed: {exc}", file=sys.stderr)


def _reject(args_dict: dict, rail: str, detail: str) -> int:
    _journal({"status": "rejected", "rail": rail, "detail": detail, "input": args_dict})
    print(json.dumps({"status": "rejected", "rail": rail, "detail": detail}, indent=2))
    return 0  # rejection is a successful, sanctioned outcome


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("--ticker", required=True)
    p.add_argument("--price", type=float, required=True, help="limit price in dollars, e.g. 0.24")
    p.add_argument("--prob", type=float, default=None, help="estimated probability 0-1 (required for buy)")
    p.add_argument("--confidence", type=float, default=None, help="0-1 (required for buy)")
    p.add_argument("--reasoning", required=True)
    p.add_argument("--sources", default="", help="comma-separated citations (required for buy)")
    p.add_argument("--type", choices=["conviction", "trade"], default="conviction")
    p.add_argument("--cost", type=float, default=None, help="dollars at risk (required for --type trade)")
    p.add_argument("--count", type=int, default=None, help="share count (required for sell)")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    args_dict = vars(a).copy()

    if not (0 < a.price < 1):
        return _reject(args_dict, "input", f"price {a.price} not in (0,1) dollars")

    # ---- balance + exposure (needed for sizing rails) ----
    bal = _api("GET", "/trade-api/v2/portfolio/balance")
    cash = float(bal.get("balance_dollars", bal.get("balance", 0) / 100))
    positions = _api("GET", "/trade-api/v2/portfolio/positions")
    wc_exposure = sum(
        float(ep.get("event_exposure_dollars", 0))
        for ep in positions.get("event_positions", [])
        if ep.get("event_ticker", "").startswith(("KXWC", "KXMENWORLDCUP"))
    )
    total_capital = cash + wc_exposure

    if a.side == "buy":
        # R1 sources
        if not a.sources.strip():
            return _reject(args_dict, "R1-sources", "no sources provided — no source, no bet")
        if a.prob is None or a.confidence is None:
            return _reject(args_dict, "input", "--prob and --confidence are required for buy")
        # R5 confidence
        if a.confidence < MIN_CONFIDENCE:
            return _reject(args_dict, "R5-confidence", f"confidence {a.confidence} < floor {MIN_CONFIDENCE}")
        # R2 edge — NET of the Kalshi taker fee, so fee-churn never counts as edge
        fee = FEE_RATE * a.price * (1 - a.price)
        edge = a.prob - a.price - fee
        min_edge = MIN_EDGE_HIGH_FV if a.prob >= HIGH_FV else MIN_EDGE
        if a.type == "conviction" and edge < min_edge:
            return _reject(args_dict, "R2-edge",
                           f"net edge {edge:.3f} < required {min_edge} "
                           f"(prob {a.prob}, price {a.price}, fee {fee:.4f})")

        # ---- sizing (code decides, not the agent) ----
        if a.type == "trade":
            # R4 trade sizing
            if a.cost is None:
                return _reject(args_dict, "input", "--cost required for --type trade")
            if a.price > TRADE_MAX_PRICE:
                return _reject(args_dict, "R4-trade", f"price {a.price} > trade ceiling {TRADE_MAX_PRICE} — not a cheap re-rate trade")
            cap = total_capital * TRADE_MAX_PCT_OF_CAPITAL
            if a.cost > cap:
                return _reject(args_dict, "R4-trade", f"cost ${a.cost:.2f} > {TRADE_MAX_PCT_OF_CAPITAL:.0%} of capital (${cap:.2f})")
            count = int(a.cost / a.price)
        else:
            # R3 confidence-scaled Kelly of TOTAL capital, capped
            kelly_fraction = min(max(a.confidence, KELLY_FRACTION_MIN), KELLY_FRACTION_MAX)
            kelly_pct = kelly_fraction * edge / (1 - a.price)
            spendable = max(0.0, cash - CASH_FLOOR_DOLLARS)
            bet_dollars = min(kelly_pct * total_capital,
                              MAX_PCT_OF_CAPITAL * total_capital,
                              spendable)
            count = int(round(bet_dollars / a.price))
            if count * a.price > spendable:  # rounding may not breach the cash floor
                count = int(spendable / a.price)
        if count < 1:
            return _reject(args_dict, "sizing", "computed size < 1 share")
        cost = count * a.price
        # R6 cash floor
        if cash - cost < CASH_FLOOR_DOLLARS:
            return _reject(args_dict, "R6-cash-floor", f"buy of ${cost:.2f} would take cash ${cash:.2f} below ${CASH_FLOOR_DOLLARS:.2f} floor")
        order_side = "bid"
    else:
        if a.count is None:
            return _reject(args_dict, "input", "--count required for sell")
        count = a.count
        order_side = "ask"

    # ---- liquidity warning (non-blocking) ----
    liq_note = ""
    try:
        mkt = _api("GET", f"/trade-api/v2/markets/{a.ticker}").get("market", {})
        liq = float(mkt.get("liquidity_dollars") or 0)
        if liq < count * a.price * 2:
            liq_note = f"THIN BOOK: liquidity ${liq:.2f} vs order ${count * a.price:.2f} — consider tranches"
    except Exception as exc:
        liq_note = f"liquidity check failed: {exc}"

    order = {
        "ticker": a.ticker,
        "count": str(count),          # Kalshi Go backend: strings, not numbers
        "side": order_side,
        "type": "limit",
        "price": f"{a.price:.4f}",
        "time_in_force": "good_till_canceled",
        "self_trade_prevention_type": "taker_at_cross",
        "client_order_id": f"kairos-{a.ticker[-12:].lower()}-{int(time.time())}",
    }

    if a.dry_run:
        result = {"status": "dry_run", "order": order, "cash": cash,
                  "wc_exposure": wc_exposure, "liquidity_note": liq_note}
        _journal({"status": "dry_run", "input": args_dict, "result": result})
        print(json.dumps(result, indent=2))
        return 0

    placed = _api("POST", "/trade-api/v2/portfolio/events/orders", order)
    result = {"status": "placed", "order": order, "response": placed,
              "cash_before": cash, "liquidity_note": liq_note}
    _journal({"status": "placed", "input": args_dict, "result": result})
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
