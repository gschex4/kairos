"""Kalshi tool wrapper — the code-enforced betting path for Kalshi.

Mirrors src/polymarket_tool.py rail-for-rail, enforcing the SAME safety stack
but against the Kalshi trade-api/v2 instead of Polymarket CLOB:

  1. Basic hard rails (shape + sources/reasoning required).
  2. Position guard (one entry per market per window) — shared file ledger.
  3. Code-enforced event-window + market-velocity kill rails.
  4. Confidence-tiered half-Kelly sizing under the milestone floors + 10% cap.
  5. Exotic-market halving + net-of-cost guard.
  6. Defense-in-depth absolute ceiling.
  7. DRY_RUN mode that logs the intended bet but sends no order.

The platform-agnostic core is reused UNCHANGED: src/sizing.py,
src/market_velocity.py, src/position_ledger.py, src/logging_setup.py. The only
Kalshi-specific code is the API I/O in src/kalshi_client.py and the price /
balance / trade / order adapters here.

The agent calls place_bet(intent: BetIntent) where `intent.token_id` is the
Kalshi MARKET TICKER (e.g. "KXWCGAME-26JUN12USAPAR-PAR") and `intent.condition_id`
is the event ticker. Same interface as PolymarketTool, so the plugin layer is a
drop-in repoint. side BUY -> Kalshi "bid" (buy YES); SELL -> "ask" (sell YES).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from src.config import Config
from src.kalshi_client import KalshiClient
from src.logging_setup import log_bet_decision, log_kill_decision
from src.market_velocity import (
    Trade,
    VelocityReading,
    compute_velocity,
    velocity_from_agent_intent,
)
# Reuse the proven intent dataclass + rejection exception verbatim.
from src.polymarket_tool import BetIntent, BetRejected
from src.position_ledger import has_open_position, record_position
from src.sizing import SizingError, SizingResult, compute_size


def _to_float(v) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


class KalshiTool:
    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[KalshiClient] = None

    def _get_client(self) -> KalshiClient:
        if self._client is None:
            self._client = KalshiClient(
                api_key=self.config.kalshi_api_key,
                key_path=self.config.kalshi_key_path,
            )
        return self._client

    # ---------- read methods (no money moves) ----------

    def get_market_price(self, ticker: str) -> dict:
        m = self._get_client().get_market(ticker)
        return {
            "ticker": ticker,
            "yes_ask": _to_float(m.get("yes_ask_dollars")),
            "yes_bid": _to_float(m.get("yes_bid_dollars")),
            "last": _to_float(m.get("last_price_dollars")),
            "status": m.get("status"),
        }

    def get_bankroll_usd(self) -> float:
        """Current bankroll in USD. DRY_RUN -> config value; live -> Kalshi balance.

        Kalshi /portfolio/balance reports cents (e.g. balance=5019 -> $50.19).
        Defensive: any failure falls back to the dry-run bankroll rather than
        crashing the rail chain.
        """
        if self.config.dry_run:
            return self.config.dry_run_bankroll_usd
        try:
            bal = self._get_client().get_balance()
            if isinstance(bal, dict):
                # Prefer the precise dollars string; fall back to integer cents.
                bd = bal.get("balance_dollars")
                if bd is not None:
                    return float(bd)
                raw = bal.get("balance")
                if raw is None:
                    raw = bal.get("available_balance") or bal.get("cash")
                if raw is not None:
                    return float(raw) / 100.0
            return self.config.dry_run_bankroll_usd
        except Exception:
            return self.config.dry_run_bankroll_usd

    def _fetch_recent_trades(self, ticker: str, lookback_seconds: int = 60) -> list[Trade]:
        """Public recent trades on a Kalshi market -> Trade objects (oldest-first).

        Kalshi trade prices are integer cents (yes_price 1..99); convert to the
        0..1 'dollar' convention the velocity module expects. Defensive parsing:
        a bad trade is skipped; total failure yields [] ('no data' -> no false
        kill for pre-match, fail-closed for in-play).
        """
        raw = self._get_client().get_recent_trades(ticker, limit=200)
        out: list[Trade] = []
        for t in raw or []:
            try:
                ts_raw = t.get("created_time") or t.get("created_at") or t.get("ts")
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                elif isinstance(ts_raw, (int, float)):
                    secs = ts_raw / 1000 if ts_raw > 1e12 else ts_raw
                    ts = datetime.fromtimestamp(secs, tz=timezone.utc)
                else:
                    continue
                price = _to_float(t.get("yes_price_dollars"))
                if price is None:
                    yp = t.get("yes_price")
                    price = float(yp) / 100.0 if yp is not None else None
                if price is None:
                    continue
                size = (_to_float(t.get("count")) or _to_float(t.get("taker_count"))
                        or _to_float(t.get("size")) or 0.0)
                out.append(Trade(timestamp=ts, price=price, size=size))
            except (TypeError, ValueError, KeyError):
                continue
        cutoff = datetime.now(timezone.utc).timestamp() - lookback_seconds
        out = [t for t in out if t.timestamp.timestamp() >= cutoff]
        return sorted(out, key=lambda t: t.timestamp)

    # ---------- velocity (identical logic to PolymarketTool) ----------

    def _get_velocity_reading(self, intent: BetIntent) -> VelocityReading:
        has_agent_hints = (
            intent.seconds_since_last_event is not None
            or intent.recent_price_movement_30s_pct is not None
        )
        if has_agent_hints:
            return velocity_from_agent_intent(
                token_id=intent.token_id,
                pct_change_30s=intent.recent_price_movement_30s_pct,
                seconds_since_last_event=intent.seconds_since_last_event,
            )
        trades = self._fetch_recent_trades(intent.token_id, lookback_seconds=60)
        return compute_velocity(trades, token_id=intent.token_id, source="live")

    # ---------- hard rails (identical to PolymarketTool) ----------

    def _check_basic_rails(self, intent: BetIntent) -> None:
        if intent.side not in ("BUY", "SELL"):
            raise BetRejected(f"invalid side: {intent.side}")
        if not (0 < intent.price < 1):
            raise BetRejected(f"invalid price: {intent.price}")
        if not (0 < intent.estimated_probability < 1):
            raise BetRejected(f"invalid estimated_probability: {intent.estimated_probability}")
        if not (0 < intent.confidence <= 1):
            raise BetRejected(f"invalid confidence: {intent.confidence}")
        if not intent.reasoning.strip():
            raise BetRejected("missing reasoning (philosophy: state the edge)")
        if not intent.sources:
            raise BetRejected("no sources cited (philosophy: cite the signal)")
        if not intent.price_feed_confirmed:
            raise BetRejected("price feed not confirmed / stale")

    def _check_velocity_rails(self, reading: VelocityReading, intent: BetIntent) -> None:
        if intent.in_play and not reading.has_market_data:
            raise BetRejected(
                "in-play bet but no live market data could be fetched — failing "
                "closed (cannot verify event window or velocity). Retry once the "
                "feed is back, or pass."
            )
        reason = reading.kill_reason()
        if reason:
            raise BetRejected(reason)

    # ---------- main entry point ----------

    def place_bet(self, intent: BetIntent) -> dict:
        """Place a Kalshi bet, applying ALL hard rails and sizing rules.

        Same contract as PolymarketTool.place_bet: returns a status dict, always
        logs, raises BetRejected on a rail violation / SizingError on no-edge.
        """
        # 1. Basic rails
        try:
            self._check_basic_rails(intent)
        except BetRejected as e:
            log_kill_decision(intent, reason=str(e), config=self.config)
            raise

        # 1b. Position guard (file-based, survives stateless cron sessions)
        if not intent.allow_duplicate and has_open_position(intent, self.config):
            reason = (
                f"already hold an open position in token {intent.token_id} "
                f"(philosophy: one entry per market per window). Set "
                f"allow_duplicate only with genuinely new information."
            )
            log_kill_decision(intent, reason=reason, config=self.config)
            raise BetRejected(reason)

        # 2. Velocity + event rails (agent override or live Kalshi fetch)
        velocity = self._get_velocity_reading(intent)
        intent.velocity_audit = {
            "source": velocity.source,
            "has_market_data": velocity.has_market_data,
            "samples_count": velocity.samples_count,
            "pct_change_30s": velocity.pct_change_30s,
            "largest_jump_60s": velocity.largest_jump_60s,
            "seconds_since_largest_jump": velocity.seconds_since_largest_jump,
        }
        try:
            self._check_velocity_rails(velocity, intent)
        except BetRejected as e:
            log_kill_decision(intent, reason=str(e), config=self.config)
            raise

        # 3. Bankroll + sizing (reused module — identical math)
        bankroll = self.get_bankroll_usd()
        try:
            sized: SizingResult = compute_size(
                bankroll=bankroll,
                starting_bankroll=self.config.starting_bankroll_usd,
                estimated_probability=intent.estimated_probability,
                ask_price=intent.price,
                confidence=intent.confidence,
                is_exotic=intent.is_exotic,
                fixed_cost_usd=self.config.fixed_cost_usd,
            )
        except SizingError as e:
            log_kill_decision(intent, reason=f"sizing: {e}", config=self.config)
            raise

        # 4. Defense in depth: absolute ceiling
        if sized.size_usd > self.config.absolute_max_bet_usd:
            reason = (
                f"computed size ${sized.size_usd:.2f} exceeds absolute ceiling "
                f"${self.config.absolute_max_bet_usd:.2f} — bankroll calc may be wrong"
            )
            log_kill_decision(intent, reason=reason, config=self.config)
            raise BetRejected(reason)

        # 5. Stamp the intent so logs show what was actually sized
        intent.computed_size_usd = sized.size_usd
        intent.sizing_audit = {
            "bankroll": sized.bankroll,
            "size_fraction": sized.size_fraction,
            "confidence_floor": sized.confidence_floor,
            "tier_ceiling_fraction": sized.tier_ceiling_fraction,
            "kelly_full": sized.kelly_fraction_full,
            "kelly_half": sized.kelly_fraction_half,
            "edge": sized.edge,
            "is_exotic_halved": sized.is_exotic_halved,
            "expected_profit_usd": sized.expected_profit_usd,
        }

        # 6. DRY_RUN: log + return, NO order sent
        if self.config.dry_run:
            log_bet_decision(intent, status="dry_run", result=None, config=self.config)
            record_position(intent, status="dry_run", config=self.config)
            return {
                "status": "dry_run",
                "size_usd": sized.size_usd,
                "intent": intent.__dict__,
                "message": "DRY_RUN=true; no Kalshi order sent.",
            }

        # 7. Real placement — Kalshi POST /portfolio/events/orders
        count = max(1, round(sized.size_usd / intent.price))
        side = "bid" if intent.side == "BUY" else "ask"  # bid = buy YES, ask = sell YES
        body = {
            "ticker": intent.token_id,
            "side": side,
            "count": str(count),
            "price": f"{intent.price:.4f}",
            "time_in_force": "good_till_canceled",
            "self_trade_prevention_type": "taker_at_cross",
            "client_order_id": str(uuid.uuid4()),  # idempotency / dedup
        }
        result = self._get_client().place_order(body)
        log_bet_decision(intent, status="placed", result=result, config=self.config)
        record_position(intent, status="placed", config=self.config)
        return {
            "status": "placed",
            "size_usd": sized.size_usd,
            "count": count,
            "intent": intent.__dict__,
            "result": result,
        }
