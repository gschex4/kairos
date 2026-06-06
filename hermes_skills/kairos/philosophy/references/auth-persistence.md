# Kalshi Auth Persistence — Private Key Survival Across Sessions

## The Problem

Kalshi API authentication requires an RSA 2048-bit private key file. When the key
is written to `/tmp/kalshi_key.pem`, it dies with the Hermes session. Every new
session — and every cron job — starts with an empty `/tmp` and cannot authenticate.

Result: `INCORRECT_API_KEY_SIGNATURE` on portfolio/order endpoints.

## The Fix: Store Key in Hermes Skills Directory

The skills directory at `C:\Users\gsche\.hermes\skills\kairos\` persists across
sessions because it's stored on the Windows filesystem. Store the key there:

```
C:\Users\gsche\.hermes\skills\kairos\kairos-philosophy\references\kalshi_key.pem
```

In git-bash, access it via the `/c/` mount:

```
/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem
```

This path survives session restarts, Hermes upgrades, and cron job invocations.

## Signing Command (from persistent path, git-bash)

Use the `/c/` path (NOT Windows `C:\`):

```bash
# Generate timestamp (python3 more reliable than date +%s%3N on git-bash)
TS=$(python3 -c "import time; print(str(int(time.time()*1000)))")

# Sign the request path
SIG=$(echo -n "/trade-api/v2/portfolio/balance" | \
  openssl dgst -sha256 -sigopt rsa_padding_mode:pss \
  -sigopt rsa_pss_saltlen:32 -sign \
  /c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem | \
  openssl base64 -A)

# Test auth
curl -s -H "KALSHI-ACCESS-KEY: ${KALSHI_API_KEY}" \
  -H "KALSHI-ACCESS-TIMESTAMP: $TS" \
  -H "KALSHI-ACCESS-SIGNATURE: $SIG" \
  "https://api.elections.kalshi.com/trade-api/v2/portfolio/balance"
```

## Working Auth Test Recipe (Python via heredoc — most reliable)

This avoids ALL shell escaping issues. Run via `terminal(workdir="/tmp")`:

```bash
python3 << 'PYEOF'
import subprocess, base64, time, urllib.request

path = b'/trade-api/v2/portfolio/balance'
ts = str(int(time.time() * 1000))
key_file = '/c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem'

proc = subprocess.run(
    ['openssl', 'dgst', '-sha256',
     '-sigopt', 'rsa_padding_mode:pss',
     '-sigopt', 'rsa_pss_saltlen:32',
     '-sign', key_file],
    input=path, capture_output=True
)
sig = base64.b64encode(proc.stdout).decode()

req = urllib.request.Request(
    'https://api.elections.kalshi.com/trade-api/v2/portfolio/balance',
    headers={
        'KALSHI-ACCESS-KEY': '${KALSHI_API_KEY}',
        'KALSHI-ACCESS-TIMESTAMP': ts,
        'KALSHI-ACCESS-SIGNATURE': sig
    }
)
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}: {e.read().decode()}')
PYEOF
```

The single-quoted `'PYEOF'` delimiter prevents all shell expansion. This is the
recommended way to test auth from execute_code or terminal(workdir="/tmp") calls.

## Setup Flow for Fresh Key

1. User pastes raw PEM in chat (starts with `the PEM header line (BEGIN RSA PRIVATE KEY)`)
2. Agent saves to skills directory via:
   ```bash
   cat > /c/Users/gsche/.hermes/skills/kairos/kairos-philosophy/references/kalshi_key.pem << 'KEYEOF'
   <paste key here>
   KEYEOF
   ```
3. Agent verifies: `openssl rsa -in <path> -check -noout`
4. Agent tests via the Python heredoc recipe above
5. Agent saves this reference + notes the file path in memory

## Cron Job Access

Cron jobs run in isolated sessions with fresh `/tmp`. The key file at the skills
directory path (`/c/Users/gsche/...`) is accessible because the skills
directory is on the Windows host filesystem. Cron scripts must reference the full
git-bash path (not `/tmp`).

## Security Note

This is stored unencrypted on disk. The Hermes skills directory is not encrypted
at rest. If this is sensitive, the user should:
- Set restrictive NTFS permissions on the file
- Or use Windows Credential Manager / DPAPI for the key material instead
