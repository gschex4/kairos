"""Sports data feed for World Cup 2026.

Primary: ESPN's undocumented public API (free, no auth, ~200ms behind broadcast).
Backup: football-data.org (free tier, 10 req/min, requires API key).

The agent uses this to:
  - Find upcoming matches and kickoff times
  - Get authoritative score, clock, status, and last in-match event
  - Fire the event-window rail proactively (as a supplement to the
    trade-history proxy in src/market_velocity.py)
  - Confirm lineups before pre-match bets

Honest about ESPN: no SLA, schema can change without notice. All field
access is defensive (.get with fallbacks). If parsing fails, helpers return
None and the caller falls back to football-data.org or to skipping the
signal. The agent never crashes on a sports-feed glitch.

Reference: https://github.com/pseudo-r/Public-ESPN-API
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
HTTP_TIMEOUT = 5.0


# ---------- Data shapes ----------

@dataclass(frozen=True)
class MatchEvent:
    """A single in-match event (goal, card, sub, etc)."""
    minute: Optional[int]
    type: str                          # e.g. "Goal", "Yellow Card", "Red Card"
    team: str
    player: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MatchState:
    """Snapshot of a match. Returned by `get_match_state(event_id)`."""
    event_id: str
    status: str                        # STATUS_SCHEDULED / IN_PROGRESS / HALFTIME / FULL_TIME / etc
    clock: Optional[str]               # broadcast clock, e.g. "67'"
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    kickoff: Optional[datetime]
    last_event: Optional[MatchEvent]
    is_live: bool
    is_halftime: bool
    raw: dict = field(default_factory=dict)


# ---------- ESPN (primary) ----------

class ESPNClient:
    """Thin client around ESPN's undocumented soccer scoreboard endpoints."""

    def __init__(self, base_url: str = ESPN_BASE):
        self.base_url = base_url

    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=HTTP_TIMEOUT)

    def list_matches(self, date_yyyymmdd: str, date_to_yyyymmdd: Optional[str] = None) -> list[dict]:
        """Return raw ESPN scoreboard entries for a date or date range.

        Examples:
            list_matches("20260611")
            list_matches("20260611", "20260619")
        """
        if date_to_yyyymmdd and date_to_yyyymmdd != date_yyyymmdd:
            params = {"dates": f"{date_yyyymmdd}-{date_to_yyyymmdd}"}
        else:
            params = {"dates": date_yyyymmdd}
        try:
            with self._http() as client:
                r = client.get(f"{self.base_url}/scoreboard", params=params)
                r.raise_for_status()
                return r.json().get("events", []) or []
        except Exception as e:
            log.warning("ESPN scoreboard fetch failed: %s", e)
            return []

    def get_match_state(self, event_id: str) -> Optional[MatchState]:
        """Fetch and parse one match. Returns None on any failure."""
        try:
            with self._http() as client:
                r = client.get(f"{self.base_url}/summary", params={"event": event_id})
                r.raise_for_status()
                payload = r.json()
        except Exception as e:
            log.warning("ESPN summary fetch failed for event %s: %s", event_id, e)
            return None
        return _parse_espn_summary(payload, event_id)


def _parse_espn_summary(d: dict, event_id: str) -> Optional[MatchState]:
    """Defensive parse of ESPN summary payload. Returns None on failure."""
    try:
        header = d.get("header", {}) or {}
        comps = header.get("competitions") or []
        comp = comps[0] if comps else {}
        status_info = comp.get("status", {}) or {}
        status_type = status_info.get("type", {}) or {}
        status_name = status_type.get("name") or "STATUS_UNKNOWN"

        competitors = comp.get("competitors", []) or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        plays = d.get("plays") or []
        last_event = _parse_play(plays[-1]) if plays else None

        kickoff_raw = comp.get("date") or header.get("date")

        return MatchState(
            event_id=event_id,
            status=status_name,
            clock=status_info.get("displayClock"),
            home_team=_team_name(home),
            away_team=_team_name(away),
            home_score=_int(home.get("score")),
            away_score=_int(away.get("score")),
            kickoff=_parse_dt(kickoff_raw),
            last_event=last_event,
            is_live=status_name in (
                "STATUS_IN_PROGRESS",
                "STATUS_FIRST_HALF",
                "STATUS_SECOND_HALF",
                "STATUS_EXTRA_TIME",
                "STATUS_SHOOTOUT",
            ),
            is_halftime=status_name in ("STATUS_HALFTIME", "STATUS_END_PERIOD"),
            raw=d,
        )
    except Exception as e:
        log.warning("ESPN parse failed for event %s: %s", event_id, e)
        return None


def _team_name(competitor: dict) -> str:
    team = competitor.get("team", {}) or {}
    return (
        team.get("displayName")
        or team.get("shortDisplayName")
        or team.get("name")
        or ""
    )


def _parse_play(play: dict) -> Optional[MatchEvent]:
    try:
        clock = play.get("clock", {}) or {}
        period = play.get("period", {}) or {}
        ptype = play.get("type", {}) or {}
        team = play.get("team", {}) or {}
        athlete = play.get("athlete", {}) or {}
        return MatchEvent(
            minute=_int_or_none(clock.get("value") or period.get("number")),
            type=ptype.get("text") or play.get("text") or "Unknown",
            team=team.get("displayName") or team.get("shortDisplayName") or "",
            player=athlete.get("displayName"),
            raw=play,
        )
    except Exception:
        return None


# ---------- football-data.org (backup oracle) ----------

class FootballDataClient:
    """Backup oracle. Free tier: 10 req/min, requires API key.

    Sign up at https://www.football-data.org/client/register — takes 60s.
    Put the key in .env as KAIROS_FOOTBALL_DATA_KEY.
    """

    def __init__(self, api_key: str, base_url: str = FOOTBALL_DATA_BASE):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def get_match(self, match_id: int) -> Optional[dict]:
        if not self.configured:
            return None
        try:
            r = httpx.get(
                f"{self.base_url}/matches/{match_id}",
                headers={"X-Auth-Token": self.api_key},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning("football-data fetch failed for match %s: %s", match_id, e)
            return None


# ---------- helpers ----------

def _int(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _int_or_none(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_dt(s) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
