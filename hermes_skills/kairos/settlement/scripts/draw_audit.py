#!/usr/bin/env python3
"""Draw-edge audit — is there a real, bettable edge in WC draws? (CLV-first)

THE VOLUME FIX: waiting for ~20-30 draws to SETTLE would need ~100+ games (draws
are ~19-25%); the group stage is only ~72 and knockouts don't draw. So this does
not wait for outcomes — it measures CLOSING-LINE VALUE (CLV), the sharp's signal:
for every observed game, did the -TIE price move TOWARD Kairos's draw lean by
kickoff? CLV uses EVERY game (not just the ones that draw), so it converges in
~20-30 GAMES — achievable in a couple weeks of group play.

For each draw observation (draw_observe.py) it pulls:
  - the SETTLED result (did it draw?), and
  - the pre-kickoff CLOSING LINE via the Kalshi candlesticks endpoint
    (price ~2.5h before the market's close_time = before the in-game move),
and reports:
  1. CLV (primary, fast): avg (closing_line - entry_tie_price) + positive-CLV rate.
     Positive => the market repriced toward our draws => the model finds real
     mispricing => edge. This is the signal that unlocks live draw betting.
  2. Realized P&L of the signal-flagged draws (slow confirmation; thin sample).
  3. Calibration: model avg draw_fv vs actual draw rate.

Verdict gates on ~20 games with CLV data (achievable), NOT on settled draws.
Public data only, read-only. Run from /tmp.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

DEFAULT_JOURNAL = r"C:\Users\gsche\.hermes\logs\draw_journal.jsonl"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
FEE_RATE = 0.07
MIN_GAMES_CLV = 20          # games (with a closing line) needed for a CLV verdict
KICKOFF_LOOKBACK_MIN = 150  # closing-line proxy: price ~2.5h before close_time (pre-kickoff)


def _get(url: str):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def _ts(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def market_info(ticker: str, cache: dict) -> dict:
    """Return {settled, drew, close_ts} for a -TIE market (one API call, cached)."""
    if ticker in cache:
        return cache[ticker]
    out = {"settled": False, "drew": False, "close_ts": None}
    try:
        m = _get(f"{BASE}/markets/{ticker}").get("market", {})
        res = (m.get("result") or "").lower()
        out["settled"] = res in ("yes", "no")
        out["drew"] = res == "yes"
        if m.get("close_time"):
            out["close_ts"] = _ts(m["close_time"])
    except Exception:  # noqa: BLE001
        pass
    cache[ticker] = out
    return out


def closing_line(ticker: str, close_ts: int | None, cache: dict) -> float | None:
    """Pre-kickoff -TIE price via candlesticks (~KICKOFF_LOOKBACK_MIN before close)."""
    key = f"cl:{ticker}"
    if key in cache:
        return cache[key]
    out = None
    if close_ts:
        target = close_ts - KICKOFF_LOOKBACK_MIN * 60
        start, end = close_ts - 6 * 3600, close_ts
        try:
            url = (f"{BASE}/series/KXWCGAME/markets/{ticker}/candlesticks"
                   f"?start_ts={start}&end_ts={end}&period_interval=60")
            cands = _get(url).get("candlesticks", [])
            best, best_d = None, 1e18
            for c in cands:
                p = (c.get("price") or {}).get("close_dollars") or (c.get("yes_ask") or {}).get("close_dollars")
                if p is None:
                    continue
                d = abs(int(c["end_period_ts"]) - target)
                if d < best_d:
                    best_d, best = d, float(p)
            out = best
        except Exception:  # noqa: BLE001
            out = None
    cache[key] = out
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", default=DEFAULT_JOURNAL)
    a = ap.parse_args()
    journal = Path(a.journal)
    if not journal.exists():
        print("DRAW AUDIT: no observations yet — nothing to audit.")
        return 0

    # dedup by ticker, keep the EARLIEST observation (the entry furthest from close)
    by_ticker: dict = {}
    for line in journal.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        t = o.get("ticker")
        if not t:
            continue
        if t not in by_ticker or o.get("ts", "") < by_ticker[t].get("ts", ""):
            by_ticker[t] = o
    obs = list(by_ticker.values())

    cache: dict = {}
    clv_vals, flagged, settled = [], [], []
    for o in obs:
        mi = market_info(o["ticker"], cache)
        entry = float(o.get("tie_price", 0))
        cl = closing_line(o["ticker"], mi["close_ts"], cache)
        if cl is not None and entry > 0:
            o["_clv"] = cl - entry
            clv_vals.append(o["_clv"])
        if mi["settled"]:
            o["_drew"] = mi["drew"]
            settled.append(o)
            if o.get("would_bet"):
                flagged.append(o)

    out = ["DRAW AUDIT — is there a bettable edge in WC draws?  (CLV-first)", ""]
    out.append(f"games observed: {len(obs)} | with closing line (CLV): {len(clv_vals)} | settled: {len(settled)}")

    # 1. CLV — the fast, primary signal
    avg_clv = sum(clv_vals) / len(clv_vals) if clv_vals else None
    pos_rate = (sum(1 for v in clv_vals if v > 0) / len(clv_vals) * 100) if clv_vals else None
    if avg_clv is not None:
        out.append(f"CLV (primary): avg {avg_clv*100:+.2f}c/contract over {len(clv_vals)} games | "
                   f"positive-CLV rate {pos_rate:.0f}%")
        out.append("   (positive => the -TIE line moved TOWARD our draw lean by kickoff => the model finds real "
                   "mispricing => edge. This unlocks live draw betting, and converges in ~20-30 GAMES not draws.)")
    else:
        out.append("CLV: no closing lines yet.")

    # 2. realized flagged-draw P&L (slow confirmation)
    if flagged:
        pnl = sum((1.0 if o["_drew"] else 0.0) - float(o["tie_price"])
                  - FEE_RATE * float(o["tie_price"]) * (1 - float(o["tie_price"])) for o in flagged)
        w = sum(1 for o in flagged if o["_drew"])
        out.append(f"realized (confirmation): {len(flagged)} flagged draws settled, {w} drew, "
                   f"P&L ${pnl:+.4f}/contract")

    # 3. calibration
    if settled:
        drew = sum(1 for o in settled if o["_drew"])
        avg_fv = sum(float(o.get("draw_fv", 0)) for o in settled) / len(settled)
        out.append(f"calibration: model avg draw_fv {avg_fv*100:.0f}% vs actual {drew}/{len(settled)}={drew/len(settled)*100:.0f}%")
        md = defaultdict(lambda: [0, 0])
        for o in settled:
            k = o.get("matchday", 0)
            md[k][0] += 1
            md[k][1] += 1 if o["_drew"] else 0
        out.append("by matchday: " + "  ".join(f"MD{k}={md[k][1]}/{md[k][0]}" for k in sorted(md)))

    # verdict — gated on CLV games (achievable), not settled draws
    out.append("")
    if not clv_vals or len(clv_vals) < MIN_GAMES_CLV:
        have = len(clv_vals)
        out.append(f"VERDICT: INSUFFICIENT DATA ({have}/{MIN_GAMES_CLV} games with CLV). Keep OBSERVING — but this "
                   f"now needs ~{MIN_GAMES_CLV} GAMES, not 20-30 draws, so it converges in a couple weeks of group play.")
    elif avg_clv > 0.01:
        out.append(f"VERDICT: POSITIVE CLV ({avg_clv*100:+.2f}c over {len(clv_vals)} games, {pos_rate:.0f}% positive). "
                   f"The model is beating the -TIE close — the draw edge looks REAL. Consider enabling live draw bets "
                   f"(add the 0.25-0.32 draw floor to place_bet.py). Confirm against realized P&L as draws accrue.")
    elif avg_clv < -0.01:
        out.append(f"VERDICT: NEGATIVE CLV ({avg_clv*100:+.2f}c). The market is ahead of the draw model — no edge. "
                   f"Stay in OBSERVE mode / do not enable live draw bets.")
    else:
        out.append(f"VERDICT: FLAT CLV ({avg_clv*100:+.2f}c). The draw model roughly matches the market — no clear edge yet.")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
