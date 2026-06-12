# Tournament Futures Fair-Value Estimation

The Poisson Elo model in `elo-to-fv-manual.md` estimates **individual match** outcomes.
For **tournament winner / stage of elimination / reach-round futures**, no single-match
model applies — you need to estimate P(win tournament) from available evidence.

## Primary method: relative Elo share among contenders

When you can't run a full tournament simulation, use relative Elo shares to anchor
fair value among the top-favorite pool:

1. **Identify the contender pool.** Take the top 8–12 teams by Elo or by market
   price (yes_ask > some threshold, say 2¢ for tournament winner).

2. **Convert Elo to odds-space share.** For each contender i:
   ```
   share_i = 10^(Elo_i / 400) / sum(10^(Elo_j / 400))  for all j in pool
   ```

3. **Estimate the total pool probability.** Sum the market's yes_bid across all
   contenders in the pool. Market prices embed long-shot bias; the sum of yes_bid
   across all 48 KXMENWORLDCUP teams typically overshoots 1.00. Use yes_bid (not
   yes_ask) to reduce spread bias. Alternatively, anchor the top-8 combined
   probability at 80–85% for the 48-team format.

4. **Compute each contender's FV:**
   ```
   FV_i = share_i × total_pool_probability
   ```

5. **Cross-check against sportsbook implied odds** (if accessible via X research).
   Sportsbook odds provide an independent probability estimate; if Kalshi is
   2+ percentage points below sportsbook consensus, that supports the edge.

## Worked example — Argentina, Jun 10 2026

| Team | Elo | 10^(Elo/400) | Share |
|------|-----|-------------|-------|
| Spain | 2155 | 244,343 | 19.3% |
| Argentina | 2113 | 191,264 | 15.1% |
| France | 2062 | 142,889 | 11.3% |
| England | 2020 | 112,202 | 8.9% |
| Brazil | 1988 | 93,325 | 7.4% |
| Portugal | 1984 | 91,201 | 7.2% |
| Colombia | 1977 | 87,902 | 6.9% |
| Netherlands | 1944 | 72,444 | 5.7% |
| **Top 8 sum** | | **1,035,570** | **81.8%** |

Top-8 market yes_bid sum: 81.8¢ (Spain 17.6 + France 15.8 + England 10.7 + Portugal
10.4 + Argentina 8.6 + Brazil 8.4 + Germany/Netherlands 5.5+4.8 = 81.8¢).

Argentina's share: 191,264 / 1,035,570 = 18.5% of top-8 pool.
Argentina FV: 18.5% × 81.8% ≈ **15.1%** → 15.1¢.

That's the **upper bound** — the raw Elo-share method overstates favorites because
it ignores bracket path, group difficulty, and tournament variance. Apply a
conservative haircut (15–25%) to account for these:

Argentina adjusted FV: 15.1¢ × 0.80 = **~12¢**.

At a market ask of 8.7¢: edge ≈ 12¢ − 8.7¢ = **3.3¢**.

## When the method breaks down

- **Elo data older than 2 weeks** — ratings drift. The Jun 5 snapshot was acceptable
  on Jun 10 (5 days old). If Elo data is >2 weeks stale, try harder to get fresh
  ratings before using this method.
- **Major injury/suspension between Elo snapshot and now** — adjust the team's share
  down manually.
- **Teams outside the contender pool** — this method can't price longshots.
  Use the trade screen (`trade-screen.md`) for cheap contracts instead.

## Pitfalls

- **Don't use yes_ask for pool probability sum.** The ask embeds the spread; use
  yes_bid for a tighter estimate.
- **The raw Elo-share method overstates favorites.** Always apply a 15–25% haircut
  for tournament variance. The final FV should feel conservative.
- **This is an anchor, not a precision instrument.** Unlike match-FV where the
  Poisson model gives a defensible number, tournament FV is inherently coarser.
  Only bet when the edge is clear (≥3–4¢) — borderline edges on tournament futures
  are likely noise.
- **Compare to sportsbook odds when possible.** If Kalshi + sportsbook consensus
  agree within 1–2¢, the market is efficient — pass.
