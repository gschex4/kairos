# Edge Finder: One-Page System Summary

Reference for bootstrapping Kairos. This describes the parent system as it actually runs, not as an ideal.

## What it bets and where

Edge Finder is a multi-sport research engine covering four core sports (UFC, NFL, NBA, MLB) and a sprinkle set (golf, soccer, tennis, F1, boxing, horse racing). Primary betting book is theScore Bet; sharp reference books are Pinnacle, then Circa, then Bookmaker. It scans every market type per event, not just sides and totals: moneyline, spread, total, alt lines, team totals, period markets (first half, first 5 innings), player props (main and alt), prop combos, and game props. The softest prices live in alt lines and props, so those get hunted hardest.

## Data inputs and signal sources

Web search for current odds, injury news, lineups, weigh-ins, fields, and probable pitchers. Named statistical sources by sport: FanGraphs for MLB (xFIP, SIERA, wRC+ splits), UFCStats for fight metrics (SLpM, striking defense, takedown defense), DataGolf for golf, Cleaning the Glass for NBA. A Polymarket divergence scan flags any market where the prediction-market price diverges from the sharp no-vig fair by 5 or more probability points (10 or more is priority one).

## Decision logic: act vs pass

The null hypothesis is always "no bet." A candidate earns its way onto the slate by clearing a computed edge threshold and surviving an adversarial review. The schedule gates when analysis runs (Tuesday open radar, Wednesday preview, Friday lock, Saturday confirm, Sunday adjust, Monday scoring), but it does not gate when bets are placed: any run can log a bet if the edge appears. A typical weekend produces 1 to 2 bets from 40 candidates. Most candidates die.

## Sizing logic

Quarter-Kelly by default. Compute edge first (model probability minus no-vig fair), run quarter-Kelly on the price actually paid, derive units, then label the confidence tier from the resulting unit count. Tier never drives sizing. Caps: 3.0 units max single bet, 6.0 units per sport per weekend, 15.0 units total weekend exposure, on a 100-unit base bankroll. Floor of 0.2 units; below that the bet demotes to a parlay leg or dies.

## Bias filters and skip conditions

Explicit red flags that reduce or kill confidence regardless of model output: rare-event spotlight bets (first start back from injury), inputs that disagree wildly (xFIP says one thing, SIERA another), single-input dependency (the whole thesis is "the wind"), heavy public action with no sharp line move, and reverse line movement. Every kill is logged with a reason category in a kill log that is read at the start of every run so the same bad idea does not return.

## What has worked

Computing model probability from named inputs rather than narrative. No-vigging the baseline so edges are not overstated by the vig. Catching reverse line movement: this weekend the Mets opened at -135 retail and moved to +110, and the contrarian-plus-mismatch read cashed. Adversarial review by a separate agent has repeatedly produced the exact loss path that played out (Taj Mahal pinned on the rail and fading was called nearly word for word).

## What has been a trap

Stale inputs locked too early: the Angels bet was set Saturday morning, then Sasaki was scratched and a much better starter took the mound, gutting the thesis after the bet was logged. High-variance prop bets with thin edges that look like value but are inside the model error band (Allen by Decision at +0.25pp edge was correctly killed even though it would have won). False confidence on an empty calibration history. Forcing plays to hit a volume target when the slate is genuinely thin.
