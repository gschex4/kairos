# Transferring Kairos from your MacBook to your PC laptop

The plan is to build and iterate on the MacBook, then move to the extra
PC laptop and leave it running 24/7 during the World Cup. This is the
punch list for that handoff.

The PC needs to recreate:
1. The Python project at `~/dev/kairos/`
2. The Hermes config + secrets at `~/.hermes/`
3. The plugin and skill symlinks
4. The DeepSeek + xAI API keys
5. Polymarket wallet credentials
6. Keep-alive (no sleep, restart on reboot)
7. Bidirectional access (you can stop/start it from your phone via Telegram)

## Before transfer (still on MacBook)

1. Confirm the agent runs cleanly on Mac in DRY_RUN. Run one full pre-match
   cron cycle against a friendly and read the output. If the agent makes
   sensible decisions on Mac, it'll behave the same on PC.

2. Commit everything to git. Verify `.env` is NOT staged:

   ```bash
   cd ~/dev/kairos
   git status                # `.env` should be untracked/ignored, never staged
   git add .
   git commit -m "Working DRY_RUN build on macOS"
   ```

3. Push to a private GitHub repo. (Strongly preferred over USB / rsync —
   you'll want to push small fixes during the tournament without physical
   access to the PC.)

   ```bash
   gh repo create kairos --private --source=. --remote=origin --push
   # or via the GitHub web UI then:
   #   git remote add origin git@github.com:you/kairos.git
   #   git push -u origin main
   ```

## On the PC laptop

### 1. Install prerequisites

- **Python 3.11+**
  - Windows: download from https://www.python.org/downloads/ and CHECK
    "Add Python to PATH" in the installer.
  - Linux: `sudo apt install python3.11 python3.11-venv`
- **git** — Windows: https://git-scm.com/download/win. Linux: `apt install git`.
- **gbrain** — install per the [gbrain repo](https://github.com/garrytan/gbrain).
  PGLite-local mode needs no extra services.

Verify:
```
python --version    # 3.11 or higher
git --version
gbrain --version
```

### 2. Clone the project + install Python deps

```bash
mkdir -p ~/dev
cd ~/dev
git clone <your-private-repo-url> kairos
cd kairos

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -e . hermes-agent
```

### 3. Re-create the Kairos `.env`

The `.env` file is NOT in git (correct). On the PC:

```bash
cp .env.example .env
```

Then edit `.env` and paste from your password manager:
- `POLYMARKET_PRIVATE_KEY`
- `POLYMARKET_FUNDER_ADDRESS`
- Keep `KAIROS_DRY_RUN=true` for the first runs

Do not retype from your MacBook screen — use the password manager.

### 4. Run the offline smoke test FIRST

Before touching Hermes:
```bash
python -m src.main --smoke-test
```

Should print `12/12 sub-tests passed`. This validates the Python stack
and your `.env` independently of Hermes. If it fails, fix it here —
debugging Hermes wiring is harder.

### 5. Configure Hermes (`~/.hermes/`)

```bash
# Make the config dir
mkdir -p ~/.hermes

# Copy the example config
cp docs/hermes_config.example.yaml ~/.hermes/config.yaml

# Copy SOUL.md (Kairos identity)
cp docs/SOUL.example.md ~/.hermes/SOUL.md
```

Create `~/.hermes/.env` with both API keys (these live OUTSIDE the
project's .env — they're owned by Hermes):

```
DEEPSEEK_API_KEY=sk-...
XAI_API_KEY=xai-...
```

Verify Hermes sees the config:
```bash
hermes --version
hermes config show
hermes model --show   # should report deepseek-chat on deepseek provider
```

### 6. Symlink the Kairos plugin and skill into `~/.hermes/`

```bash
# Plugin
mkdir -p ~/.hermes/plugins
# Windows: use `mklink /D` instead of `ln -s`
ln -s ~/dev/kairos/hermes_plugin ~/.hermes/plugins/kairos
hermes plugins enable kairos
hermes plugins list   # verify "kairos" enabled

# Skill
mkdir -p ~/.hermes/skills/kairos
ln -s ~/dev/kairos/hermes_skills/kairos/philosophy ~/.hermes/skills/kairos/philosophy
hermes skills list | grep kairos
```

(On Windows in PowerShell with admin: `New-Item -ItemType SymbolicLink
-Path C:\Users\you\.hermes\plugins\kairos -Target C:\Users\you\dev\kairos\hermes_plugin`.
Or just `xcopy /E` the directory if symlinks are a pain.)

### 7. Register gbrain MCP server (isolated brain)

Kairos uses its own gbrain brain, separate from any other gbrain brain.
On a kairos-only PC this is automatic (no other brain exists), but set
`GBRAIN_HOME` anyway so it's explicit and future-proof:

```bash
export GBRAIN_HOME=~/.kairos          # add to ~/.hermes/.env too
gbrain init --pglite                  # brain at ~/.kairos/.gbrain
hermes mcp test gbrain                # confirms the config.yaml entry works
hermes mcp list                       # should show gbrain + mcp_gbrain_* tools
```

The `brain/` markdown files came over via git, so any seeded knowledge is
preserved. gbrain rebuilds its local search index on first run.

### 8. Configure Telegram gateway

You're going to manage the agent from your phone during the tournament,
so this is required, not optional.

```bash
hermes gateway setup
# Pick Telegram. You'll need:
#   - bot token from @BotFather (DM your bot once before this step)
#   - your Telegram user ID
hermes gateway install   # launchd (macOS) / systemd (Linux) / Task Scheduler (Windows)
```

After install, DM your bot `/help` to confirm it responds. From there you
can also `/cron list`, `/cron pause kairos-prematch-scan`, etc.

### 9. Run the critical pre-launch verifications

```bash
# DeepSeek auth works
hermes chat -q "Say 'deepseek works' if you can hear me."

# xAI x_search works (the entire edge)
hermes chat -q "Use x_search to find the last 3 tweets from @FabrizioRomano. Just list the URLs."
```

Both must pass. If x_search fails, your xAI account is missing search
access — there's no workaround.

### 10. Recreate the cron jobs

```bash
# Pre-match scan (Flash, default model)
hermes cron add "0 */4 * * *" \
  "..." \
  --skill polymarket --skill kairos:philosophy \
  --deliver telegram --name kairos-prematch-scan

# Halftime poll (Pro override)
hermes cron add "*/2 * * * *" \
  --model deepseek-reasoner --provider deepseek \
  "..." \
  --skill kairos:philosophy \
  --deliver telegram --name kairos-halftime-poll
```

Full prompts are in `docs/HERMES_WIRING.md` Step 7. Copy them verbatim
from there.

### 11. Keep-alive: do not let this PC sleep

- **Windows:** Settings → System → Power → Screen and sleep → set "On
  battery: never" AND "When plugged in: never". Also lid-close action:
  "do nothing." Power Options (control panel) → Advanced settings →
  ensure USB selective suspend disabled if you're on USB-attached
  network gear.
- **Linux:** `systemctl mask sleep.target suspend.target hibernate.target
  hybrid-sleep.target`. Add `HandleLidSwitch=ignore` to
  `/etc/systemd/logind.conf` and `systemctl restart systemd-logind`.

The Hermes daemon (installed by `hermes gateway install`) will restart
itself on reboot, but only if the PC actually boots. Plug into AC,
ethernet if possible, and put it somewhere you won't accidentally close
the lid.

### 12. Verify Obsidian sees your audit trail

Install Obsidian on the PC, add a vault pointing at `~/dev/kairos/`. You
should see `logs/` (per-bet markdown + `_kills.md`) and `brain/` (gbrain
knowledge graph). This is your read interface during the tournament.

### 13. Monitoring via Hermes Desktop (remote viewer) — optional but recommended

Hermes Desktop (released 2026-06-03, v0.15.2) is a native GUI front end for
Hermes on macOS / Windows / Linux. It shows streaming tool output (every
`kairos_fair_value`, `kairos_evaluate_bet`, and the Grok `x_search`
delegation as they happen), a cron pane (view / pause / resume jobs), a file
browser over `logs/` and `brain/`, and the skills / messaging panes.

The reason it's worth setting up: it can connect to a Hermes running on a
**different machine**, so you can watch and control the PC's kairos agent
from your Mac (or any laptop) instead of relying only on Telegram + Obsidian.

NOTE: these flags are days old as of writing — confirm exact names against
`hermes desktop --help` and the [Desktop docs](https://hermes-agent.nousresearch.com/docs/user-guide/desktop)
when you set it up.

**On the PC (the agent host) — expose the gateway with the TUI backend:**
The Desktop remote connection requires the backend to run with `--tui`
enabled and reachable on a port (default `9119`). Run kairos's Hermes so the
gateway is up (this is the same process that runs your cron jobs), with the
dashboard/TUI backend enabled per the docs. Bind it to the LAN, not the
public internet (see security note below). Generate / note the session
token the backend prints; you'll paste it into Desktop.

**On your Mac (or any device — the viewer):**
```bash
# install Desktop (one of):
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash -s -- --include-desktop
# or download the macOS installer from the Hermes site, or `hermes desktop` if Hermes is already installed
```
Open Hermes Desktop → Settings → Remote gateway → set:
- Remote URL: `http://<PC-LAN-IP>:9119`  (e.g. `http://192.168.1.50:9119`)
- Session token: the token from the PC

Use Desktop in **remote mode only** on the Mac. Do NOT run kairos in *local*
mode there — remote mode keeps the agent and its gbrain on the PC, so your
EL environment and the default `~/.gbrain` brain stay untouched.

**Security (this is a money-handling agent):**
The remote gateway is control, not just viewing — through it you can manage
cron and chat-instruct the agent. Do NOT port-forward `9119` to the open
internet. Keep it LAN-only, or for access from outside the house use
**Tailscale** or an **SSH tunnel**. The session token is not sufficient
protection on its own.

## Going-live checklist on the PC

Before flipping `KAIROS_DRY_RUN=false`:

- [ ] Smoke test passes on PC (`python -m src.main --smoke-test`)
- [ ] `hermes config show` reports DeepSeek as main provider
- [ ] `hermes plugins list` shows `kairos` enabled
- [ ] `hermes skills list` shows `kairos:philosophy` and `polymarket`
- [ ] `hermes mcp test gbrain` succeeds
- [ ] DeepSeek auth verified via `hermes chat -q "..."`
- [ ] xAI x_search verified via `hermes chat -q "..."`
- [ ] Telegram bot DMs back when you message it
- [ ] Both cron jobs registered (`hermes cron list`)
- [ ] Wallet shows your $50 USDC balance in Polymarket UI
- [ ] You can stop the agent from your phone via Telegram (`/cron pause` test)
- [ ] (optional) Hermes Desktop remote viewer connects to the PC over LAN
- [ ] At least 24 hours of DRY_RUN cron output reviewed and the agent's
      reasoning looks sensible
- [ ] Obsidian vault on the PC opens `~/dev/kairos/` and shows the logs

When all boxes are checked, edit `~/dev/kairos/.env`, set
`KAIROS_DRY_RUN=false`, and restart the agent service:

- **macOS / Linux:** `launchctl kickstart -k gui/$(id -u)/hermes` (or
  whatever your service manager command is)
- **Windows:** restart the Hermes Task Scheduler job

## Recovering when something breaks during the tournament

You won't be at the PC. Failure modes and fixes from your phone:

| Symptom | Phone fix |
|---|---|
| Bot stops posting cron output | `/cron list` to check status, `/cron resume <name>` if paused |
| Bot keeps killing bets for the same reason | DM the bot directly: ask it to read `~/dev/kairos/logs/_kills.md` and summarize; decide whether to relax a parameter |
| Telegram bot unresponsive | The PC may have lost network — call/text someone to power-cycle it |
| Agent placing bad bets | Set `KAIROS_DRY_RUN=true` via SSH from phone (use Termius or Blink) and `launchctl kickstart -k ...` |

If you don't have SSH set up on the PC before transfer, set it up now —
you will want it during the tournament.
