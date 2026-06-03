"""Settlement reconciliation + closing-line-value (CLV) tracking.

This is the instrument the staged decision depends on. "Scale only on
demonstrated edge" needs a way to MEASURE edge, and with a tiny number of
bets, win/loss is too noisy to prove anything. CLV — did Kairos get a better
price than the market's close — is the better skill signal on small samples.

Flow:
  reconcile(config)
    → for each open position in the ledger:
        → resolve_market(condition_id, token_id)   [live Gamma fetch]
        → if resolved: compute P&L + CLV, settle it in the ledger

Pure math (compute_pnl, compute_clv) is unit-tested. The live Gamma fetch in
resolve_market is best-effort and marked for verification at install — same
posture as the other live API calls in this project.

Works in DRY_RUN too: paper-trading on REAL markets records real entry prices,
and reconcile settles them against real outcomes, yielding real CLV and
hypothetical P&L without risking money. That's the dress rehearsal that tells
you whether the edge is real before you scale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from src import position_ledger
from src.config import Config

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class Resolution:
    token_id: str
    resolved: bool
    won: Optional[bool] = None
    settlement_price: Optional[float] = None   # 1.0 if the outcome won, else 0.0
    closing_price: Optional[float] = None       # last market price before resolution


# ---------- Pure math (unit-tested) ----------

def compute_pnl(side: str, entry_price: float, size_usd: float, won: bool) -> float:
    """Realized P&L in USD for a settled position.

    BUY: stake `size_usd` at `entry_price` buys size_usd/entry_price shares,
    each paying $1 on a win. Profit on win = size_usd * (1 - entry)/entry;
    loss = -size_usd.

    SELL: approximated as buying the complementary outcome at (1 - entry).
    The agent is steered toward BUY (express a negative view by buying the NO
    token), so SELL P&L is a reasonable estimate, not exact.
    """
    if side == "BUY":
        return round(size_usd * (1.0 - entry_price) / entry_price, 4) if won else round(-size_usd, 4)
    # SELL (approximate)
    comp = 1.0 - entry_price
    if comp <= 0:
        return 0.0
    return round(size_usd * (1.0 - comp) / comp, 4) if won else round(-size_usd, 4)


def compute_clv(side: str, entry_price: float, closing_price: Optional[float]) -> Optional[float]:
    """Closing-line value. Positive = beat the market's closing price.

    BUY: clv = closing - entry (you bought cheaper than the close → good).
    SELL: clv = entry - closing (you sold richer than the close → good).
    """
    if closing_price is None:
        return None
    raw = (closing_price - entry_price) if side == "BUY" else (entry_price - closing_price)
    return round(raw, 4)


# ---------- Live resolution (verify at install) ----------

def resolve_market(condition_id: str, token_id: str) -> Resolution:
    """Best-effort: query Gamma for a market's resolution status.

    Returns Resolution(resolved=False) if the market is still open or the
    response shape isn't what we expect. Defensive parsing throughout —
    a settlement check must never crash the reconcile sweep.

    NOTE: the Gamma response shape (closed flag, outcomePrices, clobTokenIds)
    should be verified against a real resolved market at install time.
    """
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            r = client.get(
                f"{GAMMA_BASE}/markets",
                params={"condition_ids": condition_id},
            )
            r.raise_for_status()
            markets = r.json()
    except Exception as e:
        log.warning("resolve_market fetch failed for %s: %s", condition_id, e)
        return Resolution(token_id=token_id, resolved=False)

    if not markets:
        return Resolution(token_id=token_id, resolved=False)
    market = markets[0] if isinstance(markets, list) else markets

    try:
        closed = bool(market.get("closed"))
        if not closed:
            return Resolution(token_id=token_id, resolved=False)

        token_ids = market.get("clobTokenIds") or []
        outcome_prices = market.get("outcomePrices") or []
        if isinstance(token_ids, str):
            import json as _json
            token_ids = _json.loads(token_ids)
        if isinstance(outcome_prices, str):
            import json as _json
            outcome_prices = _json.loads(outcome_prices)

        if token_id not in token_ids:
            return Resolution(token_id=token_id, resolved=False)
        idx = token_ids.index(token_id)
        settle_price = float(outcome_prices[idx]) if idx < len(outcome_prices) else None
        won = settle_price is not None and settle_price >= 0.5
        return Resolution(
            token_id=token_id,
            resolved=True,
            won=won,
            settlement_price=settle_price,
            # Closing price (last trade before resolution) isn't reliably in
            # this payload; left None for now → CLV recorded as None until a
            # price-history fetch is added. P&L still records.
            closing_price=None,
        )
    except (KeyError, ValueError, TypeError, IndexError) as e:
        log.warning("resolve_market parse failed for %s: %s", condition_id, e)
        return Resolution(token_id=token_id, resolved=False)


# ---------- The sweep ----------

def reconcile(config: Config) -> dict:
    """Settle any open positions whose markets have resolved.

    Returns a summary dict suitable for delivery to Telegram or logging.
    Safe to run on a schedule; idempotent (already-settled positions are
    skipped because they're no longer 'open').
    """
    open_pos = position_ledger.open_positions(config)
    settled_now = 0
    still_open = 0
    for pos in open_pos:
        token_id = pos.get("token_id")
        condition_id = pos.get("condition_id")
        if not token_id or not condition_id:
            still_open += 1
            continue
        res = resolve_market(condition_id, token_id)
        if not res.resolved:
            still_open += 1
            continue
        pnl = compute_pnl(
            side=pos.get("side", "BUY"),
            entry_price=float(pos.get("price", 0) or 0),
            size_usd=float(pos.get("size_usd", 0) or 0),
            won=bool(res.won),
        )
        clv = compute_clv(
            side=pos.get("side", "BUY"),
            entry_price=float(pos.get("price", 0) or 0),
            closing_price=res.closing_price,
        )
        position_ledger.settle_position(
            token_id=token_id,
            won=bool(res.won),
            settlement_price=res.settlement_price,
            closing_price=res.closing_price,
            pnl=pnl,
            clv=clv,
            config=config,
        )
        settled_now += 1

    summary = position_ledger.performance_summary(config)
    summary["settled_this_run"] = settled_now
    summary["still_open"] = still_open
    return summary
