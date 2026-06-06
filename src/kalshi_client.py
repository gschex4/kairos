"""Kalshi trade-api/v2 REST client + RSA-PSS auth.

Thin HTTP layer for Kalshi. Market-data reads (/markets, /events, trades) are
PUBLIC (no auth). Portfolio + order endpoints are RSA-PSS-SHA256 signed.

Signing (verified Jun 2026, see hermes_skills/.../references/kalshi-api.md):
  message = f"{timestamp_ms}{METHOD}{path}"   # path EXCLUDES query params
  e.g. "1780687732145GET/trade-api/v2/portfolio/balance"
  3 headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-TIMESTAMP (ms),
             KALSHI-ACCESS-SIGNATURE (base64 RSA-PSS-SHA256, salt = digest len)

We sign with the `cryptography` library rather than shelling out to openssl, so
it works inside the Hermes gateway process with no openssl-on-PATH dependency.
salt_length = SHA256 digest size (32) == openssl `rsa_pss_saltlen:-1`.
"""
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    _CRYPTO_AVAILABLE = True
except ImportError:  # smoke test (dry-run) never signs, so this stays importable
    _CRYPTO_AVAILABLE = False

KALSHI_BASE = "https://api.elections.kalshi.com"
API_PREFIX = "/trade-api/v2"


class KalshiAuthError(RuntimeError):
    """Raised when signing credentials are missing or the key can't be loaded."""


class KalshiClient:
    """HTTP client for Kalshi trade-api/v2 with lazy RSA private-key loading.

    The private key is only loaded on the first SIGNED request, so a dry-run /
    smoke-test path that never touches portfolio endpoints needs no key at all.
    """

    def __init__(self, api_key: str, key_path: str, timeout: float = 10.0):
        self.api_key = api_key
        self.key_path = key_path
        self.timeout = timeout
        self._private_key = None  # lazy

    # ---------- auth ----------

    def _load_key(self):
        if self._private_key is not None:
            return self._private_key
        if not _CRYPTO_AVAILABLE:
            raise KalshiAuthError("the 'cryptography' package is required for Kalshi signing")
        if not self.key_path:
            raise KalshiAuthError("KALSHI_KEY_PATH is not configured")
        p = Path(self.key_path)
        if not p.exists():
            raise KalshiAuthError(f"Kalshi key file not found: {self.key_path}")
        self._private_key = serialization.load_pem_private_key(p.read_bytes(), password=None)
        return self._private_key

    def _sign_headers(self, method: str, full_path: str) -> dict[str, str]:
        """Build the 3 Kalshi auth headers. `full_path` is the path that gets
        signed (starts with /trade-api/v2/..., NO query params)."""
        if not self.api_key:
            raise KalshiAuthError("KALSHI_API_KEY is not configured")
        ts = str(int(time.time() * 1000))
        message = f"{ts}{method}{full_path}".encode()
        signature = self._load_key().sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=hashes.SHA256().digest_size,  # 32 == openssl saltlen:-1
            ),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
        }

    # ---------- raw requests ----------

    def get_public(self, path: str, params: Optional[dict] = None) -> Any:
        """Unsigned GET for public market-data endpoints. `path` excludes the prefix."""
        r = httpx.get(f"{KALSHI_BASE}{API_PREFIX}{path}", params=params or {}, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def get_auth(self, path: str) -> Any:
        """Signed GET for portfolio endpoints. `path` excludes the prefix."""
        full = f"{API_PREFIX}{path}"
        r = httpx.get(f"{KALSHI_BASE}{full}", headers=self._sign_headers("GET", full), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def post_auth(self, path: str, body: dict) -> Any:
        """Signed POST for order endpoints. `path` excludes the prefix."""
        full = f"{API_PREFIX}{path}"
        headers = self._sign_headers("POST", full)
        headers["Content-Type"] = "application/json"
        r = httpx.post(f"{KALSHI_BASE}{full}", headers=headers, json=body, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- typed helpers ----------

    def get_market(self, ticker: str) -> dict:
        data = self.get_public(f"/markets/{ticker}")
        if isinstance(data, dict):
            return data.get("market", data)
        return {}

    def get_recent_trades(self, ticker: str, limit: int = 200) -> list[dict]:
        """Public recent trades for a market (velocity input). Defensive: [] on any error."""
        try:
            data = self.get_public("/markets/trades", params={"ticker": ticker, "limit": limit})
        except Exception:
            return []
        if isinstance(data, dict):
            return data.get("trades", []) or []
        if isinstance(data, list):
            return data
        return []

    def get_balance(self) -> Any:
        return self.get_auth("/portfolio/balance")

    def get_positions(self) -> Any:
        return self.get_auth("/portfolio/positions")

    def get_settlements(self) -> Any:
        return self.get_auth("/portfolio/settlements")

    def place_order(self, body: dict) -> Any:
        return self.post_auth("/portfolio/events/orders", body)
