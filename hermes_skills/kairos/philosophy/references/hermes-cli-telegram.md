# Hermes CLI & Telegram Config (this host)

## CLI Location
The hermes binary lives in the kairos project venv:
```
/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe
```

It is NOT on PATH. Do not try `hermes config`, `npx hermes`, or `npm hermes-agent` — they fail.

All config operations use:
```bash
/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config <subcommand>
```

## Common Operations

### Check current config section
```bash
/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config show | grep -A 10 "^telegram:"
```

### Set a config value
```bash
/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config set telegram.require_mention false
```

### List all keys (usable for discovery)
```bash
/c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config show
```

## Config File
Path: `C:\Users\gsche\.hermes\config.yaml`
Agent cannot directly edit it (security block). Use the CLI above.

## Telegram Group Responsiveness Checklist
When the bot isn't responding to group messages that don't mention it:

1. **Hermes config**: `telegram.require_mention` must be `false`
   ```bash
   /c/Users/gsche/dev/kairos/.venv/Scripts/hermes.exe config set telegram.require_mention false
   ```
2. **Telegram Bot API privacy mode**: Bot must have privacy mode DISABLED via @BotFather
   - Message @BotFather → `/mybots` → select the bot → Bot Settings → Group Privacy → Turn off
3. **Gateway restart**: Hermes gateway must restart to pick up config changes

## Cron Delivery Targets
The World Cup group chat target string is: `telegram:World Cup (group)`
Chat ID: `<group chat_id>`

To audit all cron delivery targets:
```
cronjob(action='list')  — check each job's "deliver" field
```
Any job with `deliver='telegram'` (no group suffix) is going to Grant's DM only.
