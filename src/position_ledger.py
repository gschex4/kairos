"""File-based position ledger — double-bet protection across stateless sessions.

Hermes cron sessions start fresh with no memory of prior runs. The philosophy
says "one entry per market per decision window." An in-memory guard can't
enforce that across separate cron invocations. This ledger persists to disk
(logs/_positions.json), so a bet placed by the 4pm cron is visible to the 8pm
cron.

This is a guard, not a settlement system. It records what Kairos has acted on
so it doesn't act twice. It does NOT track P&L or settle positions — that's a
separate concern (see the remediation plan).

IMPORTANT: this file is runtime state and is gitignored. It must NOT travel
from the Mac to the PC, or the PC would think it holds positions the Mac
recorded. Each machine maintains its own ledger.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Config
    from src.polymarket_tool import BetIntent

LEDGER_FILENAME = "_positions.json"


def _ledger_path(config: "Config") -> Path:
    return config.log_dir / LEDGER_FILENAME


def _load(config: "Config") -> dict:
    path = _ledger_path(config)
    if not path.exists():
        return {"positions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "positions" not in data:
            return {"positions": []}
        return data
    except (json.JSONDecodeError, OSError):
        # A corrupt ledger should not crash a bet decision. Treat as empty,
        # which fails toward "allow the bet" — acceptable because the worst
        # case is one duplicate, not a runaway loop. The kill log will show it.
        return {"positions": []}


def has_open_position(intent: "BetIntent", config: "Config") -> bool:
    """True if we already hold a non-settled position on this token_id."""
    data = _load(config)
    for pos in data.get("positions", []):
        if pos.get("token_id") == intent.token_id and pos.get("status") == "open":
            return True
    return False


def open_positions(config: "Config") -> list[dict]:
    """Return all positions still marked open (for the settlement sweep)."""
    return [p for p in _load(config).get("positions", []) if p.get("status") == "open"]


def settle_position(
    token_id: str,
    won: bool,
    settlement_price: float | None,
    closing_price: float | None,
    pnl: float | None,
    clv: float | None,
    config: "Config",
) -> int:
    """Mark open positions on a token as settled and record the outcome.

    P&L and CLV are computed by the settlement module and passed in here so
    this module stays a pure store (no circular dependency on settlement).
    Returns the number of positions updated.
    """
    data = _load(config)
    n = 0
    for pos in data.get("positions", []):
        if pos.get("token_id") == token_id and pos.get("status") == "open":
            pos["status"] = "settled"
            pos["won"] = won
            pos["settlement_price"] = settlement_price
            pos["closing_price"] = closing_price
            pos["pnl_usd"] = pnl
            pos["clv"] = clv
            n += 1
    if n:
        _ledger_path(config).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return n


def performance_summary(config: "Config") -> dict:
    """Aggregate settled positions into the edge instrument.

    On a small sample, win rate is noisy. Closing-line value (CLV) is the
    better skill signal: positive avg CLV means Kairos is consistently
    getting better prices than the market's close, which is what justifies
    scaling the bankroll. This is the number the staged decision hangs on.
    """
    positions = _load(config).get("positions", [])
    settled = [p for p in positions if p.get("status") == "settled"]
    open_count = sum(1 for p in positions if p.get("status") == "open")

    wins = sum(1 for p in settled if p.get("won"))
    losses = sum(1 for p in settled if p.get("won") is False)
    total_staked = sum(float(p.get("size_usd") or 0) for p in settled)
    net_pnl = sum(float(p.get("pnl_usd") or 0) for p in settled)
    clvs = [float(p["clv"]) for p in settled if p.get("clv") is not None]
    avg_clv = sum(clvs) / len(clvs) if clvs else None
    positive_clv_rate = (
        sum(1 for c in clvs if c > 0) / len(clvs) if clvs else None
    )

    return {
        "settled_count": len(settled),
        "open_count": open_count,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(settled), 3) if settled else None,
        "total_staked_usd": round(total_staked, 2),
        "net_pnl_usd": round(net_pnl, 2),
        "roi": round(net_pnl / total_staked, 3) if total_staked > 0 else None,
        "avg_clv": round(avg_clv, 4) if avg_clv is not None else None,
        "positive_clv_rate": (
            round(positive_clv_rate, 3) if positive_clv_rate is not None else None
        ),
        "clv_sample_size": len(clvs),
    }


def record_position(intent: "BetIntent", status: str, config: "Config") -> None:
    """Append a placed/dry-run bet to the ledger as an open position."""
    config.log_dir.mkdir(parents=True, exist_ok=True)
    data = _load(config)
    data["positions"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_question": intent.market_question,
            "condition_id": intent.condition_id,
            "token_id": intent.token_id,
            "side": intent.side,
            "price": intent.price,
            "size_usd": intent.computed_size_usd,
            # Both placed and dry_run count as "open" so the guard fires in
            # paper trading too — you want to SEE it prevent a double-bet
            # before real money is involved.
            "status": "open",
            "dry_run": config.dry_run,
        }
    )
    _ledger_path(config).write_text(json.dumps(data, indent=2), encoding="utf-8")


def mark_settled(token_id: str, config: "Config") -> int:
    """Mark all open positions on a token as settled. Returns count updated.

    Not called automatically yet — settlement reconciliation is a separate
    remediation item. Exposed so a future settlement job can free a market
    for re-entry once it resolves.
    """
    data = _load(config)
    n = 0
    for pos in data.get("positions", []):
        if pos.get("token_id") == token_id and pos.get("status") == "open":
            pos["status"] = "settled"
            n += 1
    if n:
        _ledger_path(config).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return n


def reset(config: "Config") -> None:
    """Delete the ledger. Used by the smoke test for a clean slate."""
    path = _ledger_path(config)
    if path.exists():
        path.unlink()
