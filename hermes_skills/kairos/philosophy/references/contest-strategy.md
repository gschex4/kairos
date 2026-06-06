# Kalshi Free-to-Enter Contest Strategy

*Derived from the $1M World Cup winner contest, Jun 5 2026.*

## Core Principle

A free-entry contest has **zero cost** and **positive expected value for any pick**. The optimization shifts from Kelly sizing to **maximizing: P(team wins) / crowd_pick_rate**.

## Key Differences from Betting

| Dimension | Betting | Contest |
|-----------|---------|---------|
| Cost | Real money per contract | Free |
| Goal | Maximize risk-adjusted return | Maximize probability × prize share |
| Sizing | Half-Kelly | All-in (one pick) |
| Contrarian value | Negative (reduces edge) | Positive (fewer co-winners) |
| Long shots | Bad (edge shrinks with Elo gap) | Neutral (bigger share if they win) |

## Crowd Psychology

Casual entrants pick based on name recognition and narrative, not Elo:
- **Overpicked:** France (defending champs, Mbappe), Argentina (Messi farewell), Brazil (samba reputation), England (PL global audience)
- **Underpicked:** Spain (no major recent narrative), Germany (down cycle reputation), Portugal (Ronaldo shadow)

## The Quiet Favorite Strategy

The optimal pick is the team with the **highest true win probability** that the casual crowd systematically **underestimates**. As of Jun 5 2026:
- Spain (Elo #1, 2155) fits this perfectly — highest Elo, fewest casual fans picking them
- Argentina, France, Brazil will split the crowd vote
- If Spain wins, the pool has fewer winners = bigger individual share

## Implementation

When the user asks about a free contest pick:
1. Compute Elo-based tournament probabilities (same as betting)
2. Estimate crowd-pick rate from Kalshi tournament winner prices (higher price = more attention)
3. Score: `P(win) / min(1.5, crowd_pick_fraction)` — penalize heavily-picked teams
4. Recommend the top-scored team, with one-sentence reasoning

## Example

Jun 5 2026 $1M contest: Recommended **Spain** despite Argentina/France having similar Kalshi prices. Spain's Elo dominance + low crowd appeal = best expected share of the prize pool.
