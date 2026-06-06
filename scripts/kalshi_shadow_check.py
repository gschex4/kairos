"""Phase 2 shadow validation for the Kalshi code path.

Runs the FULL code-enforced pipeline against LIVE Kalshi markets in DRY_RUN:
real RSA-signed auth (balance), real discovery, real prices, real trade-history
velocity, real sizing — but places NO orders. Validates that kalshi_client /
kalshi_tool parsing matches Kalshi's live API responses (what the offline smoke
test cannot cover).

READ-ONLY. No orders. Safe to re-run. Hard-aborts unless DRY_RUN is true.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Make `src` importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Resolve credentials WITHOUT putting them in any command line.
LIVE_KEY = Path(r"C:\Users\gsche\.hermes\skills\kairos\kairos-philosophy\references\kalshi_key.pem")
LIVE_AUTH = Path(r"C:\Users\gsche\.hermes\skills\kairos\kairos-philosophy\references\kalshi_auth.py")
if not os.environ.get("KALSHI_API_KEY"):
    try:
        m = re.search(r'KALSHI-ACCESS-KEY"\s*:\s*"([0-9a-fA-F-]{36})"', LIVE_AUTH.read_text())
        if m:
            os.environ["KALSHI_API_KEY"] = m.group(1)
    except Exception:
        pass
os.environ.setdefault("KALSHI_KEY_PATH", str(LIVE_KEY))
os.environ["KAIROS_DRY_RUN"] = "true"  # SHADOW — never place orders

from src.config import Config  # noqa: E402
from src.kalshi_tool import KalshiTool  # noqa: E402
from src.polymarket_tool import BetIntent  # noqa: E402
from src.market_velocity import compute_velocity  # noqa: E402


def _mask(s: str) -> str:
    return f"present(len={len(s)})" if s else "MISSING"


def main() -> int:
    print("=== Kalshi shadow validation (DRY_RUN, read-only, NO orders) ===")
    cfg = Config.load(require_wallet=False)
    print(f"dry_run={cfg.dry_run}  KALSHI_API_KEY={_mask(cfg.kalshi_api_key)}  key_path={cfg.kalshi_key_path}")
    if not cfg.dry_run:
        print("ABORT: dry_run is not true — refusing to run a check that could place orders.")
        return 1

    tool = KalshiTool(cfg)
    client = tool._get_client()
    checks: dict[str, bool] = {}

    # 1. AUTH + balance — validates RSA-PSS signing end-to-end
    print("\n[1] AUTH / balance (signed request)...")
    try:
        bal = client.get_balance()
        print(f"    raw balance response: {bal}")
        usd = None
        if isinstance(bal, dict) and bal.get("balance") is not None:
            usd = float(bal["balance"]) / 100.0
        print(f"    -> parsed bankroll: ${usd}")
        checks["auth_balance"] = usd is not None
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        checks["auth_balance"] = False

    # 2. Discovery — find a market with a live yes_ask
    print("\n[2] Discovery (locate a liquid market)...")
    liquid_ticker = None
    liquid_ask = None
    for series in ("KXMENWORLDCUP", "KXWCGROUPQUAL", "KXWCROUND"):
        try:
            data = client.get_public("/events", params={"series_ticker": series,
                                                         "with_nested_markets": "true", "limit": 50})
            events = data.get("events", []) if isinstance(data, dict) else []
            for ev in events:
                for m in ev.get("markets", []) or []:
                    ya = m.get("yes_ask_dollars")
                    if ya in (None, "", "0", "0.0000"):
                        continue
                    try:
                        a = float(ya)
                    except (TypeError, ValueError):
                        continue
                    if 0 < a < 1:
                        liquid_ticker, liquid_ask = m.get("ticker"), a
                        break
                if liquid_ticker:
                    break
        except Exception as e:
            print(f"    {series}: {type(e).__name__}: {e}")
        if liquid_ticker:
            print(f"    found: {liquid_ticker} @ yes_ask {liquid_ask}  (series {series})")
            break
    checks["discovery"] = liquid_ticker is not None
    if not liquid_ticker:
        print("    FAIL: no liquid market found (markets may be thin pre-tournament)")
        _summary(checks)
        return 1

    # 3. Price parse
    print("\n[3] Market price parse...")
    try:
        p = tool.get_market_price(liquid_ticker)
        print(f"    {p}")
        checks["price_parse"] = p.get("yes_ask") is not None
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {e}")
        checks["price_parse"] = False

    # 4. Trade-history fetch + velocity parse
    print("\n[4] Trade-history fetch + velocity parse...")
    try:
        trades = tool._fetch_recent_trades(liquid_ticker, lookback_seconds=3600)
        print(f"    parsed {len(trades)} trades (last hour)")
        if trades:
            print(f"    newest: t={trades[-1].timestamp.isoformat()} price={trades[-1].price} size={trades[-1].size}")
        reading = compute_velocity(trades, token_id=liquid_ticker, source="live")
        print(f"    velocity: has_data={reading.has_market_data} samples={reading.samples_count} "
              f"pct_30s={reading.pct_change_30s} jump_60s={reading.largest_jump_60s}")
        checks["trade_parse"] = True  # parsing didn't crash; sparse pre-tournament trades are expected
    except Exception as e:
        import traceback
        traceback.print_exc()
        checks["trade_parse"] = False

    # 5. FULL place_bet() dry-run against the real market — NO order sent
    print("\n[5] Full place_bet() dry-run on the real market (NO order)...")
    try:
        intent = BetIntent(
            market_question=f"shadow-check {liquid_ticker}",
            condition_id="shadow",
            token_id=liquid_ticker,
            side="BUY",
            price=liquid_ask,
            estimated_probability=min(0.98, liquid_ask + 0.06),  # synthetic +6c edge
            confidence=0.80,
            reasoning="shadow validation: synthetic edge to exercise the full sizing + rail pipeline against live Kalshi data.",
            sources=["https://example.com/shadow-validation"],
            allow_duplicate=True,  # re-runnable; do not let the position guard block a re-check
        )
        res = tool.place_bet(intent)
        print(f"    status={res['status']}  size_usd=${res.get('size_usd')}")
        print(f"    velocity_audit={intent.velocity_audit}")
        print(f"    sizing_audit={intent.sizing_audit}")
        checks["dry_run_bet"] = res.get("status") == "dry_run"
    except Exception as e:
        import traceback
        traceback.print_exc()
        checks["dry_run_bet"] = False

    _summary(checks)
    return 0 if (checks.get("auth_balance") and checks.get("dry_run_bet")
                 and all(checks.values())) else 1


def _summary(checks: dict[str, bool]) -> None:
    print("\n=== SHADOW SUMMARY ===")
    for k, v in checks.items():
        print(f"  {'OK  ' if v else 'FAIL'}  {k}")
    allg = bool(checks) and all(checks.values())
    print("\n" + ("ALL GREEN — code path validated with real Kalshi data."
                  if allg else "NEEDS ATTENTION — see failures above."))


if __name__ == "__main__":
    sys.exit(main())
