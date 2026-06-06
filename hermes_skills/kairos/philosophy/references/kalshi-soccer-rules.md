# Kalshi Soccer Settlement Rules

## Group Stage Matches

All group stage match markets settle on **90 minutes plus stoppage time only**. Extra time and penalties do NOT count.

- `KXWCGAME-*` market for a team wins → that team must be winning at the final whistle of regulation
- `TIE` market → match is drawn after 90'+ stoppage time
- If a match goes to extra time/penalties in a knockout round, the TIE market still resolves based on the 90' score

This is critical: a team that wins on penalties but drew in regulation pays out the TIE market, not the win market.

## Knockout Stage

Knockout match markets also settle on 90 minutes + stoppage time. This means:
- A team that wins in extra time does NOT pay out the win market (it settles as a draw in regulation)
- Penalty shootout winners do NOT pay out the win market
- The `TIE` market resolves Yes for any match tied after 90 minutes

## Market Resolution Timing

- Markets settle automatically when a winner is declared (final whistle)
- Settlement timer is 30 seconds after the event ends
- Expected expiration is ~3 hours after match end to allow for disputes

## Cancellation / Reschedule Rules

- If a match is cancelled or rescheduled to over two weeks away, markets resolve at a fair price determined by Kalshi
- Early close conditions are checked automatically

## Implications for Betting

- **Group stage**: Bet the regulation result only. A team leading 1-0 at 80' that concedes in 90+4' pays draw, not win.
- **Knockout**: Same rule applies. The Elo model already predicts regulation outcomes, so no adjustment needed — but be aware that a team that consistently wins in extra time (e.g., Italy historically) has a lower regulation win probability than their overall win rate suggests.
- **Avoid betting on teams known for late-game heroics** (e.g., Portugal, Croatia) to win in regulation — their matches are more likely to be drawn at 90'.
