#!/usr/bin/env python3
"""Floor audit — is the R7 conviction fair-value floor helping or hurting?

The R7 conviction FV floor (place_bet.py) was added Jun 12 2026 in reaction to a
SINGLE loss (Paraguay: 37% FV, 23c, ridden as conviction, lost). One loss on a
37%-to-win bet is zero evidence the bet was wrong — it should lose 63% of the
time. So the floor is a HYPOTHESIS, not a proven fix. This script makes it
EVIDENCE-gated: it measures, from real outcomes, whether the floor is saving
money or costing it, and refuses to render a verdict on too small a sample
(the very error that motivated it).

Two measurements, conviction bets only (the floor never touches trades):
  1. PLACED, bucketed by FV band -> realized win-rate + net P&L per band.
     Calibration signal: were the low-FV bets Kairos DID place +EV or -EV?
  2. BLOCKED by the floor (rail R7-fv-floor, or R2-edge inside the 0.40-0.45
     borderline band) -> COUNTERFACTUAL: did the side the floor refused
     actually win? Per-contract P&L the floor saved (negative) or cost
     (positive). Positive sum over a real sample => the floor is blocking
     winners => lower/remove it.

Public data only (GET /markets/{ticker}); no auth, read-only. Run from /tmp.
"""
from __future__ import annotations

import json
import urllib.request
from collections import defaultdict
from pathlib import Path

JOURNAL = Path(r"C:\Users\gsche\.hermes\logs\bet_journal.jsonl")
BASE = "https://api.elections.kalshi.com"
FEE_RATE = 0.07                 # same model place_bet.py uses
MIN_N_FOR_VERDICT = 20          # do NOT conclude from a small sample — the whole point

FV_BANDS = [("<0.40 (floor)", 0.0, 0.40), ("0.40-0.45 (border)", 0.40, 0.45),
            ("0.45-0.70 (normal)", 0.45, 0.70), (">=0.70 (high)", 0.70, 1.01)]


def fee_pc(price: float) -> float:
    return FEE_RATE * price * (1 - price)


def band(p: float) -> str:
    for name, lo, hi in FV_BANDS:
        if lo <= p < hi:
            return name
    return "?"


def is_test(inp: dict) -> bool:
    """Exclude boundary-test / dry-run noise so the audit only sees real decisions."""
    s = (inp.get("sources") or "").strip().lower()
    r = (inp.get("reasoning") or "").strip().lower()
    return s in ("", "test", "x", "s") or "test" in r or "boundary" in r


def market_result(ticker: str, cache: dict) -> dict:
    if ticker in cache:
        return cache[ticker]
    try:
        req = urllib.request.Request(
            f"{BASE}/trade-api/v2/markets/{ticker}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            m = json.loads(resp.read()).get("market", {})
        res = (m.get("result") or "").lower()        # "yes" / "no" / ""
        out = {"settled": res in ("yes", "no"), "yes": res == "yes",
               "status": (m.get("status") or "").lower()}
    except Exception as exc:                          # noqa: BLE001
        out = {"settled": False, "yes": False, "status": f"err:{exc}"}
    cache[ticker] = out
    return out


def main() -> int:
    if not JOURNAL.exists():
        print("FLOOR AUDIT: no bet journal yet — nothing to audit.")
        return 0

    placed, blocked = [], []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:                              # noqa: BLE001
            continue
        inp = rec.get("input") or {}
        if inp.get("side") != "buy" or inp.get("type") != "conviction" or is_test(inp):
            continue
        st = rec.get("status")
        if st == "placed":
            placed.append(rec)
        elif st == "rejected" and rec.get("rail") in ("R7-fv-floor", "R2-edge"):
            p = inp.get("prob")
            # Only count rejects the FLOOR caused: R7 always; R2 only in the borderline band.
            if rec.get("rail") == "R7-fv-floor" or (isinstance(p, (int, float)) and 0.40 <= p < 0.45):
                blocked.append(rec)

    cache: dict = {}

    # ---- 1. PLACED conviction bets, realized, by FV band ----
    by_band = defaultdict(lambda: {"n": 0, "settled": 0, "wins": 0, "pnl": 0.0})
    for rec in placed:
        inp, r = rec["input"], (rec.get("result") or {})
        price = float(inp.get("price") or 0)
        prob = float(inp.get("prob") or 0)
        order = (r.get("order") or {})
        resp = (r.get("response") or {})
        try:
            count = int(float(order.get("count") or resp.get("fill_count") or 0))
        except Exception:                              # noqa: BLE001
            count = 0
        avg_fee = float(resp.get("average_fee_paid") or fee_pc(price))
        b = by_band[band(prob)]
        b["n"] += 1
        mk = market_result(inp.get("ticker", ""), cache)
        if mk["settled"]:
            b["settled"] += 1
            payout = 1.0 if mk["yes"] else 0.0
            b["wins"] += 1 if mk["yes"] else 0
            b["pnl"] += count * (payout - price) - avg_fee * count

    # ---- 2. BLOCKED conviction bets, counterfactual ----
    blk = {"n": len(blocked), "settled": 0, "would_win": 0, "pnl_pc": 0.0, "pending": []}
    for rec in blocked:
        inp = rec["input"]
        price = float(inp.get("price") or 0)
        mk = market_result(inp.get("ticker", ""), cache)
        if mk["settled"]:
            blk["settled"] += 1
            payout = 1.0 if mk["yes"] else 0.0
            blk["would_win"] += 1 if mk["yes"] else 0
            blk["pnl_pc"] += (payout - price - fee_pc(price))   # per-contract counterfactual
        else:
            blk["pending"].append(inp.get("ticker", "?"))

    # ---- report ----
    out = ["FLOOR AUDIT (R7 conviction fair-value floor) — is it helping or hurting?", ""]
    out.append("1) PLACED conviction bets by FV band (realized):")
    any_placed = False
    for name, _, _ in FV_BANDS:
        b = by_band.get(name)
        if not b or b["n"] == 0:
            continue
        any_placed = True
        wr = f"{(b['wins']/b['settled']*100):.0f}%" if b["settled"] else "n/a"
        out.append(f"   {name:<20} n={b['n']:<2} settled={b['settled']:<2} "
                   f"winrate={wr:<5} net P&L=${b['pnl']:+.2f}")
    if not any_placed:
        out.append("   (none yet)")

    out.append("")
    out.append(f"2) BLOCKED by the floor (counterfactual): {blk['n']} bet(s) refused, "
               f"{blk['settled']} now settled.")
    if blk["settled"]:
        wr = blk["would_win"] / blk["settled"] * 100
        out.append(f"   Of the settled blocks: {blk['would_win']}/{blk['settled']} "
                   f"would have WON ({wr:.0f}%).")
        out.append(f"   Per-contract counterfactual P&L the floor produced: ${blk['pnl_pc']:+.4f}/contract.")
        out.append(f"   (positive => floor blocked net WINNERS => it is COSTING you; "
                   f"negative => floor blocked net losers => it is SAVING you.)")
    if blk["pending"]:
        out.append(f"   {len(blk['pending'])} blocked bet(s) not yet settled — still accruing evidence.")

    # ---- verdict (sample-size honest) ----
    out.append("")
    if blk["settled"] < MIN_N_FOR_VERDICT:
        out.append(f"VERDICT: INSUFFICIENT DATA ({blk['settled']} settled blocks; need ~{MIN_N_FOR_VERDICT}). "
                   f"Keep the floor as a provisional prior and keep collecting. Do NOT tune from this yet — "
                   f"concluding now would repeat the n=1 error the floor was born from.")
    elif blk["pnl_pc"] > 0.02:
        out.append(f"VERDICT: the floor is COSTING money (${blk['pnl_pc']:+.4f}/contract over "
                   f"{blk['settled']} settled blocks). Consider lowering CONVICTION_FV_FLOOR or the "
                   f"borderline edge — the blocked underdog bets are net +EV.")
    elif blk["pnl_pc"] < -0.02:
        out.append(f"VERDICT: the floor is SAVING money (${blk['pnl_pc']:+.4f}/contract over "
                   f"{blk['settled']} settled blocks). Kairos's sub-0.40 FVs were over-optimistic — keep it.")
    else:
        out.append(f"VERDICT: roughly neutral (${blk['pnl_pc']:+.4f}/contract over {blk['settled']} "
                   f"settled blocks). The floor is mainly a variance/discipline control, not an EV lever.")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
