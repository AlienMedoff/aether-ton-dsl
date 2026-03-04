"""
tests/test_config.py

Run: pytest tests/test_config.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from config import Config, ConfigError, TonMode


# ============================================================
# HELPERS
# ============================================================

VALID_ENV = {
    "TON_MODE":         "TESTNET",
    "TON_API_ENDPOINT": "https://testnet.toncenter.com/api/v2",
    "TON_API_KEY":      "abc123realkey",
    "REDIS_HOST":       "localhost",
    "REDIS_PORT":       "6379",
    "AGENT_ID":         "TransactionExecutorAgent",
}


def load(overrides: dict = None, check_api: bool = False) -> Config:
    """Load config with valid base env, optionally overriding specific keys."""
    env = {**VALID_ENV, **(overrides or {})}
    # Remove keys set to None (simulate unset env vars)
    env = {k: v for k, v in env.items() if v is not None}
    with patch.dict("os.environ", env, clear=True):
        return Config.load(check_api=check_api)


# ============================================================
# 1. HAPPY PATH
# ============================================================

class TestHappyPath:

    def test_valid_config_loads(self):
        cfg = load()
        assert cfg.ton_mode == TonMode.TESTNET
        assert cfg.ton_api_endpoint == "https://testnet.toncenter.com/api/v2"
        assert cfg.ton_api_key == "abc123realkey"
        assert cfg.redis_host == "localhost"
        assert cfg.redis_port == 6379
        assert cfg.agent_id == "TransactionExecutorAgent"

    def test_mock_mode_loads(self):
        cfg = load({"TON_MODE": "MOCK"})
        assert cfg.ton_mode == TonMode.MOCK

    def test_mainnet_mode_loads_with_correct_endpoint(self):
        cfg = load({
            "TON_MODE":         "MAINNET",
            "TON_API_ENDPOINT": "https://toncenter.com/api/v2",
        })
        assert cfg.ton_mode == TonMode.MAINNET

    def test_optional_addresses_parsed(self):
        cfg = load({
            "WALLET_ADDRESS": "EQD" + "A" * 46,
            "POOL_ADDRESS":   "UQD" + "B" * 46,
        })
        assert cfg.wallet_address is not None
        assert cfg.pool_address is not None

    def test_missing_optional_addresses_are_none(self):
        cfg = load()
        assert cfg.wallet_address is None
        assert cfg.pool_address is None

    def test_config_is_frozen(self):
        cfg = load()
        with pytest.raises(Exception):
            cfg.ton_mode = TonMode.MOCK  # type: ignore


# ============================================================
# 2. REQUIRED FIELDS — missing
# ============================================================

class TestRequiredFields:

    @pytest.mark.parametrize("missing_key", [
        "TON_MODE",
        "TON_API_ENDPOINT",
        "TON_API_KEY",
        "AGENT_ID",
    ])
    def test_missing_required_field_raises(self, missing_key: str):
        with pytest.raises(ConfigError) as exc_info:
            load({missing_key: None})
        assert missing_key in str(exc_info.value) or "configuration error" in str(exc_info.value).lower()

    def test_empty_string_treated_as_missing(self):
        with pytest.raises(ConfigError):
            load({"TON_API_KEY": ""})

    def test_whitespace_only_treated_as_missing(self):
        with pytest.raises(ConfigError):
            load({"TON_API_KEY": "   "})


# ============================================================
# 3. TON_MODE VALIDATION
# ============================================================

class TestTonMode:

    def test_invalid_mode_raises(self):
        with pytest.raises(ConfigError) as exc_info:
            load({"TON_MODE": "PRODUCTION"})
        assert "TON_MODE" in str(exc_info.value) or "configuration error" in str(exc_info.value).lower()

    def test_mode_case_insensitive(self):
        cfg = load({"TON_MODE": "testnet"})
        assert cfg.ton_mode == TonMode.TESTNET

    def test_mainnet_with_testnet_endpoint_raises(self):
        with pytest.raises(ConfigError) as exc_info:
            load({
                "TON_MODE":         "MAINNET",
                "TON_API_ENDPOINT": "https://testnet.toncenter.com/api/v2",
            })
        assert "testnet" in str(exc_info.value).lower() or "configuration error" in str(exc_info.value).lower()


# ============================================================
# 4. API ENDPOINT VALIDATION
# ============================================================

class TestApiEndpoint:

    def test_endpoint_without_scheme_raises(self):
        with pytest.raises(ConfigError):
            load({"TON_API_ENDPOINT": "toncenter.com/api/v2"})

    def test_http_endpoint_accepted(self):
        cfg = load({"TON_API_ENDPOINT": "http://localhost:8080/api/v2"})
        assert cfg.ton_api_endpoint.startswith("http://")


# ============================================================
# 5. PLACEHOLDER DETECTION
# ============================================================

class TestPlaceholderDetection:

    @pytest.mark.parametrize("placeholder", [
        "your_api_key",
        "YOUR_KEY_HERE",
        "placeholder",
        "changeme",
        "xxx",
        "<API_KEY>",
        "todo",
    ])
    def test_placeholder_api_key_raises(self, placeholder: str):
        with pytest.raises(ConfigError):
            load({"TON_API_KEY": placeholder})


# ============================================================
# 6. TON ADDRESS VALIDATION
# ============================================================

class TestTonAddressValidation:

    def test_valid_eq_address(self):
        cfg = load({"WALLET_ADDRESS": "EQ" + "A" * 46})
        # 48 chars total: EQ + 46
        # Actually EQ + 46 = 48 total chars
        assert cfg.wallet_address is not None

    def test_valid_uq_address(self):
        cfg = load({"WALLET_ADDRESS": "UQ" + "a" * 46})
        assert cfg.wallet_address is not None

    def test_invalid_address_prefix_raises(self):
        with pytest.raises(ConfigError):
            load({"WALLET_ADDRESS": "XX" + "A" * 46})

    def test_too_short_address_raises(self):
        with pytest.raises(ConfigError):
            load({"WALLET_ADDRESS": "EQ" + "A" * 10})

    def test_raw_hex_address_raises(self):
        with pytest.raises(ConfigError):
            load({"WALLET_ADDRESS": "0:" + "a" * 64})


# ============================================================
# 7. REDIS CONFIG
# ============================================================

class TestRedisConfig:

    def test_default_redis_host(self):
        cfg = load({"REDIS_HOST": None})  # Unset → default
        assert cfg.redis_host == "localhost"

    def test_default_redis_port(self):
        cfg = load({"REDIS_PORT": None})
        assert cfg.redis_port == 6379

    def test_invalid_redis_port_raises(self):
        with pytest.raises(ConfigError):
            load({"REDIS_PORT": "not_a_number"})

    def test_out_of_range_port_raises(self):
        with pytest.raises(ConfigError):
            load({"REDIS_PORT": "99999"})


# ============================================================
# 8. API PROBE
# ============================================================

class TestApiProbe:

    def test_probe_skipped_in_mock_mode(self):
        # Should not make any HTTP calls in MOCK mode
        with patch("config.httpx.get") as mock_get:
            load({"TON_MODE": "MOCK"}, check_api=True)
            mock_get.assert_not_called()

    def test_probe_called_in_testnet_mode(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("config.httpx.get", return_value=mock_response) as mock_get:
            load({"TON_MODE": "TESTNET"}, check_api=True)
            mock_get.assert_called_once()
            url = mock_get.call_args[0][0]
            assert "getAddressBalance" in url

    def test_probe_401_raises_config_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("config.httpx.get", return_value=mock_response):
            with pytest.raises(ConfigError) as exc_info:
                load({"TON_MODE": "TESTNET"}, check_api=True)
            assert "401" in str(exc_info.value) or "configuration error" in str(exc_info.value).lower()

    def test_probe_timeout_raises_config_error(self):
        import httpx as _httpx

        with patch("config.httpx.get", side_effect=_httpx.TimeoutException("timeout")):
            with pytest.raises(ConfigError) as exc_info:
                load({"TON_MODE": "TESTNET"}, check_api=True)
            assert "configuration error" in str(exc_info.value).lower()

    def test_probe_connection_error_raises(self):
        import httpx as _httpx

        with patch("config.httpx.get", side_effect=_httpx.ConnectError("refused")):
            with pytest.raises(ConfigError):
                load({"TON_MODE": "TESTNET"}, check_api=True)


# ============================================================
# 9. ERROR MESSAGES QUALITY
# ============================================================

class TestErrorMessages:

    def test_multiple_errors_all_reported(self):
        """When several vars are missing, ALL errors show up — not just the first."""
        try:
            load({"TON_MODE": None, "TON_API_KEY": None, "AGENT_ID": None})
            pytest.fail("Expected ConfigError")
        except ConfigError as e:
            msg = str(e)
            assert "3" in msg  # "3 configuration error(s)"

    def test_error_output_to_stderr(self, capsys):
        try:
            load({"TON_MODE": None})
        except ConfigError:
            pass
        captured = capsys.readouterr()
        assert "TON_MODE" in captured.err
        assert "CONFIGURATION ERROR" in captured.err

    def test_api_key_not_exposed_in_logs(self, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            load()
        # Full key must never appear in logs
        for record in caplog.records:
            assert "abc123realkey" not in record.message
