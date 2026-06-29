"""Unit tests for configuration module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import AppConfig, load_config, validate_config


class TestAppConfig:
    """Tests for the AppConfig dataclass."""

    def test_appconfig_is_frozen(self):
        """AppConfig instances should be immutable."""
        config = AppConfig(
            telegram_bot_token="token",
            telegram_chat_id="123",
            poll_interval_minutes=15,
            x_flare_threshold="X1",
            high_solar_wind=800,
            extreme_solar_wind=1000,
            high_negative_bz=-10,
            extreme_negative_bz=-20,
            kp_warning=7,
            kp_extreme=8,
            enable_debug=False,
        )
        with pytest.raises(Exception):
            config.telegram_bot_token = "new_token"  # type: ignore


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_from_env_vars(self, monkeypatch, tmp_path):
        """Environment variables should take priority."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat-id")
        monkeypatch.setenv("POLL_INTERVAL_MINUTES", "30")
        monkeypatch.setenv("ENABLE_DEBUG", "true")
        monkeypatch.setenv("X_FLARE_THRESHOLD", "X2")
        monkeypatch.setenv("HIGH_SOLAR_WIND", "900")
        monkeypatch.setenv("EXTREME_SOLAR_WIND", "1200")
        monkeypatch.setenv("HIGH_NEGATIVE_BZ", "-15")
        monkeypatch.setenv("EXTREME_NEGATIVE_BZ", "-25")
        monkeypatch.setenv("KP_WARNING", "6")
        monkeypatch.setenv("KP_EXTREME", "9")

        config = load_config()

        assert config.telegram_bot_token == "env-token"
        assert config.telegram_chat_id == "env-chat-id"
        assert config.poll_interval_minutes == 30
        assert config.enable_debug is True
        assert config.x_flare_threshold == "X2"
        assert config.high_solar_wind == 900
        assert config.extreme_solar_wind == 1200
        assert config.high_negative_bz == -15
        assert config.extreme_negative_bz == -25
        assert config.kp_warning == 6
        assert config.kp_extreme == 9

    def test_falls_back_to_settings_json(self, monkeypatch, tmp_path):
        """When env vars are not set, should fall back to settings.json values."""
        # Clear any env vars that might interfere
        for key in [
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "POLL_INTERVAL_MINUTES",
            "ENABLE_DEBUG", "X_FLARE_THRESHOLD", "HIGH_SOLAR_WIND",
            "EXTREME_SOLAR_WIND", "HIGH_NEGATIVE_BZ", "EXTREME_NEGATIVE_BZ",
            "KP_WARNING", "KP_EXTREME",
        ]:
            monkeypatch.delenv(key, raising=False)

        settings = {
            "poll_interval_minutes": 20,
            "x_flare_threshold": "X1",
            "high_solar_wind": 800,
            "extreme_solar_wind": 1000,
            "high_negative_bz": -10,
            "extreme_negative_bz": -20,
            "kp_warning": 7,
            "kp_extreme": 8,
            "enable_debug": True,
        }
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        with patch("src.config.SETTINGS_PATH", settings_path):
            config = load_config()

        assert config.poll_interval_minutes == 20
        assert config.x_flare_threshold == "X1"
        assert config.high_solar_wind == 800
        assert config.extreme_solar_wind == 1000
        assert config.high_negative_bz == -10
        assert config.extreme_negative_bz == -20
        assert config.kp_warning == 7
        assert config.kp_extreme == 8
        assert config.enable_debug is True

    def test_defaults_when_no_env_or_settings(self, monkeypatch, tmp_path):
        """When neither env vars nor settings.json exist, defaults should be used."""
        for key in [
            "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "POLL_INTERVAL_MINUTES",
            "ENABLE_DEBUG", "X_FLARE_THRESHOLD", "HIGH_SOLAR_WIND",
            "EXTREME_SOLAR_WIND", "HIGH_NEGATIVE_BZ", "EXTREME_NEGATIVE_BZ",
            "KP_WARNING", "KP_EXTREME",
        ]:
            monkeypatch.delenv(key, raising=False)

        missing_path = tmp_path / "nonexistent.json"

        with patch("src.config.SETTINGS_PATH", missing_path):
            config = load_config()

        assert config.telegram_bot_token == ""
        assert config.telegram_chat_id == ""
        assert config.poll_interval_minutes == 15
        assert config.x_flare_threshold == "X1"
        assert config.high_solar_wind == 800
        assert config.extreme_solar_wind == 1000
        assert config.high_negative_bz == -10
        assert config.extreme_negative_bz == -20
        assert config.kp_warning == 7
        assert config.kp_extreme == 8
        assert config.enable_debug is False

    def test_env_vars_override_settings_json(self, monkeypatch, tmp_path):
        """Env vars should override settings.json values."""
        monkeypatch.setenv("POLL_INTERVAL_MINUTES", "5")

        settings = {"poll_interval_minutes": 20}
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps(settings))

        with patch("src.config.SETTINGS_PATH", settings_path):
            config = load_config()

        assert config.poll_interval_minutes == 5

    def test_enable_debug_parsing(self, monkeypatch, tmp_path):
        """ENABLE_DEBUG should handle various truthy/falsy values."""
        missing_path = tmp_path / "nonexistent.json"

        for value, expected in [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("", False),
        ]:
            monkeypatch.setenv("ENABLE_DEBUG", value)
            with patch("src.config.SETTINGS_PATH", missing_path):
                config = load_config()
            assert config.enable_debug is expected, f"Failed for ENABLE_DEBUG={value!r}"


class TestValidateConfig:
    """Tests for validate_config function."""

    def _valid_config(self, **overrides) -> AppConfig:
        """Create a valid config with optional overrides."""
        defaults = {
            "telegram_bot_token": "valid-token",
            "telegram_chat_id": "123456",
            "poll_interval_minutes": 15,
            "x_flare_threshold": "X1",
            "high_solar_wind": 800,
            "extreme_solar_wind": 1000,
            "high_negative_bz": -10,
            "extreme_negative_bz": -20,
            "kp_warning": 7,
            "kp_extreme": 8,
            "enable_debug": False,
        }
        defaults.update(overrides)
        return AppConfig(**defaults)

    def test_valid_config_returns_empty_list(self):
        """A fully valid config should have no validation errors."""
        config = self._valid_config()
        errors = validate_config(config)
        assert errors == []

    def test_missing_bot_token(self):
        """Missing bot token should produce an error."""
        config = self._valid_config(telegram_bot_token="")
        errors = validate_config(config)
        assert any("TELEGRAM_BOT_TOKEN" in e for e in errors)

    def test_missing_chat_id(self):
        """Missing chat ID should produce an error."""
        config = self._valid_config(telegram_chat_id="")
        errors = validate_config(config)
        assert any("TELEGRAM_CHAT_ID" in e for e in errors)

    def test_invalid_poll_interval(self):
        """Poll interval less than 1 should produce an error."""
        config = self._valid_config(poll_interval_minutes=0)
        errors = validate_config(config)
        assert any("POLL_INTERVAL_MINUTES" in e for e in errors)

    def test_invalid_solar_wind_thresholds(self):
        """extreme_solar_wind must be greater than high_solar_wind."""
        config = self._valid_config(high_solar_wind=1000, extreme_solar_wind=800)
        errors = validate_config(config)
        assert any("EXTREME_SOLAR_WIND" in e for e in errors)

    def test_invalid_bz_thresholds(self):
        """extreme_negative_bz must be less than high_negative_bz."""
        config = self._valid_config(high_negative_bz=-20, extreme_negative_bz=-10)
        errors = validate_config(config)
        assert any("EXTREME_NEGATIVE_BZ" in e for e in errors)

    def test_invalid_kp_thresholds(self):
        """kp_extreme must be greater than kp_warning."""
        config = self._valid_config(kp_warning=8, kp_extreme=7)
        errors = validate_config(config)
        assert any("KP_EXTREME" in e for e in errors)

    def test_multiple_errors_reported(self):
        """Multiple validation issues should all be reported."""
        config = self._valid_config(
            telegram_bot_token="",
            telegram_chat_id="",
            poll_interval_minutes=0,
        )
        errors = validate_config(config)
        assert len(errors) >= 3
