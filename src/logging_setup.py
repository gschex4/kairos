"""Markdown logging the bot writes per bet decision.

Each *placed* or *dry_run* decision becomes one markdown file in logs/.
Each *killed* decision is appended to logs/_kills.md (philosophy: the kill
log is as valuable as the bet log).

Obsidian opens logs/ as a vault and you can read everything.

Telegram alerts are now handled by Hermes' built-in gateway (see
docs/HERMES_WIRING.md). Hooks fire `send_message` on tool calls — this
module no longer owns notification delivery.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.config import Config
    from src.polymarket_tool import BetIntent


def _slugify(text: str, max_len: int = 40) -> str:
    safe = "".join(c if c.isalnum() else "-" for c in text.lower())
    safe = "-".join(p for p in safe.split("-") if p)
    return safe[:max_len].strip("-") or "untitled"


def _sources_block(sources: list[str]) -> str:
    return "\n".join(f"- {s}" for s in sources) or "_(none cited)_"


def _velocity_block(audit: Optional[dict]) -> str:
    if not audit:
        return "_(no velocity audit recorded)_"
    pct = audit.get("pct_change_30s")
    jump = audit.get("largest_jump_60s")
    since = audit.get("seconds_since_largest_jump")
    return (
        "| Field | Value |\n"
        "|---|---|\n"
        f"| Source | `{audit.get('source', 'unknown')}` |\n"
        f"| Has market data | {audit.get('has_market_data', False)} |\n"
        f"| Trade samples (last 60s) | {audit.get('samples_count', 0)} |\n"
        f"| Net % change (30s) | {f'{pct:.2%}' if pct is not None else 'n/a'} |\n"
        f"| Largest single-trade jump (60s) | {f'{jump:.2%}' if jump is not None else 'n/a'} |\n"
        f"| Seconds since that jump | {since if since is not None else 'n/a'} |\n"
    )


def log_bet_decision(
    intent: "BetIntent",
    status: str,
    result: Optional[dict],
    config: "Config",
) -> Path:
    """Write a markdown record of one placed-or-dry-run bet.

    Returns the path written. Safe to call even if the dir doesn't exist yet.
    """
    config.log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc)
    # %f = microseconds — prevents same-second writes from overwriting each other
    fname = f"{ts:%Y-%m-%d_%H%M%S_%f}_{_slugify(intent.market_question)}.md"
    path = config.log_dir / fname

    audit = intent.sizing_audit or {}
    size_usd = intent.computed_size_usd if intent.computed_size_usd is not None else 0.0

    body = f"""---
timestamp: {ts.isoformat()}
status: {status}
market: "{intent.market_question}"
condition_id: {intent.condition_id}
token_id: {intent.token_id}
side: {intent.side}
ask_price: {intent.price}
estimated_probability: {intent.estimated_probability}
confidence: {intent.confidence}
computed_size_usd: {size_usd}
is_exotic: {intent.is_exotic}
dry_run: {config.dry_run}
---

# {intent.market_question}

**Decision:** {intent.side} at ${intent.price:.3f} for ${size_usd:.2f}
**Status:** `{status}`
**Estimated probability:** {intent.estimated_probability:.3f}
**Confidence:** {intent.confidence:.2f}

## Sizing audit

| Field | Value |
|---|---|
| Bankroll at decision | ${audit.get("bankroll", 0):.2f} |
| Confidence floor (milestone) | {audit.get("confidence_floor", 0):.2f} |
| Tier ceiling (fraction) | {audit.get("tier_ceiling_fraction", 0):.3f} |
| Edge (est_prob − ask) | {audit.get("edge", 0):.3f} |
| Full Kelly fraction | {audit.get("kelly_full", 0):.3f} |
| Half Kelly fraction | {audit.get("kelly_half", 0):.3f} |
| Final size fraction | {audit.get("size_fraction", 0):.3f} |
| Exotic-halved | {audit.get("is_exotic_halved", False)} |

## Market velocity audit

{_velocity_block(intent.velocity_audit)}

## Reasoning

{intent.reasoning}

## Sources cited

{_sources_block(intent.sources)}

## Raw result

```json
{json.dumps(result or {}, indent=2, default=str)}
```
"""
    path.write_text(body, encoding="utf-8")
    return path


def log_kill_decision(intent: "BetIntent", reason: str, config: "Config") -> Path:
    """Append a kill entry to logs/_kills.md.

    The kill log is its own file (not one-per-kill) so you can scroll the
    whole history of "what the agent considered and didn't bet" in one read.
    """
    config.log_dir.mkdir(parents=True, exist_ok=True)
    path = config.log_dir / "_kills.md"
    ts = datetime.now(timezone.utc).isoformat()

    entry = f"""## {ts} — {intent.market_question}

- **Kill reason:** {reason}
- **Side:** {intent.side} at ${intent.price:.3f}
- **Estimated probability:** {intent.estimated_probability:.3f}
- **Confidence:** {intent.confidence:.2f}
- **Sources:** {len(intent.sources)} cited
- **Reasoning:** {intent.reasoning[:200]}{"..." if len(intent.reasoning) > 200 else ""}

---

"""
    with path.open("a", encoding="utf-8") as f:
        f.write(entry)
    return path


def log_event(event: str, detail: str, config: "Config") -> None:
    """Append a freeform event line to logs/_events.md.

    For non-bet events the human reviewer might care about:
    'agent started', 'X poll returned no results', 'market closed', etc.
    """
    config.log_dir.mkdir(parents=True, exist_ok=True)
    path = config.log_dir / "_events.md"
    ts = datetime.now(timezone.utc).isoformat()
    line = f"- `{ts}` **{event}** — {detail}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
