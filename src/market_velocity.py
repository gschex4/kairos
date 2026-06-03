"""Market velocity + event-window detection from Polymarket trade history.

The philosophy doc lists two related Hard Rails:
  1. "Within 60 seconds of a goal, red card, or VAR review. No exceptions."
  2. "The market moved more than 5 percent in the last 30 seconds."

Without a separate sports data feed, the cleanest code-enforceable proxy is:
the trade history itself. Match events (goal/red/VAR) show up as a sharp
single-trade jump with volume, and the seconds since that jump tells us how
long ago the event was. Net 30s drift catches steady repricing on slower news.

This module is pure: take a list of recent trades, return a VelocityReading.
The Polymarket tool is responsible for fetching the trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

# Thresholds
PCT_CHANGE_30S_KILL = 0.05   # philosophy: ">5% in last 30s"
SINGLE_JUMP_EVENT = 0.02     # ≥2% one-trade jump = treat as a match event
EVENT_WINDOW_SECONDS = 60    # philosophy: "within 60s of a goal/red/VAR"


@dataclass(frozen=True)
class Trade:
    timestamp: datetime
    price: float
    size: float  # share count, used for downstream weighting if we want it


@dataclass(frozen=True)
class VelocityReading:
    """A snapshot of how fast a market is moving right now."""
    token_id: str
    has_market_data: bool
    samples_count: int = 0
    price_now: Optional[float] = None
    pct_change_30s: Optional[float] = None             # net % move over last 30s
    largest_jump_60s: Optional[float] = None           # biggest single-trade jump in last 60s
    seconds_since_largest_jump: Optional[int] = None
    source: str = "live"  # "live" (from API), "agent_override", or "none"

    @property
    def trips_velocity_kill(self) -> bool:
        if self.pct_change_30s is None:
            return False
        return abs(self.pct_change_30s) > PCT_CHANGE_30S_KILL

    @property
    def trips_event_kill(self) -> bool:
        if self.largest_jump_60s is None or self.seconds_since_largest_jump is None:
            return False
        return (
            self.largest_jump_60s >= SINGLE_JUMP_EVENT
            and self.seconds_since_largest_jump < EVENT_WINDOW_SECONDS
        )

    def kill_reason(self) -> Optional[str]:
        """Returns a human-readable kill reason, or None if no rail tripped."""
        if self.trips_event_kill:
            return (
                f"market event proxy: {self.largest_jump_60s:.1%} single-trade jump "
                f"{self.seconds_since_largest_jump}s ago (event window is "
                f"{EVENT_WINDOW_SECONDS}s)"
            )
        if self.trips_velocity_kill:
            return (
                f"market velocity: {self.pct_change_30s:.1%} net move in last 30s "
                f"(threshold {PCT_CHANGE_30S_KILL:.0%})"
            )
        return None


def compute_velocity(
    trades: list[Trade],
    token_id: str,
    now: Optional[datetime] = None,
    source: str = "live",
) -> VelocityReading:
    """Pure compute over a sorted trade history (oldest first).

    Returns a reading even when input is empty (has_market_data=False).
    The caller decides what to do with no-data readings: typically don't kill,
    since absence of data is not evidence of a repricing event.
    """
    now = now or datetime.now(timezone.utc)
    if not trades:
        return VelocityReading(
            token_id=token_id, has_market_data=False, source=source
        )

    # Make sure they're sorted (defensive; cheap)
    trades = sorted(trades, key=lambda t: t.timestamp)
    samples = len(trades)
    price_now = trades[-1].price

    # 30s net change
    cutoff_30s = now - timedelta(seconds=30)
    in_30s = [t for t in trades if t.timestamp >= cutoff_30s]
    pct_30s: Optional[float] = None
    if in_30s and in_30s[0].price > 0:
        pct_30s = (price_now - in_30s[0].price) / in_30s[0].price

    # 60s largest single-trade jump
    cutoff_60s = now - timedelta(seconds=60)
    in_60s = [t for t in trades if t.timestamp >= cutoff_60s]
    largest_jump: Optional[float] = None
    largest_jump_at: Optional[datetime] = None
    for i in range(1, len(in_60s)):
        prev = in_60s[i - 1]
        curr = in_60s[i]
        if prev.price <= 0:
            continue
        jump = abs(curr.price - prev.price) / prev.price
        if largest_jump is None or jump > largest_jump:
            largest_jump = jump
            largest_jump_at = curr.timestamp

    seconds_since_jump: Optional[int] = None
    if largest_jump_at is not None:
        seconds_since_jump = int((now - largest_jump_at).total_seconds())

    return VelocityReading(
        token_id=token_id,
        has_market_data=True,
        samples_count=samples,
        price_now=price_now,
        pct_change_30s=pct_30s,
        largest_jump_60s=largest_jump,
        seconds_since_largest_jump=seconds_since_jump,
        source=source,
    )


def velocity_from_agent_intent(
    token_id: str,
    pct_change_30s: Optional[float],
    seconds_since_last_event: Optional[int],
    single_jump_pct: Optional[float] = None,
) -> VelocityReading:
    """Build a reading from agent-supplied fields (override path).

    Used when:
      - Smoke tests want to drive the rails without a live client.
      - The agent has external knowledge (e.g. it saw a goal tweet) and wants
        to populate the event field even if the trade-API check missed it.
    """
    # If agent says an event happened N seconds ago, treat it as a jump
    # that's at least the event threshold so the kill fires correctly.
    jump = single_jump_pct
    if seconds_since_last_event is not None and jump is None:
        jump = SINGLE_JUMP_EVENT  # agent-asserted event = canonical event jump
    return VelocityReading(
        token_id=token_id,
        has_market_data=True,
        samples_count=0,
        pct_change_30s=pct_change_30s,
        largest_jump_60s=jump,
        seconds_since_largest_jump=seconds_since_last_event,
        source="agent_override",
    )
