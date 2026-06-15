# Kairos

An autonomous agent that places FIFA World Cup 2026 bets on **Kalshi**
(CFTC-regulated, US-legal). It reasons narratively over an Elo-based
fair-value model, live X signals (via Grok), and cited contextual data
(via Perplexity), and acts only when it can state a sourced edge in one
sentence — otherwise it passes.

*Kairos* (καιρός) is the ancient Greek word for the opportune moment.
That is the agent's job: find the moment conditions align for a +EV bet,
and act then — or pass. A pass is a successful outcome, not a missed one.

Kairos runs on **Hermes Agent** (Nous Research): the `hermes` CLI provides
the LLM loop, the cron scheduler, and a Telegram gateway. Kairos itself is
an identity file (`SOUL.md`), two skills, and a handful of scripts — and the
only sanctioned order path is one rail-enforced script.

> **History:** Kairos began on Polymarket and migrated to Kalshi (Polymarket
> is US-restricted / view-only). The original plugin-based implementation
> (`src/`, `hermes_plugin/`) is **retired** and kept only for reference — the
> live agent runs on the skills + scripts below, and the legacy `kairos_*`
> plugin tools are dead on the Kalshi host. See [Legacy](#legacy).

## What it does

Every World Cup match has **three** Kalshi markets — home win, away win, and
the **draw** (`-TIE`). On a schedule, Kairos:

1. **Discovers** upcoming matches via the public Kalshi API, and checks the
   bet journal first so a free price check gates the expensive research.
2. **Prices** each side with a manual Poisson (Dixon-Coles-style) model fed
   by Elo ratings → P(home / draw / away).
3. **Cross-checks** the Elo blind spots — recent form, squad value, head-to-
   head, weather — via `web_search` on **Perplexity Sonar** (cited
   Transfermarkt / ESPN / FIFA, ~$0.005 a query).
4. **Gathers live X signals** — confirmed lineups, late injuries, team news —
   by delegating an `x_search` to **Grok**.
5. **Computes edge** = adjusted fair value − ask − fee, for *both* sides and
   the draw, then **places or passes** through the rail-enforced script.
6. **Settles**: reconciles P&L and tracks closing-line value (CLV — the
   leading indicator of edge), and watches open positions.

It hunts value on **underdogs, favorites the market underprices, and (in
observe mode) draws** — wherever the *price* is wrong, not wherever a team is
merely likely to win. "This team will win" is not an edge; the market already
knows.

## Architecture

Kairos is not a standalone program — it is a set of files Hermes loads. The
runtime layout (`~/.hermes/`), of which this repo holds the redacted
source-of-truth:

```
~/.hermes/
├── SOUL.md                          # identity + non-negotiable rails  (repo: docs/SOUL.example.md)
├── config.yaml                      # models, plugins, toolsets        (repo: docs/hermes_config.example.yaml)
├── skills/kairos-philosophy/        # discovery, FV model, sizing, placement, draws
│   ├── SKILL.md
│   ├── references/                  # elo-to-fv model, venue/heat, trade screen, tickers …
│   └── scripts/
│       ├── place_bet.py             # THE only order path — sizes the bet, enforces rails R1–R7, journals
│       └── draw_observe.py          # logs -TIE draw observations (observe mode)
├── skills/kairos-settlement/        # post-trade analysis (read-only except a deliberate cash-out)
│   └── scripts/
│       ├── reconcile.py / price_check.py   # portfolio + live price pulls
│       ├── floor_audit.py           # is the R7 conviction floor saving or costing money?
│       └── draw_audit.py            # CLV-first: is there a real, bettable edge in draws?
├── plugins/web/perplexity/          # web_search backend → Perplexity Sonar   (repo: plugins/web/perplexity/)
└── cron/jobs.json                   # the schedule (runtime-only, never committed)
```

In this repo, the skills live under `hermes_skills/kairos/{philosophy,settlement}/`
and are symlinked into `~/.hermes/skills/` at install. Credentials live in
`~/.hermes/.env` (model keys) and the project `.env` (Kalshi) and are never
committed.

**Operating model (cron jobs):**
- **prematch-scan** — find and bet +EV matches kicking off in ~24h.
- **daily-settle** — P&L, CLV, the floor + draw audits.
- **par-position-watch** — hourly open-position alerts, de-duplicated with an
  absolute-move floor so sub-penny noise stays silent.
- **lineup-watch** — late lineup / team-news polls.

## Models (hybrid, routed in `config.yaml`)

| Role | Model family | Why |
|---|---|---|
| Main loop — pre-match scans, triage, settlement | DeepSeek V4 Pro | cheap, capable reasoning; never touches xAI auth |
| Delegated `x_search` — live X signals | Grok (xAI) | X breaks lineup/injury news first |
| Contextual cross-checks — form, squad value, H2H, weather | Perplexity Sonar (via `web_search`) | cited, authoritative sources for ~$0.005/query |
| Aux utility — titles, compression, approvals | DeepSeek V4 Flash | cheapest path for non-reasoning chores |

The main loop runs on DeepSeek; for live X data it calls
`delegate_task("search X for …")` and Hermes spawns a Grok child that has
`x_search`, returning cited text the parent reasons over. **One research path
per layer** — contextual data on Perplexity, X-primary signals on Grok — never
both for the same question (a second path only adds cost). Exact model IDs live
in `~/.hermes/config.yaml`; pricing notes are in
[docs/hermes_config.example.yaml](docs/hermes_config.example.yaml).

## Fair value

Match prices come from a **manual Poisson (Dixon-Coles-style) model** driven by
Elo ratings — see
[hermes_skills/kairos/philosophy/references/elo-to-fv-manual.md](hermes_skills/kairos/philosophy/references/elo-to-fv-manual.md),
which ships calibration points to check the output. Tournament-winner,
reach-round, and group-qualification markets use their own relative-Elo-share
references. The draw probability the model already outputs is the fair value
for the `-TIE` market.

Draws are in **OBSERVE mode**: every `-TIE` is priced and logged
(`draw_observe.py`), but live draw bets stay off until `draw_audit.py` shows
positive closing-line value over enough games. The audit reconstructs the
pre-kickoff line from Kalshi candlesticks, so it converges in ~20 games rather
than waiting for dozens of *settled* draws.

## Safety — code-enforced rails (`place_bet.py`)

Every buy and sell goes through `place_bet.py`. It sizes the position, enforces
the rails, and journals **every** decision — placed, dry-run, *and* rejected.
The agent never picks a share count and never posts a raw order. A `rejected`
status is final; the agent passes rather than routing around it.

- **R1 — Sourced edge.** No source, no bet.
- **R2 — Fee-aware net edge.** edge = prob − price − fee, where the Kalshi
  taker fee = 0.07·price·(1−price). Requires ≥ 3¢ (≥ 5¢ when FV ≥ 70%; ≥ 8¢ in
  the 0.40–0.45 borderline band).
- **R3 — Sizing.** Confidence-scaled Kelly (fraction = stated confidence,
  clamped to 0.50–0.75) of **total capital** (cash + open WC exposure), applied
  to net_edge/(1−price); capped at **25% of total capital** and at cash above
  the $5 floor.
- **R4 — Trades.** A re-rate trade is sized by dollars-at-risk (`--cost`),
  capped at 5% of total capital, and only on contracts ≤ 15¢.
- **R5 — Confidence floor 0.50.**
- **R6 — Cash floor $5** — no buy may take cash below it.
- **R7 — Conviction fair-value floor.** A conviction bet rides to resolution,
  so it requires **FV ≥ 0.40** (≥ 0.45 normally; the 0.40–0.45 band needs ≥ 8¢
  net edge). FV < 0.40 is forbidden as a conviction hold no matter how large the
  edge — it must be a `≤15¢` trade or a pass. Edge proves the *price* is wrong;
  it does not prove the side *wins*. (Added after a sub-40%-FV underdog with a
  real edge was ridden to a loss.)

Trades are exempt from R2/R7 — they exit on a catalyst, not at resolution.

**Two kills stay on the agent** (they need live match context the script can't
see): no order within 60s of a goal / red card / VAR, and no order on a >5%
price move in the last 30s.

**Integrity rules** guard the facts the reasoning rests on:
- Never report a score not verified this turn — a price move is not a scoreline.
- Never invent a venue or climate — anchor every stadium / city / temperature
  to the venue reference or a fetch this turn.
- Be honest about capability — never confirm a config/cron change a chat message
  cannot make, and re-fetch before declaring a market dead instead of guessing.

`--dry-run` makes any placement reason + journal without sending the order.
Manual stop: kill the `hermes` gateway from any device.

## Install + run

Full setup is in **[docs/HERMES_WIRING.md](docs/HERMES_WIRING.md)**. In short:
install Hermes; put your model keys (DeepSeek, xAI, Perplexity) in
`~/.hermes/.env` and Kalshi creds in the project `.env`; copy
`docs/SOUL.example.md` → `~/.hermes/SOUL.md`; merge
`docs/hermes_config.example.yaml` → `~/.hermes/config.yaml`; install the skills
and the Perplexity web plugin; wire the Telegram gateway; and schedule the cron
jobs. Validate Kalshi auth read-only with `python scripts/kalshi_shadow_check.py`
before going live, and keep `--dry-run` on until the reasoning looks right.

## Legacy

`src/` (a typed Kalshi/Polymarket client plus sizing, fair-value, and settlement
modules), `hermes_plugin/`, and `pyproject.toml` are the **original
plugin-based implementation**, retired after the Kalshi cutover and the move to
a skills + scripts design. The live agent does not import them, and the
`kairos_*` plugin tools they registered are dead on the Kalshi host (the
ESPN-sourced match-state helpers aside). They remain for history and reference.
Likewise, the `POLYMARKET_*`, `KAIROS_DRY_RUN`, and milestone-bankroll variables
in `.env.example` are legacy: Kalshi is the only venue, sizing is on live total
capital (no fixed-bankroll milestone floors), and dry-running is the `--dry-run`
flag on `place_bet.py`.
