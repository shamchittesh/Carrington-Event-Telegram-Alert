"""Configuration management for CarringtonWatch Bot.

Loads configuration from environment variables with fallback to config/settings.json.
Uses python-dotenv for .env file loading.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root is one level up from the src/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration."""

    telegram_bot_token: str
    telegram_chat_id: str
    poll_interval_minutes: int
    x_flare_threshold: str
    high_solar_wind: int
    extreme_solar_wind: int
    high_negative_bz: int
    extreme_negative_bz: int
    kp_warning: int
    kp_extreme: int
    enable_debug: bool


def _load_settings_file() -> dict:
    """Load settings from JSON file. Returns empty dict on failure."""
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load settings file %s: %s", SETTINGS_PATH, e)
        return {}


def _parse_bool(value: str) -> bool:
    """Parse a string value to boolean."""
    return value.strip().lower() in ("true", "1", "yes")


def load_config() -> AppConfig:
    """Load configuration from environment variables with fallback to config/settings.json.

    Priority: environment variables > .env file > config/settings.json > defaults.
    """
    # Load .env file if it exists (does not override existing env vars)
    load_dotenv(PROJECT_ROOT / ".env")

    # Load fallback values from settings.json
    settings = _load_settings_file()

    # Read values with env var priority, then settings.json fallback, then defaults
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    poll_interval_minutes = int(
        os.getenv(
            "POLL_INTERVAL_MINUTES",
            str(settings.get("poll_interval_minutes", 15)),
        )
    )

    x_flare_threshold = os.getenv(
        "X_FLARE_THRESHOLD",
        str(settings.get("x_flare_threshold", "X1")),
    )

    high_solar_wind = int(
        os.getenv(
            "HIGH_SOLAR_WIND",
            str(settings.get("high_solar_wind", 800)),
        )
    )

    extreme_solar_wind = int(
        os.getenv(
            "EXTREME_SOLAR_WIND",
            str(settings.get("extreme_solar_wind", 1000)),
        )
    )

    high_negative_bz = int(
        os.getenv(
            "HIGH_NEGATIVE_BZ",
            str(settings.get("high_negative_bz", -10)),
        )
    )

    extreme_negative_bz = int(
        os.getenv(
            "EXTREME_NEGATIVE_BZ",
            str(settings.get("extreme_negative_bz", -20)),
        )
    )

    kp_warning = int(
        os.getenv(
            "KP_WARNING",
            str(settings.get("kp_warning", 7)),
        )
    )

    kp_extreme = int(
        os.getenv(
            "KP_EXTREME",
            str(settings.get("kp_extreme", 8)),
        )
    )

    enable_debug_env = os.getenv("ENABLE_DEBUG")
    if enable_debug_env is not None:
        enable_debug = _parse_bool(enable_debug_env)
    else:
        enable_debug = bool(settings.get("enable_debug", False))

    return AppConfig(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        poll_interval_minutes=poll_interval_minutes,
        x_flare_threshold=x_flare_threshold,
        high_solar_wind=high_solar_wind,
        extreme_solar_wind=extreme_solar_wind,
        high_negative_bz=high_negative_bz,
        extreme_negative_bz=extreme_negative_bz,
        kp_warning=kp_warning,
        kp_extreme=kp_extreme,
        enable_debug=enable_debug,
    )


def validate_config(config: AppConfig) -> list[str]:
    """Validate configuration and return list of errors. Empty list means valid."""
    errors: list[str] = []

    # Required fields
    if not config.telegram_bot_token:
        errors.append("TELEGRAM_BOT_TOKEN is required but not set")
    if not config.telegram_chat_id:
        errors.append("TELEGRAM_CHAT_ID is required but not set")

    # Numeric range validations
    if config.poll_interval_minutes < 1:
        errors.append(
            f"POLL_INTERVAL_MINUTES must be at least 1, got {config.poll_interval_minutes}"
        )

    if config.high_solar_wind <= 0:
        errors.append(
            f"HIGH_SOLAR_WIND must be positive, got {config.high_solar_wind}"
        )

    if config.extreme_solar_wind <= config.high_solar_wind:
        errors.append(
            f"EXTREME_SOLAR_WIND ({config.extreme_solar_wind}) must be greater than "
            f"HIGH_SOLAR_WIND ({config.high_solar_wind})"
        )

    if config.high_negative_bz >= 0:
        errors.append(
            f"HIGH_NEGATIVE_BZ must be negative, got {config.high_negative_bz}"
        )

    if config.extreme_negative_bz >= config.high_negative_bz:
        errors.append(
            f"EXTREME_NEGATIVE_BZ ({config.extreme_negative_bz}) must be less than "
            f"HIGH_NEGATIVE_BZ ({config.high_negative_bz})"
        )

    if not (0 <= config.kp_warning <= 9):
        errors.append(
            f"KP_WARNING must be between 0 and 9, got {config.kp_warning}"
        )

    if not (0 <= config.kp_extreme <= 9):
        errors.append(
            f"KP_EXTREME must be between 0 and 9, got {config.kp_extreme}"
        )

    if config.kp_extreme <= config.kp_warning:
        errors.append(
            f"KP_EXTREME ({config.kp_extreme}) must be greater than "
            f"KP_WARNING ({config.kp_warning})"
        )

    return errors
