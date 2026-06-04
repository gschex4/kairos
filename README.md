# Kairos

A Hermes-native agent that places FIFA World Cup 2026 bets on Polymarket
using narrative reasoning (DeepSeek V4) over live X data (Grok, delegated).

*Kairos* (καιρός) is the ancient Greek word for the opportune moment.
That is the agent's job: find the moment conditions align for a bet, and
act then.

## What it does

The agent operates in three decision windows where an LLM has an edge
over latency-optimized market-maker bots:

1. **Pre-match (12 to 24 hours before kickoff)** — outright winners, top
   scorer, prop bets driven by lineup news from X.
2. **Between halves (the 15-minute halftime window)** — adjustments based
   on first-half trajectory.
3. **Mid-trajectory (during play, narrow conditions)** — when a team is
   dominating but the market hasn't fully repriced. Skipped during the
   60-second windows after goals, red cards, or VAR events.

Sizing is floating: 10% of current bankroll, half-Kelly under confidence-
tiered ceilings, with bankroll-milestone confidence floors that tighten
as the bankroll shrinks. Hard rails are code-enforced, not prompt-
enforced. `KAIROS_DRY_RUN=true` lets the agent reason and log without
placing real orders.

## Architecture

Kairos is **not a standalone program.** It is three artifacts that plug
into Hermes Agent (NousResearch):

```
~/dev/kairos/
├── hermes_plugin/              # Hermes plugin — symlinked into ~/.hermes/plugins/kairos
│   ├── plugin.yaml
│   ├── __init__.py             # register(ctx) — Hermes entry point
│   ├── schemas.py              # JSON Schemas the LLM sees
│   ├── tools.py                # Handler functions (thin shim)
│   └── README.md
├── hermes_skills/kairos/
│   └── philosophy/SKILL.md     # The betting philosophy, loadable as /kairos:philosophy
├── src/                        # Real logic — plugin imports from here
│   ├── config.py               # typed env loader (Kairos-only vars)
│   ├── gamma_client.py         # Polymarket Gamma API — World Cup market discovery
│   ├── polymarket_tool.py      # bet placement + safety stack
│   ├── fair_value.py           # slow engine — Dixon-Coles Poisson from Elo
│   ├── sizing.py               # half-Kelly + tier ceilings + milestone floors
│   ├── market_velocity.py      # event window + 30s velocity rails
│   ├── settlement.py           # P&L + CLV reconciliation (the edge instrument)
│   ├── position_ledger.py      # double-bet guard + performance summary
│   ├── untrusted.py            # prompt-injection defense
│   ├── sports_feed.py          # ESPN (primary) + football-data.org backup
│   ├── logging_setup.py        # markdown logs for Obsidian + kill log
│   └── main.py                 # offline smoke test only
├── docs/
│   ├── HERMES_WIRING.md        # install + cron job recipes
│   ├── BETTING_PHILOSOPHY.md   # human-readable copy of the philosophy
│   ├── PRIVATE_KEY_EXPORT.md   # Polymarket wallet key export
│   ├── TRANSFER_TO_PC.md       # Mac to PC tournament handoff
│   ├── SOUL.example.md         # copy to ~/.hermes/SOUL.md
│   └── hermes_config.example.yaml  # copy/merge into ~/.hermes/config.yaml
├── brain/                      # gbrain knowledge graph (Obsidian vault)
└── logs/                       # per-bet markdown + _kills.md + _events.md
```

What lives outside `~/dev/kairos/`:

- `~/.hermes/config.yaml` — Hermes runtime config (provider, plugins, MCP servers)
- `~/.hermes/.env` — `XAI_API_KEY`, `POLYMARKET_PRIVATE_KEY`, etc.
- `~/.hermes/SOUL.md` — Kairos identity
- `~/.hermes/plugins/kairos` → symlink to `~/dev/kairos/hermes_plugin/`
- `~/.hermes/skills/kairos/philosophy` → symlink to `~/dev/kairos/hermes_skills/kairos/philosophy/`
- `~/.hermes/cron/jobs.json` — scheduled pre-match scans + halftime polls (auto-managed)

Hermes provides: the `hermes` CLI, the LLM loop, the cron scheduler, the
Telegram gateway, the bundled `polymarket` skill for Gamma/CLOB reads,
and MCP auto-discovery (which picks up gbrain as `mcp_gbrain_*` tools).

## Model setup (hybrid: DeepSeek + Grok)

Three roles, three models, routed in `~/.hermes/config.yaml`:

| Role | Model | Cost / M | Where set |
|---|---|---|---|
| Default main loop (pre-match scans, triage) | `deepseek-chat` (V4 Flash) | $0.14 in / $0.28 out | `model.default` |
| High-stakes deciders (halftime, live polls) | `deepseek-reasoner` (V4 Pro) | $0.435 in / $0.87 out | per-cron `--model` override |
| Delegated `x_search` calls | `grok-4-fast-non-reasoning` | $1.25 in / $2.50 out + $5/1k search | `delegation` block |

The agent's main loop runs on DeepSeek (cheap, capable enough). When it
needs live X data, it calls `delegate_task("search X for ...")` and
Hermes spawns a child agent on Grok, which has `x_search`. The child
returns synthesized text with citations; the main agent reasons over it
and decides whether to bet. DeepSeek never touches xAI auth; the kairos
plugin runs on the parent context unchanged.

Why `grok-4-fast-non-reasoning`: xAI retired `grok-4.1-fast` on May 15,
2026. The old name is now a transparent alias to `grok-4.3` with
`reasoning_effort=none` — the cheapest path to `x_search` access.

Projected cost at our volume (~50 reasoning + 48 x_search calls/day):
**~$10-15/month total.** Pricing is detailed in
`docs/hermes_config.example.yaml`. Both API keys live in `~/.hermes/.env`.

## Install + run

Full step-by-step lives in **[docs/HERMES_WIRING.md](docs/HERMES_WIRING.md)**.
TL;DR:

```bash
cd ~/dev/kairos
python3 -m venv .venv && source .venv/bin/activate
pip install -e . hermes-agent

# Offline smoke test (proves sizing + hard rails work; no Hermes needed)
python3 -m src.main --smoke-test

# Then per HERMES_WIRING.md:
# 1. Get xAI API key, paste into ~/.hermes/.env
# 2. Copy/merge docs/hermes_config.example.yaml → ~/.hermes/config.yaml
# 3. Symlink hermes_plugin/ + hermes_skills/ into ~/.hermes/
# 4. Verify x_search works (critical pre-launch test)
# 5. Configure Telegram gateway
# 6. Schedule cron jobs for pre-match + halftime
```

There is no `python -m src.main` for the real agent. The agent runs
under `hermes` and is driven by cron jobs. `src/main.py` is only for the
offline smoke test.

## Moving to the PC for the tournament

See [docs/TRANSFER_TO_PC.md](docs/TRANSFER_TO_PC.md). Short version:
push to a private git repo, clone on the PC, re-create `~/.hermes/.env`
on the new machine, redo the plugin + skill symlinks, install Hermes,
configure cron + gateway, configure the PC not to sleep.

## Pre-launch timeline

15 days from today (May 27) to kickoff (June 11). Suggested ramp:

| Days | Work |
|---|---|
| 1-2 | Install Hermes locally, configure xAI + DeepSeek keys, **verify x_search works on your tier** (critical gate). Smoke test passes. |
| 3 | Install plugin + skill symlinks, gbrain MCP, verify `hermes plugins list` and `hermes mcp test gbrain`. |
| 4 | Configure Telegram gateway, verify bidirectional chat. |
| 5 | Add bundled `polymarket` skill, copy `SOUL.md`. |
| 6 | Register the pre-match cron job. First dry-run scan. |
| 7-10 | DRY_RUN against late-May / early-June international friendlies. Review every cron output for reasoning quality. Adjust philosophy as needed. |
| 11 | Optional: enable Langfuse observability plugin for full LLM trace capture. |
| 12-14 | Final paper-trades. Push code + config to private repo. Transfer to PC laptop per `TRANSFER_TO_PC.md`. |
| 15 (Jun 11) | Flip `KAIROS_DRY_RUN=false`. Watch the first match closely. |

## What's solid vs what to verify

**Solid and tested (offline):**
- Project structure, config loading, env handling
- Hermes plugin registration shape (plugin.yaml + register(ctx) + json.dumps handlers)
- `PolymarketTool` hard rails (basic validation, sources required)
- Philosophy sizing in `src/sizing.py` — floating 10% cap, half-Kelly,
  confidence tiers, milestone floors, exotic halving
- Code-enforced market velocity + event-window detection over live
  Polymarket Data API trades
- Markdown logging that Obsidian reads + `_kills.md` + per-bet sizing
  and velocity audits
- Smoke test (`python3 -m src.main --smoke-test`) — 12 sub-tests, 12 pass

**To verify at install time (require live network + accounts):**
- `XAI_API_KEY` has `x_search` access (critical pre-launch test in
  HERMES_WIRING.md Step 1)
- Polymarket Data API trade response shape matches what `_fetch_recent_trades`
  expects (defensive parsing handles common variations)
- gbrain MCP server starts under Hermes' filtered env (test with
  `hermes mcp test gbrain`)
- Bundled `polymarket` skill is installed (`hermes skills list | grep polymarket`)
- ESPN's hidden API schema for `fifa.world` matches `sports_feed.py`
  (defensive parsing; will degrade gracefully)

## Safety summary

All of the following are enforced in code, not in the prompt. See
`src/sizing.py`, `src/market_velocity.py`, and
`src/polymarket_tool.py:_check_basic_rails`.

**Floating per-bet cap:**
- 10% of current bankroll, recomputed on every bet
- Within that, half-Kelly capped by confidence tier:
  - 0.60-0.65 confidence: up to 4% of bankroll
  - 0.65-0.75: up to 7%
  - 0.75+: up to the full 10%
- Exotic / thin markets get their computed size halved
- Below 3% of bankroll → pass (not worth placing)
- Paranoid absolute hard ceiling on top (default 20% of starting bankroll)

**Milestone confidence floors:**
- > 60% bankroll remaining: 0.60 floor
- 40-60% remaining: 0.65 floor
- 20-40% remaining: 0.80 floor
- < 20% remaining: 0.85 floor (near-hibernation)

**Hard rails:**
- No bets within 60s of a market event. Live trade-history fetch infers
  events from sharp single-trade jumps (≥ 2%). Agent can override via
  `seconds_since_last_event` when it has direct knowledge (e.g. a goal
  tweet seen on x_search).
- No bets if the market moved > 5% net in the last 30 seconds.
- No bets without reasoning + at least one cited source.
- No bets with zero or negative computed edge.
- No bets above the absolute hard ceiling.

**Always:**
- `KAIROS_DRY_RUN` flag — reasons and logs but doesn't place orders.
- Manual stop — kill the `hermes` process from any device.
- Every kill logged to `logs/_kills.md` with reason and full reasoning.

No auto-shutoffs tied to loss thresholds, by design. The floating cap and
milestone floors auto-tighten as bankroll shrinks.
