# Trade Exit Strategy — Selling Into the Re-Rate

## When to use this

Any position opened as a **trade** (see `trade-screen.md`): bought cheap because
the *price* will rise before resolution. The whole point is to **sell into
appreciation** — you do not need the event to settle YES.

**Not** for conviction / hold-to-resolution positions (most match-win bets). Those
ride to settlement; the only pre-match exit is thesis invalidation (injury, lineup
news). If you're holding to be *right about the outcome*, this doc doesn't apply.

## Core principle: harvest the move, don't round-trip it

A cheap contract that 5×'s and then settles NO pays **nothing** if you held it to
the end. The trade is the *move*, not the outcome:

> **Sell into strength as catalysts hit. Lock cost basis early, bank profit on the
> way up, and never let a winner round-trip back to zero.**

## The exit ladder — percentage-based, market-agnostic

Default rules keyed to the **relative move from entry** (works on any series):

| Price vs. entry | Action | Why |
|---|---|---|
| +100% (2×) | Sell ~25% | Recover ~half the cost basis on the first pop |
| +200–300% | Sell ~25% | Cost basis fully recovered — now playing with house money |
| +400–700% | Sell ~25% | Bank the bulk of the gain |
| +700%+ | Sell down to a runner | Heavy profit locked in |
| Runner (≤10–25% of original) | Trail or hold | Optional upside — see moonbag rule |

The *trigger* is the catalyst; the *fraction* is the ladder. When a catalyst pops
the price, that's your window to sell a tranche — don't sit on a price target that
has no catalyst behind it.

## Catalyst-timed selling (the actual mechanic)

Price, attention, and liquidity all peak in the **24–48h after a catalyst** (a win,
lineup news, a draw reveal). That window is when buyers arrive and you can sell size
without crushing the book.

- **Sell INTO the spike, not during the event** — spreads widen mid-match.
- **A binary catalyst that passed favorably = the re-rate is realized.** Take the
  scheduled tranche now; don't give it back waiting for the next catalyst.
- **A catalyst that comes and the price *doesn't* move** = the thesis is weakening.
  See the time-decay stop below.

## The moonbag rule (optional — only with resolution conviction)

Keep a small runner (≤10–25% of original) past your exits **only** if you also
believe the outcome could genuinely land. The default trade thesis ("sell the
move") does **not** require a moonbag — banking the move and walking away is a
complete, successful trade. Don't talk yourself into holding a runner just because
it's exciting. If you keep one, it's the shares you never sell until resolution.

## Stop-loss / thesis-invalidation — cut 100% when:

1. **The catalyst won't come** — eliminated, key player ruled out for the event the
   trade depended on, or the fixture is voided.
2. **The re-rate reversed** — price round-tripped back toward entry after a failed
   catalyst. The move you were trading is gone.
3. **Time decay** — held N+ days, the catalyst window passed with no move. Dead
   money — cut and redeploy. (For tournament futures: "no price move after a played
   match" is the signal.)
4. **Market error / void risk** — the market is misconfigured; exit before capital
   is locked up in a void.
5. **Bankroll needs the capital** — a higher-conviction edge appears and the bucket
   is full; a flat-lined trade is the most dispensable capital you hold.

Do **not** cut on: noise on a thin book, one bad half of football, or Twitter panic
while the catalyst is still ahead of you.

## Liquidity mechanics (Kalshi-specific)

Long-shot and cheap markets on Kalshi can have thin books. Before ANY exit:

1. **Check book depth** — `GET /markets/{ticker}` returns `yes_bid_dollars` and
   `liquidity_dollars`. If liquidity is $0.00 and the bid is one resting order for a
   few shares, a large market-sell will walk the book to a terrible average price.
2. **Thin book → limit-sell at/just below the ask**, never market-sell into the bid.
   A market sell into a thin book can crater the price 40% and trip your own
   position-watch alerts. (Limit sell = `POST /portfolio/events/orders` with
   `side='ask'` at your limit price.)
3. **Trickle large exits over hours** — 3–4 small tranches if the position is large
   relative to volume.
4. **Post-catalyst liquidity is best; mid-event is worst.** The 24–48h after a win
   is when buyers are arriving — that's the time to feed out a tranche.

## Worked example — tournament-round ladder (Ivory Coast, the specialization)

For a multi-stage tournament future, the catalysts *are* the rounds, so the generic
ladder above maps directly onto the bracket. This is **one concrete instance** of
the ladder, not the general rule.

Actual position: **250 shares @ 0.4¢ = $1.00**. Tranches ≈25%; proceeds illustrative.

| Catalyst (dated) | Est. price | Action | ~Shares | Running result |
|---|---|---|---|---|
| Beat Ecuador (Jun 14) | 1.5¢ | Sell ~25% | 62 | recover most of cost basis |
| Advance from group | 4¢ | Sell ~25% | 62 | cost basis fully back + profit |
| Win R32 | 10¢ | Sell ~25% | 63 | bulk of gain banked |
| Win R16 (→ QF) | 20¢ | Sell ~15% | 37 | heavy profit locked |
| Win QF (→ SF) | 40¢ | Let ride | 0 | moonbag (~26 sh) only |
| Reach final | 60¢ | Sell half of runner | 13 | lock life-changing money |
| Win tournament | $1.00 | Resolution | 13 | the moonbag lands |

Each knockout round is a **dated catalyst** — the same "sell into the post-catalyst
spike" mechanic, scheduled by the bracket. If a round comes and the price *doesn't*
re-rate (a narrow win the market shrugs off), that's a time-decay signal, not an
automatic hold.

### Pre-catalyst price moves

Sometimes the market re-rates before the event (lineup leaks, sharp money). If the
price moves 2×+ *before* the catalyst fires:
- **Sell 10–15% to de-risk**, not the full tranche. Pre-event moves can reverse;
  lock a small edge, keep the rest for the confirmed catalyst.

## Position-watch integration

- **Conviction / match-win positions**: alert at ≥15% relative move (existing rule).
- **Trade positions** (futures/props/awards, and any cheap contract held as a trade):
  alert at ≥50% relative move — big moves on thin markets are catalysts, small moves
  are noise. An **UP** move ≥50% = a possible exit window; check the catalyst and the
  ladder. A **DOWN** move ≥50% = thesis-invalidation signal; investigate now.

## Summary card

```
TRADE EXIT (sell into the re-rate):
├── +100%     → sell ~25%   (recover cost basis)
├── +200-300% → sell ~25%   (house money)
├── +400-700% → sell ~25%   (bank the gain)
├── +700%+    → sell down to a runner
├── runner ≤10-25% → trail/hold ONLY with resolution conviction
│
├── SELL INTO the post-catalyst spike (24-48h), never mid-event
├── catalyst passed favorably → take the tranche, don't wait
│
├── catalyst can't come / reversed / time-decayed → CUT 100%
├── always check liquidity; limit-sell thin books; trickle size
└── trade bucket ≤10% bankroll, single trade ≤5%
```
