import os
import re
import sys
import logging
import httpx
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# TYPES
# ============================================================

class TonMode(Enum):
    MOCK    = "MOCK"
    TESTNET = "TESTNET"
    MAINNET = "MAINNET"

class ConfigError(Exception):
    """Raised at startup when configuration is invalid."""
    pass

# ============================================================
# CONFIG DATACLASS
# ============================================================

@dataclass(frozen=True)
class Config:
    ton_mode:          TonMode
    ton_api_endpoint:  str
    ton_api_key:       str
    redis_host:        str
    redis_port:        int
    agent_id:          str
    wallet_address:    Optional[str] = None
    pool_address:      Optional[str] = None

    @classmethod
    def load(cls, check_api: bool = True) -> "Config":
        errors: list[str] = []

        raw_mode = _require("TON_MODE", errors)
        ton_mode = None
        if raw_mode:
            try:
                ton_mode = TonMode(raw_mode.upper())
            except ValueError:
                errors.append(f"TON_MODE={raw_mode!r} is invalid. Must be one of: {[m.value for m in TonMode]}")

        ton_api_endpoint = _require("TON_API_ENDPOINT", errors)
        if ton_api_endpoint:
            _validate_url(ton_api_endpoint, "TON_API_ENDPOINT", errors)

        ton_api_key = _require("TON_API_KEY", errors)
        if ton_api_key:
            _validate_not_placeholder(ton_api_key, "TON_API_KEY", errors)

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port_raw = os.getenv("REDIS_PORT", "6379")
        try:
            redis_port = int(redis_port_raw)
            if not (1 <= redis_port <= 65535):
                errors.append(f"REDIS_PORT={redis_port} is out of range (1–65535)")
        except ValueError:
            errors.append(f"REDIS_PORT={redis_port_raw!r} is not a valid integer")
            redis_port = 6379

        agent_id = _require("AGENT_ID", errors)
      
        w_env = os.getenv("WALLET_ADDRESS")
        wallet_address = w_env.strip() if (w_env and w_env.strip()) else None

        p_env = os.getenv("POOL_ADDRESS")
        pool_address = p_env.strip() if (p_env and p_env.strip()) else None

        if wallet_address:
            _validate_ton_address(wallet_address, "WALLET_ADDRESS", errors)
        if pool_address:
            _validate_ton_address(pool_address, "POOL_ADDRESS", errors)

        if ton_mode == TonMode.MAINNET and ton_api_endpoint and "testnet" in ton_api_endpoint.lower():
            errors.append("TON_MODE=MAINNET but TON_API_ENDPOINT contains 'testnet'")

        if errors:
            _fatal(errors)

        cfg = cls(
            ton_mode=ton_mode,
            ton_api_endpoint=ton_api_endpoint,
            ton_api_key=ton_api_key,
            redis_host=redis_host,
            redis_port=redis_port,
            agent_id=agent_id,
            wallet_address=wallet_address,
            pool_address=pool_address,
        )

        if check_api and ton_mode != TonMode.MOCK:
            _probe_api(cfg.ton_api_endpoint, cfg.ton_api_key)

        return cfg

# ============================================================
# VALIDATORS
# ============================================================

_TON_ADDRESS_RE = re.compile(r"^(EQ|UQ)[A-Za-z0-9_\-]{46,47}$")

_FORBIDDEN_VALUES = {
    "your_api_key", "placeholder", "changeme", "xxx", "todo", "example", "<api_key>", "your_key_here"
}

def _require(key: str, errors: list[str]) -> Optional[str]:
    value = os.getenv(key, "").strip()
    if not value:
        errors.append(f"{key} is not set (required)")
        return None
    return value

def _validate_url(value: str, key: str, errors: list[str]) -> None:
    if not value.startswith(("http://", "https://")):
        errors.append(f"{key}={value!r} must start with http:// or https://")

def _validate_not_placeholder(value: str, key: str, errors: list[str]) -> None:
    if value.lower() in _FORBIDDEN_VALUES or (value.startswith("<") and value.endswith(">")):
        errors.append(f"{key} looks like a placeholder ({value!r}). Set a real value before starting.")

def _validate_ton_address(value: str, key: str, errors: list[str]) -> None:
    if not _TON_ADDRESS_RE.match(value):
        errors.append(f"{key}={value!r} is not a valid TON address. Expected format: EQ/UQ + 46 base64url chars")

def _probe_api(endpoint: str, api_key: str) -> None:
    probe_url = endpoint.rstrip("/") + "/getAddressBalance"
    params = {"address": "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"}
    headers = {"X-API-Key": api_key}
    
    try:
        response = httpx.get(probe_url, params=params, headers=headers, timeout=5.0)
        if response.status_code == 401:
            _fatal([f"TON_API_KEY is invalid — API returned 401 Unauthorized."])
        if response.status_code >= 500:
            _fatal([f"TON API returned {response.status_code} — server error."])
    except httpx.TimeoutException:
        _fatal([f"TON API probe timed out after 5s."])
    except httpx.ConnectError:
        _fatal([f"Cannot connect to TON API."])

def _fatal(errors: list[str]) -> None:
    # Print the exact header that tests look for
    sys.stderr.write("  ❌  CONFIGURATION ERROR — Aether OS cannot start\n")
    sys.stderr.write("\n".join([f"  {i+1}. {e}" for i, e in enumerate(errors)]) + "\n")
    # Explicitly raise
    raise ConfigError(f"{len(errors)} configuration error(s) found")





