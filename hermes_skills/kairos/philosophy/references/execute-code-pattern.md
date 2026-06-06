# execute_code Pattern for Python API Work on Windows/git-bash Hermes

## The Problem

This Hermes setup runs on Windows with git-bash as the terminal backend. The
default CWD is `C:\Windows\System32` which doesn't exist in bash's namespace.
Every terminal call without `workdir="/tmp"` fails. Additionally, `write_file`
and `patch` tools route through the same shell and share the CWD issue.

## The Pattern: Use `execute_code` + bash heredoc + `workdir="/tmp"`

This is the most reliable way to run Python scripts that do API calls:

```python
from hermes_tools import terminal

result = terminal("""
python3 << 'PYEOF'
import subprocess, json, base64, time, urllib.request

# Your Python code here
ts = str(int(time.time() * 1000))
# ...
print(result)
PYEOF
""", workdir="/tmp", timeout=15)
```

**Key rules:**
1. Always set `workdir="/tmp"` — this is the only parameter that prevents the CWD failure
2. Use `<< 'PYEOF'` with single-quoted delimiter (`'PYEOF'`) to prevent variable expansion
3. Use Python f-strings and print() for output — don't mix shell and Python quoting
4. The `execute_code()` call itself routes through a fresh Python process, which avoids the CWD issue. The `terminal()` call inside it needs the explicit workdir.
5. Set `timeout` generously (15-20s for API calls, 30s for batch processing)

## Pattern for File Writes

### To /tmp (simple, for temp scripts)

When you need to write a Python script to /tmp for later use:

```python
from hermes_tools import terminal

result = terminal("""
cat > /tmp/my_script.py << 'SCRIPTEOF'
#!/usr/bin/env python3
import ...
print("done")
SCRIPTEOF
chmod +x /tmp/my_script.py
""", workdir="/tmp", timeout=10)
```

Then run it:
```python
result = terminal("python3 /tmp/my_script.py", workdir="/tmp", timeout=15)
```

### To ~/.hermes/scripts/ (for cron jobs — base64 technique)

Writing bash scripts to the Hermes scripts directory is fragile because heredocs
containing Python string literals (single quotes, backticks, f-strings) get
mangled by bash interpretation. **Use base64 encoding instead:**

**Step 1 — Encode in `execute_code`:**
```python
import base64
script_content = (
    '#!/bin/bash\n'
    'DATA=$(curl -s "https://api.elections.kalshi.com/trade-api/v2/...")
    'ASK=$(echo "$DATA" | python3 -c "import sys,json; '
    'print(json.load(sys.stdin)[chr(39)+chr(115)+chr(39)].get(...))")\n'
    'echo "ASK=$ASK"\n'
)
b64 = base64.b64encode(script_content.encode()).decode()
print(b64)
```

**Step 2 — Write in `terminal()` with workdir="/tmp":**
```bash
echo '<base64_string>' | base64 -d > /c/Users/gsche/.hermes/scripts/myscript.sh
chmod +x /c/Users/gsche/.hermes/scripts/myscript.sh
```

This avoids all heredoc escaping issues — the content is pure base64 with no
quotes, backticks, or special characters for bash to misinterpret.

## Pattern for Single-Command API Calls

When you just need one curl call with parsing:

```python
from hermes_tools import terminal

result = terminal("""
curl -s "https://api.elections.kalshi.com/trade-api/v2/markets/KXWCGAME-26JUN11MEXRSA-MEX" | \
python3 -c "import sys,json; m=json.load(sys.stdin)['market']; print(m.get('yes_ask_dollars','?'))"
""", workdir="/tmp", timeout=10)
```

## Pitfalls

- **Do NOT use triple-quoted strings for the shell command** if they contain complex
  Python string interpolation — the Python and shell quoting layers interact badly.
  Use `<< 'DELIMITER'` heredocs with a unique delimiter instead.
- **Do NOT put Python code inline in `-c` strings** if it contains f-strings or complex
  expressions — the shell will mangle the quotes. Use a heredoc instead.
- **The `execute_code` tool's own output** — the `/bin/bash: line N: C:/Users/gsche/...`
  messages in stderr are harmless. They're Hermes' internal log cleanup using the
  broken CWD, not script failures. Check exit code and stdout content.
- **`execute_code()` runs Python in a separate process** (Windows Python, not the
  git-bash Python). If you need shell tools (`curl`, `openssl`, `tee`, etc.), you MUST
  use `terminal()` inside `execute_code()`, not `subprocess.run()` from the inline Python.
- **Single-quote strings in bash heredocs inside Python** — this is the most common
  failure mode. A Python string `'market'` inside a `<< 'PYEOF'` heredoc gets
  interpreted by bash before Python sees it. The base64 technique is the only
  reliable escape hatch for scripts with complex quoting.
- **On native git-bash, `/tmp` is SHARED across terminal() calls — files persist.**
  Files saved to `/tmp` by `curl -o /tmp/foo.json` in one terminal() call ARE
  readable by a later terminal() call. There is no snap-private-tmp here and no
  per-call /tmp isolation. **Best practice:** still prefer to fetch AND parse in
  the SAME terminal() call when the response is large — pipe curl straight into
  python in a single terminal() call (`curl -s URL | python3 -c`) or use Python
  urllib inside a heredoc. The reason is to avoid Hermes' ~50KB stdout truncation
  on large API responses, NOT tmp-isolation. For small responses, writing to
  `/tmp` in one call and reading in the next works fine.
