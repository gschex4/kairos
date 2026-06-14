#!/usr/bin/env python3
"""Log a draw (TIE) observation for the draw-edge instrument — OBSERVE mode.

Kairos is in OBSERVE mode on draws (added Jun 14 2026, after the WC-2026 draw
analysis). It PRICES the `-TIE` market for every game it scans and logs the
observation here; it does NOT place live draw bets yet. Live draw betting turns
on only when draw_audit.py shows a real edge over ~20-30 settled observations —
the same instrument-before-sizing discipline as floor_audit. (Belt-and-braces:
even if a draw bet were submitted to place_bet.py, the R7 floor blocks it, since
draws price ~0.25-0.32 < the 0.40 conviction floor.)

Usage (terminal, workdir=/tmp):
  python3 draw_observe.py --ticker KXWCGAME-26JUN14NEDJPN-TIE \
      --draw-fv 0.28 --tie-price 0.24 --matchday 1 \
      --signals "defensive-underdog,depleted-favorite,heat" \
      --reasoning "JPN low-block; NED missing key creator; hot afternoon venue"

Appends a JSON line to ~/.hermes/logs/draw_journal.jsonl. draw_audit.py reconciles
it against Kalshi settled outcomes to measure model calibration + counterfactual edge.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

JOURNAL = Path(r"C:\Users\gsche\.hermes\logs\draw_journal.jsonl")
FEE_RATE = 0.07
MIN_EDGE = 0.03  # net edge to flag a draw as would-bet


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True, help="the -TIE market ticker")
    p.add_argument("--draw-fv", type=float, required=True, help="model draw probability 0-1 (Poisson)")
    p.add_argument("--tie-price", type=float, required=True, help="TIE yes_ask in dollars")
    p.add_argument("--matchday", type=int, default=0)
    p.add_argument("--signals", default="", help="comma-separated draw signals that fired")
    p.add_argument("--reasoning", default="")
    a = p.parse_args()

    if "TIE" not in a.ticker.upper():
        print(json.dumps({"status": "rejected", "detail": f"{a.ticker} is not a -TIE market"}))
        return 0
    if not (0 < a.draw_fv < 1) or not (0 < a.tie_price < 1):
        print(json.dumps({"status": "rejected", "detail": "draw_fv/tie_price must be in (0,1)"}))
        return 0

    fee = FEE_RATE * a.tie_price * (1 - a.tie_price)
    edge = a.draw_fv - a.tie_price - fee
    sigs = [s.strip() for s in a.signals.split(",") if s.strip()]
    # OBSERVE-mode would-bet gate (the always-on checklist from the draw analysis):
    # a structurally defensive underdog is near-necessary, plus >=1 more signal, plus positive net edge.
    has_def = any(("defensive" in s.lower() or "underdog" in s.lower() or "low-block" in s.lower()) for s in sigs)
    would_bet = edge >= MIN_EDGE and has_def and len(sigs) >= 2

    rec = {
        "ticker": a.ticker, "draw_fv": a.draw_fv, "tie_price": a.tie_price,
        "net_edge": round(edge, 4), "matchday": a.matchday, "signals": sigs,
        "would_bet": would_bet, "reasoning": a.reasoning,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "observed", "net_edge": round(edge, 4), "would_bet": would_bet}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
