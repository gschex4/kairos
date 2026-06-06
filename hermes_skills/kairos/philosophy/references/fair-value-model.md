# Elo-Based Fair-Value Model for World Cup Markets

*Built and validated Jun 5, 2026. Uses eloratings.net data + Kalshi market prices.*

## Tournament Winner Model

### Approach
For a 48-team knockout tournament, each team's probability is proportional to their Elo-transformed strength:

```
strength(t) = exp(elo(t) / 400)
fair_value(t) = strength(t) / SUM(strength for all teams)
```

This is a simplification — it doesn't account for:
- Bracket structure (which teams are on which side of the draw)
- Group draw difficulty (weak group = easier path to RO32)
- Knockout path quality (which teams you'd face in later rounds)
- Home advantage for the 3 host nations (USA, Canada, Mexico)
- Recent form / injuries

### Accuracy
- The model correctly identifies the top tier (Spain, France, Argentina, England, Brazil)
- It likely UNDERESTIMATES top teams and OVERESTIMATES mid-tier teams because it ignores bracket structure
- For buy-side edge (undervalued teams), the raw Elo model is more conservative — if it says a team is undervalued, that's stronger signal
- For sell-side edge (overvalued teams), bracket structure matters more — the favorites' paths should be simulated properly

### Edge Computation
```
edge = fair_value - market_ask_price
```

Edge >0.02 (2%) is the threshold for consideration. Most individual game lines at this stage have edge <1%.

### Implementation (Python)

```python
import math
def fair_value(elo_ratings, team_codes):
    elo_for = {}
    for c in team_codes:
        elo_for[c] = elo_ratings.get(c, 1500)
    
    total = 0.0
    strengths = {}
    for c in team_codes:
        s = math.exp(elo_for[c] / 400.0)
        strengths[c] = s
        total += s
    
    return {c: s/total for c, s in strengths.items()}
```

## KXWCROUND (Reach-Round) Model

For a team to reach a given round, compute:
1. Probability of winning each necessary match (from Elo)
2. Multiply sequential match probabilities
3. Account for group placement (top 2 vs 3rd place paths differ in 2026 format)

Basic approximation for group stage advancement:
```
P(reach RO32) = P(finish top 2 in group)
P(reach RO16) = P(top 2 in group) * P(win RO32 match)
P(reach QF)   = P(reach RO16) * P(win RO16 match)
```

Where match win probability = 1 / (1 + 10^((elo_opponent - elo_team) / 400))

For KXWCROUND prices, the model can be run against the 4 events:
- KXWCROUND-26RO16 (Round of 16)
- KXWCROUND-26QUAR (Quarterfinals)  
- KXWCROUND-26SEMI (Semifinals)
- KXWCROUND-26FINAL (Final)

## Group Qualifier Model (KXWCGROUPQUAL)

For each group (A-L, 4 teams each):
1. Compute pairwise win probabilities for all 6 matches in the group
2. Simulate the group stage (each team plays 3 matches)
3. Top 2 advance to RO32

Simplified: each team's group qualification probability ≈ their Elo strength vs the other 3 teams in the group. The stronger team in a group of 4 has an outsized advantage.

## Elo-Based Match Probability (for KXWCGAME lines)

The `kairos_fair_value` tool (Elo Dixon-Coles model) works for match-level probability estimates. Feed it Elo ratings from `references/wc-2026-elo-ratings.md`.

For manual computation of a 3-way match line:
```python
def elo_prob(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))

def match_fair_value(elo_home, elo_away):
    p_home_raw = elo_prob(elo_home, elo_away)
    p_away_raw = 1.0 - p_home_raw
    # Draw absorbs ~12-15%, higher for close matchups
    draw = 0.12 + 0.03 * (1.0 - abs(p_home_raw - 0.5) * 2)
    draw = min(draw, 0.35)
    scale = 1.0 - draw
    return {
        'home': round(p_home_raw * scale, 3),
        'draw': round(draw, 3),
        'away': round(p_away_raw * scale, 3)
    }
```

## When to Run

- **Pre-tournament**: Tournament winner + KXWCROUND + group qualifier (markets respond to Elo)
- **During group stage**: KXWCGAME match lines (Elo adjusts for tournament performance)
- **After groups settle**: Re-run KXWCROUND with updated Elo (accounts for in-tournament form)
- **Knockout stage**: KXWCGAME specific lines (head-to-head, Elo is most accurate here)

## Free-to-Enter Contests

For free-entry contests (no cost), see `references/contest-strategy.md`. The optimization shifts from Kelly sizing to probability × prize-share maximization.
