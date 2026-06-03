"""The slow engine: a minimal Dixon-Coles Poisson fair-value model.

The philosophy says: build a fair-value estimate from named inputs (Elo,
expected goals) BEFORE looking at the price, so the price can't anchor you.
This module is that engine. It is deliberately minimal:

    Elo ratings  →  expected goals (lambdas)  →  Dixon-Coles scoreline grid
                 →  fair-value probabilities for the standard markets

It is NOT a fitted model. The constants (mu_total, supremacy_per_100, rho)
are priors you can tune. The point is to give the agent a *defensible number*
to compare against the market price, instead of inventing a probability.

Everything here is pure math: no network, fully testable offline. The agent
sources the Elo ratings (from eloratings.net via web_search) and passes them
in; this module turns them into market probabilities.

Reference: docs/BETTING_PHILOSOPHY.md, "The analytical toolkit".
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# --- Tunable priors (documented defaults, override per-call if you have reason) ---

# Average total goals in a competitive international match. ~2.5 is a
# reasonable World Cup prior; knockouts tend lower, group openers higher.
DEFAULT_MU_TOTAL = 2.5

# Goal supremacy per 100 Elo points of difference. 0.40 means a 100-Elo edge
# is worth ~0.4 expected goals. Calibrate against history if you want; this is
# a conservative middle-of-the-road value.
DEFAULT_SUPREMACY_PER_100 = 0.40

# Dixon-Coles low-score correlation correction. Small negative nudges
# probability toward 0-0 and 1-1 (draws) and away from 1-0 / 0-1, correcting
# the basic Poisson model's underestimate of low-scoring draws.
DEFAULT_RHO = -0.05

# Floor on a team's expected goals so a huge favorite never zeroes out the dog.
MIN_LAMBDA = 0.15

# Scoreline grid is computed up to this many goals per team, then normalized.
MAX_GOALS = 10


@dataclass(frozen=True)
class FairValue:
    """Model output. Compare these probabilities against the market ask."""
    lambda_home: float
    lambda_away: float
    elo_win_expectation_home: float   # pure-Elo win expectation (ignores draws)
    home_win: float
    draw: float
    away_win: float
    over_2_5: float
    under_2_5: float
    btts_yes: float
    btts_no: float

    def as_dict(self) -> dict:
        return {
            "lambda_home": round(self.lambda_home, 3),
            "lambda_away": round(self.lambda_away, 3),
            "elo_win_expectation_home": round(self.elo_win_expectation_home, 3),
            "home_win": round(self.home_win, 4),
            "draw": round(self.draw, 4),
            "away_win": round(self.away_win, 4),
            "over_2_5": round(self.over_2_5, 4),
            "under_2_5": round(self.under_2_5, 4),
            "btts_yes": round(self.btts_yes, 4),
            "btts_no": round(self.btts_no, 4),
        }


class FairValueError(ValueError):
    """Invalid inputs to the fair-value model."""


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _dc_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor for cell (x, y)."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def elo_to_lambdas(
    elo_home: float,
    elo_away: float,
    home_adv: float = 0.0,
    mu_total: float = DEFAULT_MU_TOTAL,
    supremacy_per_100: float = DEFAULT_SUPREMACY_PER_100,
) -> tuple[float, float]:
    """Map Elo ratings to each side's expected goals.

    home_adv is added to the home Elo (use 0 for neutral venues — most of
    World Cup 2026 is neutral; use a positive value only for actual host
    nation matches: USA, Canada, Mexico).
    """
    if mu_total <= 0:
        raise FairValueError(f"mu_total must be positive, got {mu_total}")
    d = (elo_home + home_adv) - elo_away
    supremacy = supremacy_per_100 * (d / 100.0)
    lambda_home = max(MIN_LAMBDA, (mu_total + supremacy) / 2.0)
    lambda_away = max(MIN_LAMBDA, (mu_total - supremacy) / 2.0)
    return lambda_home, lambda_away


def scoreline_grid(
    lambda_home: float,
    lambda_away: float,
    rho: float = DEFAULT_RHO,
    max_goals: int = MAX_GOALS,
) -> list[list[float]]:
    """Build a normalized Dixon-Coles scoreline probability matrix.

    grid[i][j] = P(home scores i, away scores j).
    """
    grid = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    total = 0.0
    for i in range(max_goals + 1):
        ph = _poisson_pmf(i, lambda_home)
        for j in range(max_goals + 1):
            pa = _poisson_pmf(j, lambda_away)
            cell = ph * pa * _dc_tau(i, j, lambda_home, lambda_away, rho)
            cell = max(0.0, cell)  # tau can't realistically go negative here, but be safe
            grid[i][j] = cell
            total += cell
    if total <= 0:
        raise FairValueError("degenerate scoreline grid (total probability 0)")
    # Normalize (corrects for the truncated Poisson tail + the DC reweighting)
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            grid[i][j] /= total
    return grid


def market_probabilities(grid: list[list[float]]) -> dict:
    """Read the standard market probabilities off a scoreline grid."""
    n = len(grid)
    home_win = draw = away_win = 0.0
    over = under = 0.0
    btts_yes = btts_no = 0.0
    for i in range(n):
        for j in range(n):
            p = grid[i][j]
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
            if i + j >= 3:
                over += p
            else:
                under += p
            if i >= 1 and j >= 1:
                btts_yes += p
            else:
                btts_no += p
    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_2_5": over,
        "under_2_5": under,
        "btts_yes": btts_yes,
        "btts_no": btts_no,
    }


def fair_value(
    elo_home: float,
    elo_away: float,
    home_adv: float = 0.0,
    mu_total: float = DEFAULT_MU_TOTAL,
    supremacy_per_100: float = DEFAULT_SUPREMACY_PER_100,
    rho: float = DEFAULT_RHO,
) -> FairValue:
    """Full pipeline: Elo in, fair-value market probabilities out.

    Raises FairValueError on bad input.
    """
    if elo_home <= 0 or elo_away <= 0:
        raise FairValueError(
            f"Elo ratings must be positive, got home={elo_home}, away={elo_away}"
        )
    lam_h, lam_a = elo_to_lambdas(
        elo_home, elo_away, home_adv, mu_total, supremacy_per_100
    )
    grid = scoreline_grid(lam_h, lam_a, rho)
    mkt = market_probabilities(grid)
    d = (elo_home + home_adv) - elo_away
    elo_we = 1.0 / (1.0 + 10 ** (-d / 400.0))
    return FairValue(
        lambda_home=lam_h,
        lambda_away=lam_a,
        elo_win_expectation_home=elo_we,
        home_win=mkt["home_win"],
        draw=mkt["draw"],
        away_win=mkt["away_win"],
        over_2_5=mkt["over_2_5"],
        under_2_5=mkt["under_2_5"],
        btts_yes=mkt["btts_yes"],
        btts_no=mkt["btts_no"],
    )
