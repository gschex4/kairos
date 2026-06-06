"""Runtime configuration loaded from .env.

Single source of truth for everything the bot needs at runtime.
Import `config` from here and read attributes — don't read env vars elsewhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val or val.startswith("0x_paste"):
        raise RuntimeError(
            f"Missing required env var: {name}. "
            f"Copy .env.example to .env and fill in real values."
        )
    return val


def _optional(name: str, default: str = "") -> str:
    # Treat a present-but-empty value (e.g. `KAIROS_DRY_RUN_BANKROLL_USD=` in
    # .env) the same as absent, so the default applies instead of returning ""
    # (which would crash float()/int() parsing downstream).
    val = os.environ.get(name, "").strip()
    return val if val else default


@dataclass(frozen=True)
class Config:
    # Polymarket wallet
    polymarket_private_key: str
    polymarket_funder_address: str
    polymarket_api_key: str
    polymarket_api_secret: str
    polymarket_api_passphrase: str
    polymarket_chain_id: int

    # Bankroll + sizing
    starting_bankroll_usd: float    # the original $50 (or whatever); used for milestone calc
    dry_run_bankroll_usd: float     # the bankroll to assume in DRY_RUN, since no real wallet is read
    absolute_max_bet_usd: float     # paranoid hard ceiling, defense in depth on top of the 10% rule
    fixed_cost_usd: float           # est. per-bet transaction cost (gas + buffer); edge must clear it
    dry_run: bool

    # Paths
    log_dir: Path
    brain_dir: Path

    # Sports data backup oracle (opt-in)
    football_data_api_key: str

    # Kalshi — the active exchange (Polymarket is US-restricted / view-only).
    # kalshi_key_path points at the RSA private key (.pem) used to sign
    # portfolio/order requests. Both are optional so dry-run smoke tests load
    # without credentials; live mode requires them (see require_wallet below).
    kalshi_api_key: str
    kalshi_key_path: str

    # Note: XAI_API_KEY and TELEGRAM_* are owned by Hermes (live in
    # ~/.hermes/.env). The Kairos plugin never reads them directly —
    # Hermes injects model auth and Telegram delivery itself.

    @classmethod
    def load(cls, require_wallet: bool = True) -> "Config":
        # The wallet credentials are only required when we actually want to
        # touch Polymarket. For pure dry-run smoke tests we can skip them.
        if require_wallet:
            pk = _require("POLYMARKET_PRIVATE_KEY")
            funder = _require("POLYMARKET_FUNDER_ADDRESS")
        else:
            pk = _optional("POLYMARKET_PRIVATE_KEY")
            funder = _optional("POLYMARKET_FUNDER_ADDRESS")

        starting = float(_optional("KAIROS_STARTING_BANKROLL_USD", "50"))
        return cls(
            polymarket_private_key=pk,
            polymarket_funder_address=funder,
            polymarket_api_key=_optional("POLYMARKET_API_KEY"),
            polymarket_api_secret=_optional("POLYMARKET_API_SECRET"),
            polymarket_api_passphrase=_optional("POLYMARKET_API_PASSPHRASE"),
            polymarket_chain_id=int(_optional("POLYMARKET_CHAIN_ID", "137")),
            starting_bankroll_usd=starting,
            dry_run_bankroll_usd=float(
                _optional("KAIROS_DRY_RUN_BANKROLL_USD", str(starting))
            ),
            # Default the absolute ceiling to 2x the starting 10% — should never
            # trip in normal use, will catch catastrophic miscomputation.
            absolute_max_bet_usd=float(
                _optional("KAIROS_ABSOLUTE_MAX_BET_USD", str(starting * 0.20))
            ),
            # Est. round-trip transaction cost (Polygon gas + a small spread
            # buffer). A bet's expected profit must exceed this or it's a pass.
            fixed_cost_usd=float(_optional("KAIROS_FIXED_COST_USD", "0.05")),
            dry_run=_optional("KAIROS_DRY_RUN", "true").lower() in ("true", "1", "yes"),
            log_dir=PROJECT_ROOT / _optional("KAIROS_LOG_DIR", "logs"),
            brain_dir=PROJECT_ROOT / _optional("KAIROS_BRAIN_DIR", "brain"),
            football_data_api_key=_optional("KAIROS_FOOTBALL_DATA_KEY"),
            kalshi_api_key=_optional("KALSHI_API_KEY"),
            kalshi_key_path=_optional("KALSHI_KEY_PATH", ""),
        )
