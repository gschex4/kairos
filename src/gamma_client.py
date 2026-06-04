"""Polymarket Gamma API client — World Cup market discovery.

The Gamma API is public, no auth. This is how Kairos finds which World Cup
markets exist and their token IDs, so it can then price them, check velocity,
and bet. It replaces the dependency on Hermes's bundled `polymarket` skill,
which may not be present in every Hermes install — Kairos owns its own
discovery path so it works regardless.

Docs: https://docs.polymarket.com/developers/gamma-markets-api/get-events

The parse step (`parse_event`) is pure and unit-tested; the live fetch is
best-effort and degrades to an empty list on any error so a discovery glitch
never crashes a decision run.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
HTTP_TIMEOUT = 10.0

# FIFA World Cup 2026 runs June 11 — July 19, 2026.
WORLD_CUP_2026_START = datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc)
WORLD_CUP_2026_END = datetime(2026, 7, 19, 23, 59, tzinfo=timezone.utc)


@dataclass(frozen=True)
class GammaMarket:
    condition_id: str
    question: str
    token_ids: list[str]               # clobTokenIds for the YES/NO outcomes
    outcome_prices: list[float]        # current prices aligned to token_ids
    last_trade_price: Optional[float]
    end_date: Optional[datetime]
    volume: float
    liquidity: float

    def as_dict(self) -> dict:
        return {
            "condition_id": self.condition_id,
            "question": self.question,
            "token_ids": self.token_ids,
            "outcome_prices": self.outcome_prices,
            "last_trade_price": self.last_trade_price,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "volume": self.volume,
            "liquidity": self.liquidity,
        }


@dataclass(frozen=True)
class GammaEvent:
    event_id: str
    slug: str
    title: str
    start_date: Optional[datetime]
    markets: list[GammaMarket] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "markets": [m.as_dict() for m in self.markets],
        }


# ---------- Pure parsing (unit-tested) ----------

def _coerce_list(v) -> list:
    """Gamma returns some array fields as JSON-encoded strings. Handle both."""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def parse_market(raw: dict) -> Optional[GammaMarket]:
    try:
        token_ids = [str(t) for t in _coerce_list(raw.get("clobTokenIds"))]
        prices = [_safe_float(p) for p in _coerce_list(raw.get("outcomePrices"))]
        return GammaMarket(
            condition_id=str(raw.get("conditionId", "")),
            question=str(raw.get("question", "")),
            token_ids=token_ids,
            outcome_prices=prices,
            last_trade_price=(
                _safe_float(raw.get("lastTradePrice"))
                if raw.get("lastTradePrice") is not None
                else None
            ),
            end_date=_parse_dt(raw.get("endDate")),
            volume=_safe_float(raw.get("volume")),
            liquidity=_safe_float(raw.get("liquidity")),
        )
    except (TypeError, ValueError):
        return None


def parse_event(raw: dict) -> Optional[GammaEvent]:
    try:
        markets = [m for m in (parse_market(x) for x in raw.get("markets", []) or []) if m]
        return GammaEvent(
            event_id=str(raw.get("id", "")),
            slug=str(raw.get("slug", "")),
            title=str(raw.get("title", "")),
            start_date=_parse_dt(raw.get("startDate")),
            markets=markets,
        )
    except (TypeError, ValueError):
        return None


# ---------- Live client ----------

class GammaClient:
    def __init__(self, base_url: str = GAMMA_BASE):
        self.base_url = base_url

    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=HTTP_TIMEOUT)

    def get_soccer_tag_id(self) -> Optional[int]:
        try:
            with self._http() as client:
                r = client.get(f"{self.base_url}/tags")
                r.raise_for_status()
                tags = r.json()
        except Exception as e:
            log.warning("gamma tags fetch failed: %s", e)
            return None
        for tag in tags or []:
            slug = (tag.get("slug") or "").lower()
            label = (tag.get("label") or "").lower()
            if slug == "soccer" or "soccer" in label or "football" in label:
                try:
                    return int(tag.get("id"))
                except (TypeError, ValueError):
                    continue
        return None

    def fetch_events(
        self,
        start: datetime = WORLD_CUP_2026_START,
        end: datetime = WORLD_CUP_2026_END,
        tag_id: Optional[int] = None,
        limit: int = 100,
    ) -> list[GammaEvent]:
        """Open soccer events whose start falls in [start, end]. Empty on error."""
        if tag_id is None:
            tag_id = self.get_soccer_tag_id()
        params: dict[str, str | int] = {
            "limit": limit,
            "closed": "false",
            "active": "true",
            "start_date_min": _iso(start),
            "start_date_max": _iso(end),
        }
        if tag_id is not None:
            params["tag_id"] = tag_id
        try:
            with self._http() as client:
                r = client.get(f"{self.base_url}/events", params=params)
                r.raise_for_status()
                raw_events = r.json()
        except Exception as e:
            log.warning("gamma events fetch failed: %s", e)
            return []
        return [e for e in (parse_event(x) for x in raw_events or []) if e]

    def upcoming_world_cup_matches(
        self, hours_ahead: int = 24, tag_id: Optional[int] = None
    ) -> list[GammaEvent]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)
        return self.fetch_events(start=now, end=end, tag_id=tag_id)


# ---------- helpers ----------

def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dt(s) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _safe_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
