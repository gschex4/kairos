"""Bet sizing — encodes the philosophy doc's Sizing + Bankroll Milestones.

Pure functions, no I/O. The Polymarket tool calls these to size every bet
and to determine the active confidence floor.

Reference: docs/BETTING_PHILOSOPHY.md, sections "Sizing" and "Bankroll milestones".
"""
from __future__ import annotations

from dataclasses import dataclass

# --- Constants from the philosophy doc (single source of truth) ---

# Hard ceiling: never risk more than 10% of current bankroll on one bet.
HARD_CEILING_FRACTION = 0.10

# Minimum worth placing: 3% of current bankroll. Below this, pass.
MIN_FRACTION = 0.03

# Confidence-tiered ceilings (top of each band from the philosophy)
TIER_CEILINGS = [
    # (min_confidence, max_fraction_of_bankroll)
    (0.75, 0.10),  # "Confidence above 0.75: up to the 10 percent cap"
    (0.65, 0.07),  # "Confidence 0.65 to 0.75: roughly 5 to 7 percent"
    (0.60, 0.04),  # "Confidence around 0.60 to 0.65: target roughly 3 to 4 percent"
]

# Bankroll milestone → minimum confidence to place any bet
# Keyed by remaining fraction of starting bankroll
MILESTONE_FLOORS = [
    # (min_remaining_fraction, min_confidence)
    (0.60, 0.60),  # >60% remaining: standard floor
    (0.40, 0.65),  # 40-60% remaining
    (0.20, 0.80),  # 20-40% remaining
    (0.00, 0.85),  # <20% remaining: near-hibernation
]

KELLY_FRACTION = 0.5  # half-Kelly default

# Exotic / thin markets get their computed size cut in half (philosophy:
# "A reasonable default is to halve the computed size on any market with
# a wide spread or shallow book.")
EXOTIC_MARKET_MULTIPLIER = 0.5


@dataclass(frozen=True)
class SizingResult:
    """The outcome of a sizing computation, suitable for logging."""
    size_usd: float
    size_fraction: float          # fraction of bankroll
    bankroll: float
    confidence_floor: float       # active floor from milestone
    tier_ceiling_fraction: float  # ceiling from confidence tier
    kelly_fraction_full: float    # full Kelly (per-bankroll fraction)
    kelly_fraction_half: float    # half-Kelly (what we use as the basis)
    edge: float                   # estimated_probability - ask_price
    is_exotic_halved: bool
    expected_profit_usd: float    # edge * shares; must clear transaction cost


class SizingError(Exception):
    """Sizing cannot produce a valid bet. The bet should be passed."""


def confidence_floor_for_bankroll(bankroll: float, starting_bankroll: float) -> float:
    """Active confidence floor based on what fraction of bankroll remains."""
    if starting_bankroll <= 0:
        raise SizingError(f"starting_bankroll must be > 0, got {starting_bankroll}")
    if bankroll < 0:
        raise SizingError(f"bankroll must be >= 0, got {bankroll}")

    remaining = bankroll / starting_bankroll
    for threshold, floor in MILESTONE_FLOORS:
        if remaining > threshold:
            return floor
    return MILESTONE_FLOORS[-1][1]  # defensive: shouldn't reach here


def tier_ceiling_for_confidence(confidence: float) -> float:
    """Per-tier max fraction of bankroll, from confidence tiering."""
    for min_conf, max_frac in TIER_CEILINGS:
        if confidence >= min_conf:
            return max_frac
    return 0.0  # below the lowest tier means no bet


def kelly_fraction(estimated_probability: float, ask_price: float) -> float:
    """Full-Kelly fraction of bankroll for a single Polymarket-style bet.

    For binary outcomes priced at `ask_price` (e.g. 0.55 USDC per share)
    with the agent's estimated probability `estimated_probability`:

        edge = p - c
        kelly = edge / (1 - c)

    Returns 0 if edge <= 0 (no positive edge → no bet).
    Raises SizingError on invalid inputs.
    """
    if not (0 < ask_price < 1):
        raise SizingError(f"ask_price must be in (0, 1), got {ask_price}")
    if not (0 < estimated_probability < 1):
        raise SizingError(
            f"estimated_probability must be in (0, 1), got {estimated_probability}"
        )

    edge = estimated_probability - ask_price
    if edge <= 0:
        return 0.0
    return edge / (1 - ask_price)


def compute_size(
    *,
    bankroll: float,
    starting_bankroll: float,
    estimated_probability: float,
    ask_price: float,
    confidence: float,
    is_exotic: bool = False,
    fixed_cost_usd: float = 0.0,
) -> SizingResult:
    """Compute the bet size in USD, applying all of the philosophy's rules.

    Raises SizingError if the bet should be passed (no edge, below floors,
    or expected profit doesn't clear `fixed_cost_usd`). Callers catch
    SizingError and route to the kill log.
    """
    if bankroll <= 0:
        raise SizingError(f"bankroll is ${bankroll:.2f} — nothing to size")
    if not (0 < confidence <= 1):
        raise SizingError(f"confidence must be in (0, 1], got {confidence}")

    # Confidence floor for this bankroll level (milestone-based)
    floor = confidence_floor_for_bankroll(bankroll, starting_bankroll)
    if confidence < floor:
        raise SizingError(
            f"confidence {confidence:.2f} below milestone floor {floor:.2f} "
            f"(bankroll ${bankroll:.2f} / ${starting_bankroll:.2f} starting)"
        )

    # Kelly fraction
    full_kelly = kelly_fraction(estimated_probability, ask_price)
    if full_kelly == 0:
        raise SizingError(
            f"no positive edge: est_prob {estimated_probability:.3f} <= "
            f"ask_price {ask_price:.3f}"
        )
    half_kelly = full_kelly * KELLY_FRACTION

    # Confidence-tiered ceiling (separate from milestone floor)
    tier_ceiling = tier_ceiling_for_confidence(confidence)

    # Size = min(half-Kelly, tier ceiling), then halve if exotic, then hard 10% cap.
    size_fraction = min(half_kelly, tier_ceiling)
    is_exotic_halved = False
    if is_exotic:
        size_fraction *= EXOTIC_MARKET_MULTIPLIER
        is_exotic_halved = True
    size_fraction = min(size_fraction, HARD_CEILING_FRACTION)

    # "If half-Kelly comes back below the minimum worth placing, pass."
    if size_fraction < MIN_FRACTION:
        raise SizingError(
            f"sized fraction {size_fraction:.3f} below min worth placing "
            f"{MIN_FRACTION:.3f} (bankroll ${bankroll:.2f})"
        )

    size_usd = round(size_fraction * bankroll, 2)

    # Net-of-cost guard: expected gross profit must clear transaction cost.
    # shares = size_usd / ask_price; per-share EV = (true_prob - price) = edge;
    # so expected profit ≈ shares * edge. A thin edge on a small stake can be
    # +EV on paper but -EV after Polygon gas + spread. If it doesn't clear, pass.
    edge_value = estimated_probability - ask_price
    expected_profit_usd = (size_usd / ask_price) * edge_value
    if expected_profit_usd <= fixed_cost_usd:
        raise SizingError(
            f"expected profit ${expected_profit_usd:.3f} does not clear "
            f"transaction cost ${fixed_cost_usd:.3f} (edge {edge_value:.3f} too "
            f"thin for ${size_usd:.2f} stake)"
        )

    return SizingResult(
        size_usd=size_usd,
        size_fraction=size_fraction,
        bankroll=bankroll,
        confidence_floor=floor,
        tier_ceiling_fraction=tier_ceiling,
        kelly_fraction_full=full_kelly,
        kelly_fraction_half=half_kelly,
        edge=edge_value,
        is_exotic_halved=is_exotic_halved,
        expected_profit_usd=round(expected_profit_usd, 4),
    )
