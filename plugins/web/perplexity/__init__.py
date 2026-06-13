"""Perplexity Sonar web search plugin (user, opt-in via plugins.enabled)."""

from __future__ import annotations

from .provider import PerplexityWebSearchProvider


def register(ctx) -> None:
    """Register the Perplexity provider with the plugin context."""
    ctx.register_web_search_provider(PerplexityWebSearchProvider())
