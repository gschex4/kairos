"""Perplexity Sonar web search — Kairos user plugin.

Routes ``web_search`` tool calls to Perplexity's Sonar models via the
OpenAI-compatible ``/chat/completions`` endpoint. Unlike a links-only
provider, this returns the CITED SYNTHESIZED answer as the first row
(``choices[0].message.content``) PLUS the underlying ``search_results`` as
subsequent rows — because Kairos's contextual cross-checks want the cited
synthesis (a Transfermarkt squad value, a form table), not bare URLs.

Search-only (no extract — Perplexity does not crawl arbitrary URLs).

Config (``config.yaml``)::

    web:
      search_backend: "perplexity"
      perplexity:
        model: "sonar"                 # or "sonar-pro" for richer citations
        search_context_size: "low"     # low | medium | high
        timeout: 60                    # seconds
        max_tokens: 1200
        allowed_domains:               # optional allowlist (<=10), sharpens citations
          - "transfermarkt.com"
          - "eloratings.net"
          - "fbref.com"
          - "espn.com"
          - "fifa.com"

Env: ``PERPLEXITY_API_KEY`` (read from ``~/.hermes/.env`` at gateway launch).

Response shape verified live (Jun 2026): top-level keys
``id, model, created, usage, citations, search_results, object, choices``;
``search_results[]`` = ``{title, url, date, last_updated, snippet, source}``;
``citations[]`` = list of URL strings; ``usage.cost.total_cost`` = $ for the call.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

PPLX_URL = "https://api.perplexity.ai/chat/completions"
DEFAULT_MODEL = "sonar"
DEFAULT_CONTEXT = "low"
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_TOKENS = 1200
_MAX_DOMAINS = 10
_MAX_SOURCE_ROWS = 8
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

# Purpose-built steering: factual, cited, quantitative, no fabrication — this
# mirrors Kairos's anti-fabrication substrate rail (never invent a number,
# score, venue, or date; say so when a fact isn't found).
_SYSTEM = (
    "You are a precise sports-data research assistant for a quantitative betting model. "
    "Answer ONLY from retrieved web sources. Be concise, quantitative, and cite every claim. "
    "Prefer authoritative sources (Transfermarkt for squad market values, ESPN/FBref for "
    "results and form, eloratings.net for Elo). If a fact is not present in the sources, say so "
    "explicitly — never guess or fabricate a number, score, venue, lineup, or date."
)


def _load_cfg() -> Dict[str, Any]:
    """Read ``web.perplexity`` from config.yaml (returns {} on miss)."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        web = cfg.get("web") if isinstance(cfg, dict) else None
        pplx = web.get("perplexity") if isinstance(web, dict) else None
        return pplx if isinstance(pplx, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not load web.perplexity config: %s", exc)
        return {}


def _domains(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        if len(out) >= _MAX_DOMAINS:
            break
    return out


class PerplexityWebSearchProvider(WebSearchProvider):
    """Perplexity Sonar search provider (search-only, cited synthesis)."""

    @property
    def name(self) -> str:
        return "perplexity"

    @property
    def display_name(self) -> str:
        return "Perplexity Sonar"

    def is_available(self) -> bool:
        """True when PERPLEXITY_API_KEY is set (cheap; no network call)."""
        return bool(os.getenv("PERPLEXITY_API_KEY", "").strip())

    def supports_search(self) -> bool:
        return True

    # supports_extract() inherits False from the ABC — Perplexity is search-only.

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        try:
            from tools.interrupt import is_interrupted

            if is_interrupted():
                return {"success": False, "error": "Interrupted"}
        except Exception:  # noqa: BLE001 — interrupt module optional
            pass

        api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
        if not api_key:
            return {"success": False, "error": "PERPLEXITY_API_KEY not set"}

        cfg = _load_cfg()
        model = str(cfg.get("model") or DEFAULT_MODEL).strip()
        context = str(cfg.get("search_context_size") or DEFAULT_CONTEXT).strip()
        try:
            timeout = float(cfg.get("timeout") or DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            timeout = float(DEFAULT_TIMEOUT)
        try:
            max_tokens = int(cfg.get("max_tokens") or DEFAULT_MAX_TOKENS)
        except (TypeError, ValueError):
            max_tokens = DEFAULT_MAX_TOKENS
        allowed = _domains(cfg.get("allowed_domains"))

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "web_search_options": {"search_context_size": context},
            "return_related_questions": False,
        }
        if allowed:
            payload["search_domain_filter"] = allowed

        try:
            import httpx

            logger.info("Web search via perplexity (%s): '%s' (limit=%d)", model, query, limit)
            resp = httpx.post(
                PPLX_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001 — incl. httpx HTTP/timeout errors
            logger.warning("Perplexity search error: %s", exc)
            return {"success": False, "error": f"Perplexity search failed: {exc}"}

        # Cost logging for the daily-settle burn line (defensive: block may be absent).
        try:
            cost = (data.get("usage") or {}).get("cost") or {}
            total = cost.get("total_cost")
            if total is not None:
                logger.info("Perplexity usage.cost.total_cost=$%.5f model=%s", float(total), model)
        except Exception:  # noqa: BLE001
            pass

        # Synthesized cited answer (strip any <think> block a reasoning model might emit).
        try:
            answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        except Exception:  # noqa: BLE001
            answer = ""
        answer = _THINK_RE.sub("", answer).strip()

        search_results = data.get("search_results")
        citations = data.get("citations")

        web_rows: List[Dict[str, Any]] = []

        # Row 1 — the cited synthesized answer (the reason to use this provider).
        if answer:
            first_url = ""
            if isinstance(search_results, list) and search_results and isinstance(search_results[0], dict):
                first_url = search_results[0].get("url", "") or ""
            elif isinstance(citations, list) and citations and isinstance(citations[0], str):
                first_url = citations[0]
            web_rows.append(
                {
                    "title": f"Perplexity Sonar — synthesized answer ({model})",
                    "url": first_url,
                    "description": answer,
                    "position": 1,
                }
            )

        # Subsequent rows — the underlying sources (prefer structured search_results).
        pos = len(web_rows) + 1
        if isinstance(search_results, list) and search_results:
            for r in search_results[:_MAX_SOURCE_ROWS]:
                if not isinstance(r, dict):
                    continue
                web_rows.append(
                    {
                        "title": r.get("title", "") or "",
                        "url": r.get("url", "") or "",
                        "description": r.get("snippet", "") or "",
                        "position": pos,
                    }
                )
                pos += 1
        elif isinstance(citations, list):
            for c in citations[:_MAX_SOURCE_ROWS]:
                if isinstance(c, str) and c:
                    web_rows.append({"title": c, "url": c, "description": "", "position": pos})
                    pos += 1

        if not web_rows:
            return {"success": False, "error": "Perplexity returned no answer or sources"}

        return {"success": True, "data": {"web": web_rows}}

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Perplexity Sonar",
            "badge": "paid",
            "tag": "Cited web-search synthesis (Sonar). Search-only; no extract.",
            "env_vars": [
                {
                    "key": "PERPLEXITY_API_KEY",
                    "prompt": "Perplexity API key",
                    "url": "https://www.perplexity.ai/settings/api",
                },
            ],
        }
