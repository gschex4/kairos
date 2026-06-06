"""Kairos plugin handlers.

Every handler:
  - Takes `args: dict` (the LLM's JSON arguments) plus **kwargs for forward
    compatibility with Hermes' evolving plugin protocol.
  - Returns a JSON string (json.dumps).
  - NEVER raises. Failures become {"error": "..."} JSON responses so the
    agent sees the error and can retry / correct.

Real logic lives in ~/dev/kairos/src/. These handlers are thin adapters.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Make ~/dev/kairos importable when this plugin is symlinked into
# ~/.hermes/plugins/. Plugins run inside Hermes' process, so we extend
# sys.path to include the Kairos project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import position_ledger, settlement  # noqa: E402
from src.config import Config  # noqa: E402
from src.fair_value import FairValueError, fair_value  # noqa: E402
from src.gamma_client import GammaClient  # noqa: E402
from src.market_velocity import compute_velocity  # noqa: E402
from src.kalshi_tool import KalshiTool  # noqa: E402  -- active exchange backend
from src.polymarket_tool import BetIntent, BetRejected  # noqa: E402  -- reused intent + exception
from src.sizing import SizingError  # noqa: E402
from src.sports_feed import ESPNClient  # noqa: E402
from src.untrusted import fence_untrusted, scan_for_injection  # noqa: E402

# -----------------------------------------------------------------------------
# Lazy singletons. We don't load Config at import time because that would
# require POLYMARKET_PRIVATE_KEY to be set even for dry-run smoke tests.
# -----------------------------------------------------------------------------

_config: Config | None = None
# Active betting backend is Kalshi (Polymarket is retired / US-restricted).
_pm_tool: KalshiTool | None = None
_espn: ESPNClient | None = None
_gamma: GammaClient | None = None


def _dry_run() -> bool:
    return os.environ.get("KAIROS_DRY_RUN", "true").lower() in ("true", "1", "yes")


def _ensure_ready() -> None:
    """Load config + clients on first use. Raises on misconfiguration."""
    global _config, _pm_tool, _espn, _gamma
    if _config is None:
        # In DRY_RUN we can run without wallet creds.
        _config = Config.load(require_wallet=not _dry_run())
    if _pm_tool is None:
        _pm_tool = KalshiTool(_config)
    if _espn is None:
        _espn = ESPNClient()
    if _gamma is None:
        _gamma = GammaClient()


def _ok(data: dict) -> str:
    return json.dumps(data)


def _err(msg: str, **extra: Any) -> str:
    payload = {"error": msg}
    payload.update(extra)
    return json.dumps(payload)


# -----------------------------------------------------------------------------
# Write tool
# -----------------------------------------------------------------------------

def kairos_evaluate_bet(args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        # Filter args to BetIntent's known fields (defensive: LLM may include extras)
        from dataclasses import fields
        known = {f.name for f in fields(BetIntent)}
        clean = {k: v for k, v in args.items() if k in known}
        intent = BetIntent(**clean)
        result = _pm_tool.place_bet(intent)
        return _ok({
            "status": result.get("status"),
            "size_usd": result.get("size_usd"),
            "message": result.get("message", ""),
        })
    except BetRejected as e:
        return _ok({"status": "rejected", "rule": "hard_rail", "reason": str(e)})
    except SizingError as e:
        return _ok({"status": "rejected", "rule": "sizing", "reason": str(e)})
    except TypeError as e:
        return _err(f"bad arguments: {e}")
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


# -----------------------------------------------------------------------------
# Slow engine
# -----------------------------------------------------------------------------

def kairos_fair_value(args: dict, **_kwargs) -> str:
    try:
        elo_home = args.get("elo_home")
        elo_away = args.get("elo_away")
        if elo_home is None or elo_away is None:
            return _err("elo_home and elo_away are required (source from eloratings.net)")
        fv = fair_value(
            elo_home=float(elo_home),
            elo_away=float(elo_away),
            home_adv=float(args.get("home_adv", 0.0)),
            mu_total=float(args.get("mu_total", 2.5)),
            supremacy_per_100=float(args.get("supremacy_per_100", 0.40)),
        )
        return _ok(fv.as_dict())
    except FairValueError as e:
        return _err(f"fair_value: {e}")
    except (TypeError, ValueError) as e:
        return _err(f"bad arguments: {e}")
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


# -----------------------------------------------------------------------------
# Read tools
# -----------------------------------------------------------------------------

def kairos_get_bankroll(_args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        bankroll = _pm_tool.get_bankroll_usd()
        starting = _config.starting_bankroll_usd
        remaining_pct = (bankroll / starting * 100) if starting > 0 else 0
        # Active milestone floor (mirrors src/sizing.py logic for the agent's awareness)
        if remaining_pct > 60:
            floor = 0.60
        elif remaining_pct > 40:
            floor = 0.65
        elif remaining_pct > 20:
            floor = 0.80
        else:
            floor = 0.85
        return _ok({
            "bankroll_usd": bankroll,
            "starting_bankroll_usd": starting,
            "remaining_pct": round(remaining_pct, 1),
            "active_confidence_floor": floor,
            "dry_run": _dry_run(),
        })
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_get_market_price(args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        token_id = args.get("token_id")
        if not token_id:
            return _err("token_id required")
        return _ok({"token_id": token_id, "price": _pm_tool.get_market_price(token_id)})
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_check_velocity(args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        token_id = args.get("token_id")
        if not token_id:
            return _err("token_id required")
        trades = _pm_tool._fetch_recent_trades(token_id, lookback_seconds=60)
        reading = compute_velocity(trades, token_id=token_id, source="live")
        return _ok({
            "token_id": reading.token_id,
            "has_market_data": reading.has_market_data,
            "samples_count": reading.samples_count,
            "price_now": reading.price_now,
            "pct_change_30s": reading.pct_change_30s,
            "largest_jump_60s": reading.largest_jump_60s,
            "seconds_since_largest_jump": reading.seconds_since_largest_jump,
            "trips_velocity_kill": reading.trips_velocity_kill,
            "trips_event_kill": reading.trips_event_kill,
            "kill_reason": reading.kill_reason(),
        })
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_list_matches(args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        start = args.get("start_date_yyyymmdd")
        if not start:
            return _err("start_date_yyyymmdd required")
        end = args.get("end_date_yyyymmdd", start)
        events = _espn.list_matches(start, end)
        slim = []
        for e in events:
            try:
                slim.append({
                    "event_id": str(e.get("id", "")),
                    "name": e.get("name", ""),
                    "short_name": e.get("shortName", ""),
                    "date": e.get("date", ""),
                    "status": ((e.get("status") or {}).get("type") or {}).get("name", ""),
                })
            except (TypeError, AttributeError):
                continue
        return _ok({"matches": slim, "count": len(slim)})
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_reconcile_positions(_args: dict, **_kwargs) -> str:
    """Settle any resolved positions and return the performance summary."""
    try:
        _ensure_ready()
        return _ok(settlement.reconcile(_config))
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_performance(_args: dict, **_kwargs) -> str:
    """Return the running performance summary (P&L, win rate, CLV)."""
    try:
        _ensure_ready()
        return _ok(position_ledger.performance_summary(_config))
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_vet_signal(args: dict, **_kwargs) -> str:
    """Screen raw X / web content for prompt-injection before acting on it.

    Pass any text pulled from a tweet or web page. Returns whether injection
    markers were found and a fenced version safe to reason over as DATA.
    """
    text = args.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return _err("text required")
    flags = scan_for_injection(text)
    return _ok({
        "injection_suspected": bool(flags),
        "markers": flags,
        "fenced": fence_untrusted(text),
    })


def kairos_find_markets(args: dict, **_kwargs) -> str:
    """Discover open World Cup markets on Polymarket (Gamma API)."""
    try:
        _ensure_ready()
        hours = int(args.get("hours_ahead", 24))
        events = _gamma.upcoming_world_cup_matches(hours_ahead=hours)
        out = []
        for ev in events:
            ev_d = ev.as_dict()
            # Trim to keep the payload manageable for the model
            ev_d["markets"] = ev_d["markets"][:12]
            out.append(ev_d)
        return _ok({"events": out, "count": len(out), "hours_ahead": hours})
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")


def kairos_get_match_state(args: dict, **_kwargs) -> str:
    try:
        _ensure_ready()
        event_id = args.get("event_id")
        if not event_id:
            return _err("event_id required")
        state = _espn.get_match_state(event_id)
        if state is None:
            return _err(f"could not fetch match state for event_id {event_id}")
        return _ok({
            "event_id": state.event_id,
            "status": state.status,
            "clock": state.clock,
            "home_team": state.home_team,
            "away_team": state.away_team,
            "home_score": state.home_score,
            "away_score": state.away_score,
            "kickoff": state.kickoff.isoformat() if state.kickoff else None,
            "is_live": state.is_live,
            "is_halftime": state.is_halftime,
            "last_event": (
                {
                    "type": state.last_event.type,
                    "team": state.last_event.team,
                    "player": state.last_event.player,
                    "minute": state.last_event.minute,
                }
                if state.last_event
                else None
            ),
        })
    except Exception as e:
        return _err(f"unexpected {type(e).__name__}: {e}")
