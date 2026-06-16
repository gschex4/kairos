#!/usr/bin/env python3
"""Kairos code-enforced bet placement for Kalshi.

THE ONLY SANCTIONED WAY TO PLACE OR EXIT A POSITION. The agent supplies its
estimate, confidence, reasoning, and sources; THIS SCRIPT decides the size,
enforces every hard rail, journals the decision (placed, dry_run, AND
rejected) to ~/.hermes/logs/bet_journal.jsonl, and places the RSA-signed
order. The agent never picks share counts and never calls
POST /portfolio/events/orders directly.

BUY (conviction bet) — size computed by confidence-scaled Kelly, rails enforced.
  Conviction requires FV >= 0.40 (>= 0.45 for normal edge) — see R7. Example:
  python3 place_bet.py buy --ticker KXWCGAME-26JUN12USAPAR-PAR \
      --price 0.46 --prob 0.55 --confidence 0.7 \
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
  R2 NET edge = prob - price - fee, fee = 0.07*price*(1-price); required edge SCALES
     with FV (favorite-longshot bias): >=0.03 at FV>=0.45 (>=0.05 at FV>=0.70),
     >=0.04 at FV 0.35-0.45, >=0.05 at FV 0.25-0.35, >=0.06 at FV 0.20-0.25
  R3 conviction size = confidence-scaled, FV-SHRUNK Kelly of TOTAL capital (cash +
     WC exposure): fraction = confidence clamped [0.50,0.75], x an FV shrink
     (1.0 >=0.45, 0.75 at .35-.45, 0.55 at .25-.35, 0.40 at .20-.25), applied to
     net edge/(1-price); capped at 20% of total capital, at 6% for sub-0.40 bets,
     and at available cash above the $5 floor
  R4 trade size = --cost, capped at 5% of total capital (cash + WC exposure);
     trades also require price <= 0.15
  R5 confidence floor 0.50; below that, no bet
  R6 minimum cash floor: a buy may not take cash below $5.00
  R7 conviction fair-value FLOOR (graduated, v2): only the DEEP longshot tail is
     banned - prob < 0.20 conviction is FORBIDDEN (--type trade <=15c or PASS).
     From 0.20 up, conviction is ALLOWED but throttled by R2's FV-scaled edge bar
     and R3's FV size shrink. Edge-size/confidence never override the floor.
  R8 speculative-sleeve cap: aggregate OPEN sub-0.40 conviction exposure <= 20% of
     total capital (ruin is a portfolio property). Trades are EXEMPT from R2/R7/R8.
Sells skip R2-R7 (exits are always allowed) but still journal.

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

# R7 v2 (Jun 16 2026) — GRADUATED low-FV control; REPLACES the hard FV<0.40 conviction BAN.
# Research consensus (Kelly / value-CLV / favorite-longshot / guardrail-design / calibration lenses):
# the Paraguay loss was a SIZING + CORRELATION failure, not a selection failure. The hard FV>=0.40 ban
# conflated EXPECTED VALUE with P(win) and banned the exact band (underdog value, FV 0.25-0.40) the
# thesis is built to harvest — it flatlined the bet journal (0 bets in 3 days; 14/23 historical
# convictions retro-banned, incl. ALL 5 match-win bets ever placed). The fix is SIZE DISCIPLINE, not a
# category ban: a deep-tail floor + an FV-scaled size shrink + an FV-scaled min-edge + a per-bet and an
# aggregate "speculative sleeve" exposure cap on sub-0.40 conviction (ruin is a PORTFOLIO property —
# bound it with sizing + an exposure budget, not an outcome-probability ban). A single half-Kelly bet
# at FV~0.37 is then ~$3-6 on a $100 book, not the ~$12 Paraguay lost.
# PROVISIONAL + EVIDENCE-GATED: tune these from floor_audit / draw_audit CLV over ~20-30 settled cases,
# never from one result, in EITHER direction. Genuine Paraguay lessons PRESERVED: edge-size and
# confidence NEVER buy a path past the floor or caps; only a sourced FACT lifts FV; and correlated
# "favorite-won't-win" legs (a draw + that game's underdog) are sized as ONE thesis (agent-enforced).
CONVICTION_FV_FLOOR = 0.20    # FV < this -> conviction FORBIDDEN (deep longshot tail); --type trade (<=15c) or PASS
SPEC_FV_THRESHOLD = 0.40      # "speculative sleeve" = conviction positions entered at FV below this
SPEC_PER_BET_CAP = 0.06       # a single sub-0.40 conviction <= 6% of total capital
SPEC_SLEEVE_CAP = 0.20        # aggregate OPEN sub-0.40 conviction exposure <= 20% of total capital

KELLY_FRACTION_MIN = 0.50
KELLY_FRACTION_MAX = 0.75
FEE_RATE = 0.07  # Kalshi taker fee: 0.07 * price * (1 - price) per contract
MAX_PCT_OF_CAPITAL = 0.20  # global per-bet cap (trimmed from 0.25 — 25% of a small book on ONE bet is the real ruin lever)
TRADE_MAX_PCT_OF_CAPITAL = 0.05
TRADE_MAX_PRICE = 0.15
MIN_CONFIDENCE = 0.50
CASH_FLOOR_DOLLARS = 5.00


def _fv_size_shrink(fv: float) -> float:
    """Low-FV estimates are noisier -> shrink the Kelly stake (encode model risk as SIZE, not a wall)."""
    if fv >= 0.45:
        return 1.00
    if fv >= 0.35:
        return 0.75
    if fv >= 0.25:
        return 0.55
    return 0.40  # 0.20-0.25 (deep but allowed)


def _fv_min_edge(fv: float) -> float:
    """Required NET edge scales with FV: cheap sides fight the favorite-longshot bias, so demand a
    larger mispricing as FV falls. (Trades skip this — they exit on a catalyst, not at resolution.)"""
    if fv >= HIGH_FV:
        return MIN_EDGE_HIGH_FV  # 0.05 at FV>=0.70 (thin edge on an expensive contract)
    if fv >= 0.45:
        return MIN_EDGE          # 0.03
    if fv >= 0.35:
        return 0.04
    if fv >= 0.25:
        return 0.05
    return 0.06                  # 0.20-0.25


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


def _spec_sleeve_exposure(positions: dict) -> float:
    """Sum of current market exposure of OPEN WC positions entered (per the bet journal) at a
    conviction FV < SPEC_FV_THRESHOLD — the 'speculative sleeve'. Best-effort; returns 0.0 if the
    journal is missing. Used by the R8 aggregate cap so many sub-0.40 legs can't become one big bet."""
    entry_fv: dict = {}
    try:
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("status") != "placed":
                continue
            inp = r.get("input", {}) or {}
            if inp.get("side") != "buy" or inp.get("type", "conviction") != "conviction":
                continue
            tk, pr = inp.get("ticker"), inp.get("prob")
            if tk and isinstance(pr, (int, float)):
                entry_fv[tk] = float(pr)  # chronological file -> latest entry wins
    except FileNotFoundError:
        return 0.0
    total = 0.0
    for mp in positions.get("market_positions", []):
        tk = mp.get("ticker", "")
        if not tk.startswith(("KXWC", "KXMENWORLDCUP")):
            continue
        fv = entry_fv.get(tk)
        if fv is not None and fv < SPEC_FV_THRESHOLD:
            total += abs(float(mp.get("market_exposure_dollars", 0) or 0))
    return total


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
        if not (0 < a.prob < 1):
            return _reject(args_dict, "input",
                           f"--prob {a.prob} not in (0,1) — probability must be a fraction, e.g. 0.37")
        # R5 confidence
        if a.confidence < MIN_CONFIDENCE:
            return _reject(args_dict, "R5-confidence", f"confidence {a.confidence} < floor {MIN_CONFIDENCE}")
        # R2/R7 edge — NET of the Kalshi taker fee, so fee-churn never counts as edge
        fee = FEE_RATE * a.price * (1 - a.price)
        edge = a.prob - a.price - fee

        # R7 v2 — only the DEEP longshot tail is forbidden as a hold-to-resolution conviction.
        # Between the floor (0.20) and 0.45 the bet is ALLOWED but throttled: a larger required edge
        # (R2 via _fv_min_edge) and a smaller stake (R3 via _fv_size_shrink). The Paraguay loss was a
        # SIZING failure, not a selection one — a hard FV>=0.40 ban conflated EV with P(win) and banned
        # the underdog-value band where mispricing lives. Edge-size and confidence NEVER override this.
        if a.type == "conviction" and a.prob < CONVICTION_FV_FLOOR:
            return _reject(
                args_dict, "R7-fv-floor",
                f"prob {a.prob:.3f} < {CONVICTION_FV_FLOOR:.2f} deep-longshot floor — too far in the "
                f"favorite-longshot tail to ride to resolution regardless of edge ({edge:.3f}). "
                f"Re-submit as '--type trade --cost X' (price <= {TRADE_MAX_PRICE:.2f}) or PASS.")

        # R2 edge gate (conviction only; trades skip it — priced on catalyst re-rate, not resolution).
        # Required NET edge SCALES with FV: cheap sides fight the favorite-longshot bias, so a bigger
        # mispricing is required as FV falls (the principled replacement for the old flat 8c borderline).
        if a.type == "conviction":
            min_edge = _fv_min_edge(a.prob)
            if edge < min_edge:
                return _reject(args_dict, "R2-edge",
                               f"net edge {edge:.3f} < required {min_edge:.2f} for FV {a.prob:.2f} "
                               f"(price {a.price}, fee {fee:.4f})")

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
            # R3 confidence-scaled, FV-SHRUNK Kelly of TOTAL capital, capped.
            # Low-FV estimates are noisier -> _fv_size_shrink shrinks the stake (size, not a wall).
            kelly_fraction = min(max(a.confidence, KELLY_FRACTION_MIN), KELLY_FRACTION_MAX)
            kelly_pct = kelly_fraction * _fv_size_shrink(a.prob) * edge / (1 - a.price)
            spendable = max(0.0, cash - CASH_FLOOR_DOLLARS)
            per_bet_cap = MAX_PCT_OF_CAPITAL
            if a.prob < SPEC_FV_THRESHOLD:
                per_bet_cap = min(per_bet_cap, SPEC_PER_BET_CAP)  # sub-0.40 single bet capped tighter
            bet_dollars = min(kelly_pct * total_capital,
                              per_bet_cap * total_capital,
                              spendable)
            # R8 speculative-sleeve cap — bound aggregate sub-0.40 conviction exposure as a PORTFOLIO
            # (ruin is a portfolio property; many correlated small dogs must not become one big bet).
            # Best-effort + FAIL-SAFE: any data error only ever SHRINKS or passes the bet, never enlarges it.
            if a.prob < SPEC_FV_THRESHOLD and bet_dollars > 0:
                try:
                    spec_open = _spec_sleeve_exposure(positions)
                    room = SPEC_SLEEVE_CAP * total_capital - spec_open
                    if room <= 0:
                        return _reject(args_dict, "R8-sleeve",
                                       f"sub-0.40 sleeve full: open speculative exposure ${spec_open:.2f} "
                                       f">= {SPEC_SLEEVE_CAP:.0%} of capital "
                                       f"(${SPEC_SLEEVE_CAP * total_capital:.2f}) — PASS.")
                    bet_dollars = min(bet_dollars, room)
                except Exception as exc:  # noqa: BLE001 — sleeve must never block on a data error
                    print(f"WARNING: R8 sleeve check skipped: {exc}", file=sys.stderr)
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
