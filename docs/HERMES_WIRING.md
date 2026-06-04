# Wiring Kairos into Hermes

This is the install + run guide. It replaces an earlier doc that invented
a `hermes.toml` config interface that does not exist. Hermes uses YAML
(`~/.hermes/config.yaml`), and the canonical entry point is the `hermes`
CLI plus cron jobs — not an embedded Python loop.

## Mental model

Kairos is **not a standalone program**. It is three artifacts that plug
into Hermes:

| Artifact | What it does | Lives at |
|---|---|---|
| `hermes_plugin/` | Wraps `src/polymarket_tool.py` + `src/sports_feed.py` as LLM-callable tools (`kairos_evaluate_bet`, `kairos_get_match_state`, etc.) | `~/dev/kairos/hermes_plugin/` symlinked into `~/.hermes/plugins/kairos/` |
| `hermes_skills/kairos/philosophy/SKILL.md` | The betting philosophy as a Hermes skill, loadable on demand | `~/dev/kairos/hermes_skills/` symlinked into `~/.hermes/skills/` |
| `docs/SOUL.example.md` | Kairos identity, auto-loaded into every session | Copy to `~/.hermes/SOUL.md` |

Plus two pieces from Hermes itself:

- **Bundled `polymarket` skill** for read-only Gamma/CLOB/Data API queries
  (replaces our deleted `gamma_client.py`)
- **Built-in `cronjob` tool** for scheduling pre-match scans and in-play polls
- **Built-in Telegram gateway** for alerts (replaces our deleted `notifications.py`)

The `hermes` CLI is the entry point. There is no `python -m src.main` for
the real agent (only for `--smoke-test`).

## Step 1: install Hermes + DeepSeek + xAI

```bash
cd ~/dev/kairos
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install hermes-agent
hermes --version
```

### Why two providers (DeepSeek + xAI hybrid)

Kairos uses a hybrid model setup:

- **DeepSeek V4 Flash** ($0.14/M input, $0.28/M output) runs the main
  agent loop — the narrative reasoning, the bet decisions, the tool calls
  to the Kairos plugin. DeepSeek V4 made their 75% discount permanent on
  May 22, 2026 and competes with Grok 4.3 on the reasoning benchmarks
  that matter for our task.
- **Grok 4.3 with `reasoning_effort=none`** (aliased as `grok-4-fast-non-reasoning`)
  runs delegated `x_search` calls only. `x_search` is xAI-exclusive — no
  other provider has X firehose access. We pay $5/1000 calls + tokens at
  zero reasoning overhead.

Total projected cost: **~$10-13/month** at our volume (50 reasoning calls
+ 48 x_search calls per day). vs. ~$50-80/month if we ran everything on
Grok 4.3.

**Don't use the OAuth path** (`hermes auth add xai-oauth`). It's gated to
SuperGrok Heavy ($300/mo) only on standard accounts; see
[hermes-agent#26847](https://github.com/NousResearch/hermes-agent/issues/26847)
and [#27228](https://github.com/NousResearch/hermes-agent/issues/27228).
Also, xAI's $175/mo data-sharing credits were discontinued in May 2026 —
the paid API key is the only working path, and it's cheap enough for our
use case to not matter.

### Get both API keys

1. **DeepSeek key:** sign up at https://platform.deepseek.com, generate
   an API key (starts with `sk-`). Put in `~/.hermes/.env`:
   ```
   DEEPSEEK_API_KEY=sk-...your-deepseek-key...
   ```
2. **xAI key:** sign up at https://x.ai/api, generate a key (starts with
   `xai-`). Put in the same file:
   ```
   XAI_API_KEY=xai-...your-xai-key...
   ```
3. Set Kairos's other shared env vars in the same file:
   ```
   POLYMARKET_PRIVATE_KEY=0x...
   POLYMARKET_FUNDER_ADDRESS=0x...
   KAIROS_DRY_RUN=true
   KAIROS_STARTING_BANKROLL_USD=50
   # Isolate Kairos's gbrain brain from any other gbrain brain on the
   # machine. gbrain appends `.gbrain`, so this puts it at ~/.kairos/.gbrain,
   # completely separate from a default ~/.gbrain knowledge base.
   GBRAIN_HOME=~/.kairos
   ```
   Also `export GBRAIN_HOME=~/.kairos` in your shell so manual `gbrain`
   commands (init, sync) target the Kairos brain, not the default one.
4. Set the default model:
   ```bash
   hermes model
   # interactive picker → DeepSeek → deepseek-chat
   ```
5. Verify: `hermes model --show` should report `deepseek-chat` on the
   `deepseek` provider.

### Critical pre-launch test: confirm BOTH providers work

The hybrid only works if both keys are valid. Test in order:

```bash
# DeepSeek (main reasoning)
hermes chat -q "Say 'deepseek works' if you can hear me."

# xAI x_search (delegated)
hermes chat -q "Use x_search to find the last 3 tweets from @FabrizioRomano. Just list the URLs."
```

If DeepSeek errors → check the key + spelling of provider name in config.
If x_search errors → your xAI account is missing search access. There's no
workaround; `web_search` is not a substitute for the X firehose. Investigate
at https://x.ai/api before continuing.

### About the Grok model alias

xAI retired `grok-4.1-fast` (and 7 other slugs) on **May 15, 2026**. The
old names still work but transparently alias to `grok-4.3` with different
default reasoning levels:

| Alias | Maps to |
|---|---|
| `grok-4-fast-non-reasoning` | `grok-4.3` with `reasoning_effort=none` (cheapest) |
| `grok-4-fast-reasoning` | `grok-4.3` with `reasoning_effort=low` |
| `grok-4.3` | full reasoning, most expensive |

For Kairos's delegated x_search calls, we use `grok-4-fast-non-reasoning`.
The child agent's only job is "search X and summarize." It doesn't need
chain of thought, and the zero-reasoning alias saves us output tokens
(billed at $2.50/M).

## Step 2: copy/merge `~/.hermes/config.yaml`

A template lives at `~/dev/kairos/docs/hermes_config.example.yaml`. The
essentials:

```yaml
model:
  provider: deepseek
  default: deepseek-chat       # V4 Flash — cheap reasoning

# Delegated subagents (e.g. for x_search) run on this model instead.
delegation:
  provider: xai
  model: grok-4-fast-non-reasoning   # → grok-4.3 with reasoning_effort=none

plugins:
  enabled:
    - kairos

skills:
  enabled:
    - polymarket          # bundled, covers Gamma + CLOB + Data API reads
    - kairos:philosophy

mcp_servers:
  gbrain:
    command: gbrain
    args: ["serve"]
    env:
      PATH: ${PATH}
      HOME: ${HOME}
      GBRAIN_HOME: ${GBRAIN_HOME}   # isolates Kairos's brain (see Step 1)

terminal:
  backend: local

timezone: America/Chicago
```

Initialize the Kairos brain once, with `GBRAIN_HOME` set so it lands in its
own home and not the default `~/.gbrain`:
```bash
export GBRAIN_HOME=~/.kairos
gbrain init --pglite          # creates the brain at ~/.kairos/.gbrain
gbrain doctor --fast          # should report THIS brain, not another
```

Verify after editing:
```bash
hermes config show
hermes plugins list
hermes mcp list
hermes mcp test gbrain
```

### Model routing summary

| Task | Model | Why |
|---|---|---|
| Default main loop (pre-match scans) | `deepseek-chat` (V4 Flash, $0.14/$0.28 per M) | Triage + filtering, most calls won't bet |
| High-stakes deciders (halftime, live polls) | `deepseek-reasoner` (V4 Pro, $0.435/$0.87 per M) | Each call has real bet-placing potential |
| Auxiliary slots (compression, titles, MCP routing) | inherit Flash via `auto` | Housekeeping, quality doesn't matter |
| Vision | unused | Kairos has no image inputs |
| Delegated x_search calls | `grok-4-fast-non-reasoning` ($1.25/$2.50 per M + $5/1k search) | xAI exclusive; alias = `grok-4.3` with `reasoning_effort=none` for cheapest x_search |

Pro override on specific cron jobs uses `--model deepseek-reasoner --provider deepseek`. See Step 7.

## Step 3: install the Kairos plugin

```bash
# Symlink the in-repo plugin directory into Hermes' plugins folder
mkdir -p ~/.hermes/plugins
ln -s ~/dev/kairos/hermes_plugin ~/.hermes/plugins/kairos

# Enable
hermes plugins enable kairos
hermes plugins list   # verify "kairos" shows enabled

# Verify the tools registered correctly
hermes chat -q "List your tools that start with kairos_"
```

You should see eleven tools: `kairos_find_markets`, `kairos_fair_value`,
`kairos_evaluate_bet`, `kairos_get_bankroll`, `kairos_get_market_price`,
`kairos_check_velocity`, `kairos_list_matches`, `kairos_get_match_state`,
`kairos_reconcile_positions`, `kairos_performance`, `kairos_vet_signal`.

Note: `kairos_find_markets` does World Cup market discovery via Polymarket's
public Gamma API, so Kairos does NOT depend on Hermes's bundled `polymarket`
skill (which isn't present in every install).

## Step 4: install the philosophy skill

```bash
mkdir -p ~/.hermes/skills/kairos
ln -s ~/dev/kairos/hermes_skills/kairos/philosophy ~/.hermes/skills/kairos/philosophy

hermes skills list | grep kairos
# Should see kairos:philosophy

# Test that it loads
hermes chat -q "/kairos:philosophy - Summarize the hard rails in one sentence."
```

## Step 5: copy SOUL.md

```bash
cp ~/dev/kairos/docs/SOUL.example.md ~/.hermes/SOUL.md
```

Hermes auto-loads this on every session start. Edit later if Kairos's
identity needs to drift.

## Step 6: configure Telegram gateway

```bash
hermes gateway setup
# pick Telegram, paste bot token from @BotFather, paste your user ID
hermes gateway install   # installs as launchd (macOS) / systemd (Linux)
```

This replaces the old `src/notifications.py` we deleted. You now get:
- Cron jobs auto-deliver to Telegram
- The `send_message` tool inside agent reasoning
- Bidirectional chat with the agent from your phone (slash commands etc.)

## Step 7: schedule the cron jobs

Two cron jobs cover all of Kairos's decision windows. Both follow the
**delegation pattern** for X data: the main agent runs on DeepSeek (no
direct `x_search` access) and delegates to a Grok child agent when it
needs live X signals.

### Pre-match scan (every 4 hours, Flash default)

Runs on the cheap Flash model since most matches won't produce a bet —
this is triage. Per-bet quality is fine on Flash; the Pro override goes
on halftime where each call has higher chance of placing a real bet.

```bash
hermes cron add "0 */4 * * *" \
  "Scan FIFA World Cup matches kicking off in the next 24 hours. \
First, call kairos_list_matches with today and tomorrow's dates in YYYYMMDD format \
to get the list of matches with ESPN event_ids and kickoff times. \
Then for each match in that window: \
(1) call kairos_get_match_state with the event_id to get authoritative metadata, \
(2) call kairos_find_markets to discover the relevant Polymarket markets and their token IDs + current prices, \
(3) call delegate_task with a query like 'search X for confirmed starting lineups, \
last-minute injury news, weather, and referee appointment for {home} vs {away} \
World Cup match on {date}. Return what you find with the specific tweet URLs as \
citations. Discard anonymous accounts and unsourced rumors.' \
(4) consult the kairos:philosophy skill for sizing math and hard rails, \
(5) call kairos_get_bankroll to know the active confidence floor, \
(6) for any market with a defensible edge (state it in one sentence), \
call kairos_evaluate_bet with the required fields. \
Pass on anything that does not meet the philosophy's confidence and source bars. \
Write a brief summary of what you considered to memory via the memory tool." \
  --skill kairos:philosophy \
  --deliver telegram \
  --name kairos-prematch-scan
```

### Halftime poll (every 2 minutes, Pro override)

Runs on V4 Pro because each call has a real chance of placing a bet and
the windows are time-sensitive. Adds ~$1-3/month over Flash but worth it
where bet quality actually matters.

```bash
hermes cron add "*/2 * * * *" \
  --model deepseek-reasoner --provider deepseek \
  "If a World Cup match is currently at halftime (check with \
kairos_get_match_state), fetch its state and consider an adjustment bet. \
Skip if no match is at halftime or if kairos_check_velocity reports either \
kill rail tripped. If conditions are right, call delegate_task to search X \
for any halftime news (formation changes, injuries, manager interviews), \
then call kairos_evaluate_bet if a defensible edge exists. Otherwise pass." \
  --skill kairos:philosophy \
  --deliver telegram \
  --name kairos-halftime-poll
```

Start with pre-match only. Add halftime after you've watched the pre-match
loop run cleanly on real friendlies in DRY_RUN.

### Daily settlement + performance report

This is the instrument that tells you whether the edge is real (and whether
to scale the bankroll). Run it once a day; it settles resolved positions and
reports P&L + closing-line value.

```bash
hermes cron add "0 9 * * *" \
  "Call kairos_reconcile_positions to settle any resolved markets, then \
report the performance summary: settled count, win rate, net P&L, ROI, and \
especially average CLV and positive-CLV rate. CLV is the signal that matters \
on a small sample. Write the summary to memory." \
  --deliver telegram \
  --name kairos-daily-settle
```

### A note on cron timing (event-driven beats flat intervals)

The flat `0 */4 * * *` pre-match schedule is a starting point, but it will
sometimes miss the single highest-value signal: confirmed lineups, which post
~1 hour before kickoff. The better pattern, once you've watched it run, is to
have the agent read the day's fixtures (via kairos_list_matches) and schedule
a per-match scan ~70 minutes before each kickoff. You can do this by having a
lightweight morning cron call kairos_list_matches and then create one-shot
cron entries for each match that day. Until you build that, set the pre-match
interval tighter on match days (e.g. hourly) so you don't sit in a 4-hour gap
across a kickoff.

Also gate the halftime poll to match windows rather than running it 24/7 —
either narrow the cron hours to when matches actually play, or have the poll
no-op cheaply when kairos_list_matches shows nothing live.

Manage jobs:
```bash
hermes cron list
hermes cron pause kairos-halftime-poll
hermes cron resume kairos-halftime-poll
hermes cron remove kairos-halftime-poll
```

Outputs land at `~/.hermes/cron/output/<job_id>/<timestamp>.md` and (if
`--deliver telegram`) get DMed to you.

## Step 8: verify Obsidian sees your audit trail

Open Obsidian. Add a new vault and point it at `~/dev/kairos/`. You should
see:
- `logs/` — markdown per placed/dry-run bet, plus `_kills.md` for everything
  rejected and `_events.md` for agent lifecycle events
- `brain/` — gbrain's knowledge graph (markdown, indexed by gbrain's local PGLite)

## Verify the offline smoke test still passes

After all the above, run the offline validation:

```bash
cd ~/dev/kairos
python3 -m src.main --smoke-test
```

Should print `12/12 sub-tests passed` and `=== Smoke test passed ===`.
This proves sizing + hard rails work in isolation, independent of Hermes.

## When something is off

- **HTTP 403 on inference from xAI:** you're on the OAuth path with standard
  SuperGrok. Switch to API key (Step 1).
- **DeepSeek auth errors:** confirm `DEEPSEEK_API_KEY` is set in
  `~/.hermes/.env` and starts with `sk-`. Try `hermes chat -q "test"` to
  isolate from cron complexity.
- **`x_search` errors:** your xAI tier doesn't include search. There is no
  workaround. Verify your account at https://x.ai/api.
- **Agent never calls x_search:** check that the `delegation:` block is
  present in `~/.hermes/config.yaml` and points at xAI. If x_search lives
  on the main model (DeepSeek), the agent can't find it — make sure your
  cron prompt explicitly says "delegate a task to search X for ..." so
  the main agent spawns the child correctly.
- **Plugin tools don't show up:** confirm symlink, then
  `hermes plugins enable kairos && hermes plugins list`. Check that
  `~/dev/kairos/hermes_plugin/__init__.py` exists and has the `register`
  function.
- **gbrain MCP server won't start:** Hermes strips most env vars from MCP
  subprocesses. Make sure required vars (`PATH`, `HOME`, any DB credentials)
  are explicitly listed under `mcp_servers.gbrain.env:` in
  `~/.hermes/config.yaml`. Test with `hermes mcp test gbrain`.
- **Polymarket tool errors on first real bet:** re-read
  [PRIVATE_KEY_EXPORT.md](PRIVATE_KEY_EXPORT.md) and confirm the wallet
  address in `.env` matches the wallet connected to Polymarket.
- **Anything unclear:** flip `KAIROS_DRY_RUN=true` and re-run the smoke
  test to confirm the offline stack is healthy. That isolates whether the
  problem is in Kairos's logic or in the Hermes wiring.
