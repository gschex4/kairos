"""Post-cutover LIVE check (read-only).

Confirms the rewired plugin path runs in LIVE mode (KAIROS_DRY_RUN=false ->
Config.load(require_wallet=True) -> requires KALSHI creds -> KalshiTool) and
that kairos_get_bankroll fetches the real balance. NO order is placed
(kairos_get_bankroll is read-only).
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AUTH = Path(r"C:\Users\gsche\.hermes\skills\kairos\kairos-philosophy\references\kalshi_auth.py")
KEY = Path(r"C:\Users\gsche\.hermes\skills\kairos\kairos-philosophy\references\kalshi_key.pem")
if not os.environ.get("KALSHI_API_KEY"):
    m = re.search(r'KALSHI-ACCESS-KEY"\s*:\s*"([0-9a-fA-F-]{36})"', AUTH.read_text())
    if m:
        os.environ["KALSHI_API_KEY"] = m.group(1)
os.environ.setdefault("KALSHI_KEY_PATH", str(KEY))
os.environ["KAIROS_DRY_RUN"] = "false"  # LIVE — but only a READ-ONLY tool is called below

from hermes_plugin import tools  # noqa: E402

print("plugin _dry_run():", tools._dry_run())
print("kairos_get_bankroll (LIVE, read-only):", tools.kairos_get_bankroll({}))
print("betting backend:", type(tools._pm_tool).__name__)
