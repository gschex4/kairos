"""Polymarket CLOB tool wrapper.

Wraps py-clob-client-v2 and enforces the philosophy doc's safety rules:
  1. Hard rails (basic validation, sources/reasoning required).
  2. Code-enforced market velocity + event-window detection from live trade
     history. See src/market_velocity.py for the math.
  3. Floating per-bet cap = 10% of current bankroll, with confidence-tiered
     half-Kelly sizing under the cap. See src/sizing.py.
  4. Bankroll-milestone confidence floors that tighten as bankroll shrinks.
  5. Exotic-market size halving.
  6. DRY_RUN mode that logs intended bets but never sends them.
  7. Markdown logging of every action, including kills, for Obsidian audit.

The agent calls `place_bet(intent)`. It does NOT set the bet size — the
tool computes the size from the intent's estimated_probability + confidence
+ current bankroll. The agent CAN populate market-velocity hints on the
intent (useful when it has external knowledge), but the tool will fetch
live velocity from the market when those hints are absent.

Reference: docs/BETTING_PHILOSOPHY.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx

# NOTE: import paths assume py-clob-client-v2. If pip resolves a different
# version, adjust these to match. See README for installation notes.
try:
    from py_clob_client.client import ClobClient  # type: ignore
    from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType  # type: ignore
    from py_clob_client.constants import POLYGON  # type: ignore
    _CLIENT_AVAILABLE = True
except ImportError:
    # Lets the dry-run smoke test run before the user has installed deps.
    ClobClient = None  # type: ignore
    ApiCreds = None  # type: ignore
    OrderArgs = None  # type: ignore
    OrderType = None  # type: ignore
    POLYGON = 137
    _CLIENT_AVAILABLE = False

from src.config import Config
from src.logging_setup import log_bet_decision, log_kill_decision
from src.market_velocity import (
    Trade,
    VelocityReading,
    compute_velocity,
    velocity_from_agent_intent,
)
from src.position_ledger import has_open_position, record_position
from src.sizing import SizingError, SizingResult, compute_size

POLYMARKET_HOST = "https://clob.polymarket.com"
POLYMARKET_DATA_API = "https://data-api.polymarket.com"


@dataclass
class BetIntent:
    """What the agent produces. The tool sizes it, validates it, logs it."""
    # --- Market identification ---
    market_question: str
    condition_id: str
    token_id: str

    # --- The bet ---
    side: Literal["BUY", "SELL"]
    price: float                          # ask price the agent will pay (0, 1)
    estimated_probability: float          # agent's fair-value estimate (0, 1)
    confidence: float                     # agent's confidence in the estimate (0, 1]

    # --- Justification (required, per Hard Rails) ---
    reasoning: str                        # must include the one-sentence edge
    sources: list[str]                    # X URLs, news links, etc — empty = kill

    # --- Optional context the agent can populate ---
    is_exotic: bool = False               # exotic/thin market → size halved
    price_feed_confirmed: bool = True     # if False, hard-rail kill

    # in_play=True means the match is underway (halftime or trajectory bet).
    # The velocity rail then FAILS CLOSED: if it can't fetch live market data
    # it rejects the bet rather than flying blind. Leave False for pre-match
    # (quiet markets legitimately have no recent trades).
    in_play: bool = False

    # By default the tool refuses a second bet on a token_id already held
    # (one entry per market per window). Set True only with genuinely new
    # information that justifies re-entering / adding to a market.
    allow_duplicate: bool = False

    # --- Agent-supplied velocity hints (override / supplement live fetch) ---
    # When set, these take precedence over the live trade-history fetch.
    # Useful for: (a) smoke tests, (b) cases where the agent saw a goal tweet
    # before the trade data caught up.
    seconds_since_last_event: Optional[int] = None
    recent_price_movement_30s_pct: Optional[float] = None

    # --- Filled in by the tool, not the agent ---
    computed_size_usd: Optional[float] = None
    sizing_audit: Optional[dict] = field(default=None)
    velocity_audit: Optional[dict] = field(default=None)


class BetRejected(Exception):
    """Raised when a hard rail or sizing rule blocks a bet."""


class PolymarketTool:
    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[ClobClient] = None

    # ---------- Client setup ----------

    def _get_client(self) -> ClobClient:
        if not _CLIENT_AVAILABLE:
            raise RuntimeError(
                "py-clob-client is not installed. Run `pip install -e .` first."
            )
        if self._client is None:
            client = ClobClient(
                host=POLYMARKET_HOST,
                key=self.config.polymarket_private_key,
                chain_id=self.config.polymarket_chain_id,
                funder=self.config.polymarket_funder_address,
            )
            if self.config.polymarket_api_key:
                creds = ApiCreds(
                    api_key=self.config.polymarket_api_key,
                    api_secret=self.config.polymarket_api_secret,
                    api_passphrase=self.config.polymarket_api_passphrase,
                )
            else:
                creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            self._client = client
        return self._client

    # ---------- Read methods (safe, no money moves) ----------

    def get_market_price(self, token_id: str) -> dict:
        return self._get_client().get_price(token_id, "BUY")

    def get_bankroll_usd(self) -> float:
        """Current bankroll in USD.

        DRY_RUN: returns config.dry_run_bankroll_usd.
        Live: queries the wallet's USDC balance.

        NOTE: the exact py-clob-client v2 balance call varies; the
        implementation below is a placeholder, verify at install time.
        """
        if self.config.dry_run:
            return self.config.dry_run_bankroll_usd
        client = self._get_client()
        try:
            bal = client.get_balance_allowance()  # type: ignore[attr-defined]
            return float(bal.get("balance", 0)) / 1e6  # USDC has 6 decimals
        except Exception:
            return self.config.dry_run_bankroll_usd

    def _fetch_recent_trades(
        self, token_id: str, lookback_seconds: int = 60
    ) -> list[Trade]:
        """Fetch public recent trades on a market token via Polymarket's Data API.

        The CLOB client's `get_trades()` returns YOUR account's trades (L2 auth
        required), not public market trades — easy mistake to make. For public
        trade history the right endpoint is:
            GET https://data-api.polymarket.com/trades?market={token_id}&limit=200
        No auth required, works in DRY_RUN too (so paper trading sizes against
        real market velocity).

        Returns Trade objects sorted oldest-first. Empty list on any error so
        the velocity check falls through to "no data" rather than failing.
        """
        try:
            r = httpx.get(
                f"{POLYMARKET_DATA_API}/trades",
                params={"market": token_id, "limit": 200},
                timeout=5.0,
            )
            r.raise_for_status()
            raw = r.json()
        except Exception:
            return []

        out: list[Trade] = []
        for t in raw or []:
            try:
                # Defensive: the public Data API ignores an unrecognized `market`
                # filter and returns cross-market trades. Drop any trade whose
                # asset (clobTokenId) doesn't match the requested token, so an
                # unknown/fake token yields no trades rather than cross-market
                # prices the velocity rail would misread as a huge single jump.
                asset = t.get("asset")
                if asset is not None and str(asset) != str(token_id):
                    continue
                # Polymarket trade timestamp can come as unix seconds, unix ms,
                # or ISO string. Handle all three defensively.
                ts_raw = (
                    t.get("timestamp")
                    or t.get("ts")
                    or t.get("createdAt")
                    or t.get("created_at")
                )
                if isinstance(ts_raw, (int, float)):
                    # Heuristic: > 1e12 ⇒ unix ms; else unix seconds
                    secs = ts_raw / 1000 if ts_raw > 1e12 else ts_raw
                    ts = datetime.fromtimestamp(secs, tz=timezone.utc)
                elif isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                else:
                    continue
                price = float(t.get("price"))
                size = float(t.get("size", 0))
                out.append(Trade(timestamp=ts, price=price, size=size))
            except (TypeError, ValueError, KeyError):
                continue

        cutoff = datetime.now(timezone.utc).timestamp() - lookback_seconds
        out = [t for t in out if t.timestamp.timestamp() >= cutoff]
        return sorted(out, key=lambda t: t.timestamp)

    def get_open_orders(self) -> dict:
        client = self._get_client()
        return {
            "address": self.config.polymarket_funder_address,
            "open_orders": client.get_orders(),
        }

    # ---------- Velocity gathering ----------

    def _get_velocity_reading(self, intent: BetIntent) -> VelocityReading:
        """Build a VelocityReading from agent hints or live fetch.

        Precedence (highest first):
          1. Agent override — if EITHER seconds_since_last_event OR
             recent_price_movement_30s_pct is populated on the intent.
          2. Live fetch — only attempted outside DRY_RUN with a real client.
          3. No-data reading — neither rail will fire.
        """
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

    # ---------- Hard rails ----------

    def _check_basic_rails(self, intent: BetIntent) -> None:
        """Basic shape + required-content rails. Raises BetRejected on violation."""
        if intent.side not in ("BUY", "SELL"):
            raise BetRejected(f"invalid side: {intent.side}")
        if not (0 < intent.price < 1):
            raise BetRejected(f"invalid price: {intent.price}")
        if not (0 < intent.estimated_probability < 1):
            raise BetRejected(
                f"invalid estimated_probability: {intent.estimated_probability}"
            )
        if not (0 < intent.confidence <= 1):
            raise BetRejected(f"invalid confidence: {intent.confidence}")
        if not intent.reasoning.strip():
            raise BetRejected("missing reasoning (philosophy: state the edge)")
        if not intent.sources:
            raise BetRejected("no sources cited (philosophy: cite the signal)")
        if not intent.price_feed_confirmed:
            raise BetRejected("price feed not confirmed / stale")

    def _check_velocity_rails(self, reading: VelocityReading, intent: BetIntent) -> None:
        """Apply event-window + market-velocity kill rails.

        FAIL CLOSED for in-play bets: if the match is underway but we could
        not fetch live market data, we cannot verify the event window or
        velocity, so we refuse. A pre-match bet (in_play=False) legitimately
        has no recent trades and is allowed to proceed without velocity data.
        """
        if intent.in_play and not reading.has_market_data:
            raise BetRejected(
                "in-play bet but no live market data could be fetched — failing "
                "closed (cannot verify event window or velocity). Retry once the "
                "feed is back, or pass."
            )
        reason = reading.kill_reason()
        if reason:
            raise BetRejected(reason)

    # ---------- The main entry point ----------

    def place_bet(self, intent: BetIntent) -> dict:
        """Place a bet, applying all hard rails and sizing rules.

        Returns a dict describing what happened. Always logs (to bet log on
        success/dry_run, to kill log on rejection). Raises BetRejected on
        any rail violation; raises SizingError on no-edge / below-min sizing.
        """
        # 1. Basic rails (shape + required content)
        try:
            self._check_basic_rails(intent)
        except BetRejected as e:
            log_kill_decision(intent, reason=str(e), config=self.config)
            raise

        # 1b. Position guard — don't double-bet a market already held.
        # File-based so it survives stateless cron sessions.
        if not intent.allow_duplicate and has_open_position(intent, self.config):
            reason = (
                f"already hold an open position in token {intent.token_id} "
                f"(philosophy: one entry per market per window). Set "
                f"allow_duplicate only with genuinely new information."
            )
            log_kill_decision(intent, reason=reason, config=self.config)
            raise BetRejected(reason)

        # 2. Velocity + event rails (live fetch or agent override)
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

        # 3. Bankroll + sizing (philosophy)
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

        # 5. Stamp the intent so the log shows what was actually sized
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

        # 6. DRY_RUN: log + return
        if self.config.dry_run:
            log_bet_decision(intent, status="dry_run", result=None, config=self.config)
            record_position(intent, status="dry_run", config=self.config)
            return {
                "status": "dry_run",
                "size_usd": sized.size_usd,
                "intent": intent.__dict__,
                "message": "DRY_RUN=true; no order sent.",
            }

        # 7. Real placement
        client = self._get_client()
        shares = sized.size_usd / intent.price
        order_args = OrderArgs(
            token_id=intent.token_id,
            price=intent.price,
            size=shares,
            side=intent.side,
        )
        signed = client.create_order(order_args)
        result = client.post_order(signed, OrderType.GTC)
        log_bet_decision(intent, status="placed", result=result, config=self.config)
        record_position(intent, status="placed", config=self.config)
        return {
            "status": "placed",
            "size_usd": sized.size_usd,
            "intent": intent.__dict__,
            "result": result,
        }
