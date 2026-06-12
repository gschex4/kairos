# Trade-Candidate Screen — Buy Cheap, Sell Into the Re-Rate

This is the check to run **going forward** when scanning for positions you open
*because the price is too low and will rise before resolution* — not because you
think the outcome will "hit 100%." You buy cheap, a catalyst re-rates the price
up, and you **sell into that strength**. The exit, not the settlement, is the point.

## Two kinds of position — know which one you're opening

Before any entry, decide which game you're playing. They have **opposite** exit logic:

| | **Conviction / hold-to-resolution** | **Trade / re-rate** (this doc) |
|---|---|---|
| Thesis | "This outcome happens" | "This contract is cheap and will trade higher before it resolves" |
| You need | The event to settle YES | The *price* to rise — you sell before resolution |
| Exit | Ride to settlement | Sell into strength on a catalyst; you may never hold to the end |
| Example | Mexico to beat South Africa (ride it out) | Ivory Coast at 0.4¢ — flip it on the first price pop |

Most match-win bets are conviction. This screen is for the **other** kind: cheap,
mispriced contracts where the plan is to *sell*, not to be right about the final result.
**You do not need it to hit $1.00.**

## The screen — run on any cheap contract, in any series

Pull cheap contracts (roughly **≤15¢**, where a re-rate pays multiples) across
*every* series — match-win (KXWCGAME), tournament winner (KXMENWORLDCUP),
reach-round (KXWCROUND), awards (KXWCAWARD), golden boot (KXWCGOALLEADER). A cheap
re-rate trade can live in a match market just as easily as a futures market.

For each candidate, answer four questions. **3 of 4 (question #2 mandatory) = tradeable.**

### 1. Cheap vs. a defensible value?
Is the current ask below where a sourced estimate — or the market itself — should
put it? You are **not** claiming it wins. You're claiming the *price* is too low for
the probability/attention it will command.
- Evidence: Elo-based fair value, recent form, squad value, or a plain mispricing
  (priced like a 0.1¢ minnow but clearly isn't one).

### 2. Is there a dated catalyst that re-rates the price UP — and when? *(mandatory)*
This is the heart of the trade. A catalyst moves the *price*, independent of the
final outcome:
- A favorable result (win/draw) in an upcoming match
- Group draw / bracket reveal that opens a soft path
- Confirmed lineup (star starts) at the lineup window
- A rival favorite stumbling — their price drops, yours re-rates up relative to it
- Narrative / sharp-money momentum into a known event date

**No identifiable catalyst before resolution → PASS.** A cheap contract that only
moves at settlement isn't a trade — it's a lottery ticket you can't sell.

### 3. Asymmetric payoff?
Downside is the full premium (bounded, small in dollars). Upside is a multiple on
the re-rate. At 0.4¢, a move to 2¢ is 5×; the most you lose is the premium. The
cheaper the entry, the more asymmetric — **that's the edge, not P(win).**

### 4. Can I exit?
A re-rate trade is only real if you can **sell into it**. Check order-book depth
(`GET /markets/{ticker}/orderbook`). If the book is thin now, will liquidity arrive
*with* the catalyst? (Results and lineup news pull buyers in.) If you can't foresee
an exit, PASS — you'd be stuck holding to resolution, which defeats the thesis.

## Score → size

| Questions passed | Action |
|---|---|
| 4 / 4 | Strong trade — size at top of the trade bucket |
| 3 / 4 (incl. #2 catalyst) | Tradeable — standard size |
| 3 / 4 but #2 weak / undated | Watchlist only — no catalyst, no entry |
| ≤ 2 | Pass |

**Sizing — trades are sized by dollars-at-risk, not Kelly.** Downside is the whole
premium, so size by what you'll shrug off losing. Cap the **entire trade bucket at
≤10% of bankroll**, any **single trade ≤5%**. A $2 stab on a 0.4¢ long-shot is 4%
of a $50 bankroll — inside the rail.

## Tournament long-shot — the specialization (not the universal screen)

For tournament-winner / reach-round markets, the five checks below are a good way
to *answer questions 1–2* — they don't replace them. Passing 3+ supports "cheap vs.
value (Q1)"; the group/match schedule supplies the dated catalysts (Q2).

- **Squad quality** — 5+ top-5-league starters, squad value >€100M, or a continental
  title in 8y. *(→ "not actually a minnow," Q1)*
- **Group-path viability** — soft #2 slot, no titan in the R32 draw. *(→ each matchday
  is a dated catalyst, Q2)*
- **Recent form** — ≥50% win rate, scoring regularly, no bad losses. *(→ Q1)*
- **Tournament DNA** — knockout experience / continental title. *(→ supports the
  re-rate holding through later rounds)*
- **Hedge compatibility** — already hold a match position on a group opponent? Bonus
  cross-hedge, never a blocker.

Treat the five gates as *one way to answer Q1–Q2 for tournament futures*, not as the
screen itself. The screen is the four questions above, and it runs on any market.

## Worked example — Ivory Coast (general screen, any-market framing)

| Q | Pass? | Why |
|---|---|---|
| 1. Cheap vs. value | ✅ | 0.4¢ prices them as a 0.1¢-floor minnow; they're AFCON champs with a top-5-league spine. The *price* is wrong — independent of whether they ever win the cup. |
| 2. Dated catalyst | ✅ | Beat Ecuador (Jun 14) → first price pop. Group advance, R32 — a *schedule* of re-rate events. |
| 3. Asymmetric | ✅ | Risk ~$1–2 (the premium). A pop to 2¢ is 5×; a QF run is 30×+. Bounded down, multiple up. |
| 4. Exitable | ✅ | Thin now, but a win pulls buyers + narrative in — sell into that, don't hold to July. |

4/4 → traded. **The plan was always to sell into the re-rate (see
`trade-exit-strategy.md`), not to need them to win the World Cup.**

## Pitfalls

- **Don't confuse "cheap" with "will win."** The screen finds *mispriced prices*,
  not winners. If your only reason is "they could win it," that's a conviction
  bet — size it as one or pass.
- **No catalyst = no trade.** Cheap + no upcoming price-moving event = a held
  lottery ticket. Watchlist it; enter when a catalyst comes into view.
- **The 0.1¢ floor is correctly-priced noise.** Genuine minnows (no squad, no path)
  belong there. Don't buy them hoping for a bounce that never comes.
- **Re-screen after each catalyst.** A trade you passed can go live when a draw
  lands or a favorite stumbles. A trade you *hold* must be re-evaluated the moment
  its catalyst fires — that's your exit window, per `trade-exit-strategy.md`.
