"""Unit tests for the TelegramNotifier class and command handlers."""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Bot, Update, Message, Chat, User
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from src.analyzer import RiskAssessment, RiskLevel
from src.collector import SpaceWeatherData
from src.notifier import (
    CARRINGTON_DISCLAIMER,
    LEVEL_EMOJI,
    LEVEL_HEADER,
    TelegramNotifier,
    register_commands,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_bot() -> AsyncMock:
    """Create a mock Bot instance."""
    bot = AsyncMock(spec=Bot)
    return bot


@pytest.fixture
def notifier(mock_bot: AsyncMock) -> TelegramNotifier:
    """Create a TelegramNotifier with mocked bot."""
    return TelegramNotifier(bot=mock_bot, chat_id="123456")


@pytest.fixture
def sample_data() -> SpaceWeatherData:
    """Create sample space weather data."""
    return SpaceWeatherData(
        timestamp="2026-07-21T12:35:00Z",
        kp_index=6.0,
        solar_wind_speed=780.0,
        bz_component=-17.0,
        xray_flare="X1.2",
    )


@pytest.fixture
def normal_assessment(sample_data: SpaceWeatherData) -> RiskAssessment:
    """Create a NORMAL level assessment."""
    return RiskAssessment(
        score=15,
        level=RiskLevel.NORMAL,
        contributing_factors=[],
        data=sample_data,
    )


@pytest.fixture
def watch_assessment(sample_data: SpaceWeatherData) -> RiskAssessment:
    """Create a WATCH level assessment."""
    return RiskAssessment(
        score=35,
        level=RiskLevel.WATCH,
        contributing_factors=["Kp >= 7 (7.0): +15", "Solar wind > 800 km/s (850): +20"],
        data=sample_data,
    )


@pytest.fixture
def warning_assessment(sample_data: SpaceWeatherData) -> RiskAssessment:
    """Create a WARNING level assessment."""
    return RiskAssessment(
        score=62,
        level=RiskLevel.WARNING,
        contributing_factors=[
            "X-class flare detected (X1.2): +30",
            "Bz < -10 nT (-17.0): +10",
            "Kp >= 7 (6.0): +15",
        ],
        data=sample_data,
    )


@pytest.fixture
def extreme_assessment(sample_data: SpaceWeatherData) -> RiskAssessment:
    """Create an EXTREME level assessment."""
    return RiskAssessment(
        score=85,
        level=RiskLevel.EXTREME,
        contributing_factors=[
            "X-class flare detected (X2.5): +30",
            "Solar wind > 1000 km/s (1200): +30",
            "Bz < -20 nT (-25.0): +25",
        ],
        data=sample_data,
    )


# ── TelegramNotifier.send_alert() tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_send_alert_normal(
    notifier: TelegramNotifier, mock_bot: AsyncMock, normal_assessment: RiskAssessment
) -> None:
    """NORMAL alerts include green emoji, header, and score."""
    result = await notifier.send_alert(normal_assessment)
    assert result is True

    call_args = mock_bot.send_message.call_args
    message = call_args.kwargs["text"]

    assert "🟢" in message
    assert "Space Weather Status: NORMAL" in message
    assert "Risk Score: 15/100" in message
    # No contributing factors for NORMAL
    assert "Contributing Factors:" not in message
    # No disclaimer for NORMAL
    assert CARRINGTON_DISCLAIMER not in message


@pytest.mark.asyncio
async def test_send_alert_watch(
    notifier: TelegramNotifier, mock_bot: AsyncMock, watch_assessment: RiskAssessment
) -> None:
    """WATCH alerts include yellow emoji, header, score, and factors."""
    result = await notifier.send_alert(watch_assessment)
    assert result is True

    call_args = mock_bot.send_message.call_args
    message = call_args.kwargs["text"]

    assert "🟡" in message
    assert "CarringtonWatch: WATCH" in message
    assert "Risk Score: 35/100" in message
    assert "Contributing Factors:" in message
    assert "Kp >= 7 (7.0): +15" in message
    # No disclaimer for WATCH
    assert CARRINGTON_DISCLAIMER not in message


@pytest.mark.asyncio
async def test_send_alert_warning(
    notifier: TelegramNotifier, mock_bot: AsyncMock, warning_assessment: RiskAssessment
) -> None:
    """WARNING alerts include orange emoji, header, score, and factors."""
    result = await notifier.send_alert(warning_assessment)
    assert result is True

    call_args = mock_bot.send_message.call_args
    message = call_args.kwargs["text"]

    assert "🟠" in message
    assert "CarringtonWatch Warning" in message
    assert "Risk Score: 62/100" in message
    assert "Contributing Factors:" in message
    assert "X-class flare detected (X1.2): +30" in message
    assert CARRINGTON_DISCLAIMER not in message


@pytest.mark.asyncio
async def test_send_alert_extreme(
    notifier: TelegramNotifier, mock_bot: AsyncMock, extreme_assessment: RiskAssessment
) -> None:
    """EXTREME alerts include red emoji, header, score, factors, and disclaimer."""
    result = await notifier.send_alert(extreme_assessment)
    assert result is True

    call_args = mock_bot.send_message.call_args
    message = call_args.kwargs["text"]

    assert "🔴" in message
    assert "CarringtonWatch Extreme Alert" in message
    assert "Risk Score: 85/100" in message
    assert "Contributing Factors:" in message
    assert "X-class flare detected (X2.5): +30" in message
    assert CARRINGTON_DISCLAIMER in message


@pytest.mark.asyncio
async def test_send_alert_telegram_error(
    notifier: TelegramNotifier, mock_bot: AsyncMock, normal_assessment: RiskAssessment
) -> None:
    """Telegram API errors are caught and False is returned."""
    mock_bot.send_message.side_effect = TelegramError("Network error")
    result = await notifier.send_alert(normal_assessment)
    assert result is False


# ── TelegramNotifier.send_status() tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_send_status_contains_all_fields(
    notifier: TelegramNotifier, warning_assessment: RiskAssessment
) -> None:
    """Status response contains all required fields."""
    message = await notifier.send_status(warning_assessment)

    assert "Risk Level: WARNING" in message
    assert "Risk Score: 62/100" in message
    assert "X-Ray Flare: X1.2" in message
    assert "Solar Wind Speed: 780 km/s" in message
    assert "Bz Component: -17.0 nT" in message
    assert "Kp Index: 6.0" in message
    assert "Last Update: 2026-07-21T12:35:00Z" in message


@pytest.mark.asyncio
async def test_send_status_handles_none_values(
    notifier: TelegramNotifier,
) -> None:
    """Status handles None measurement values gracefully."""
    data = SpaceWeatherData(
        timestamp="2026-01-01T00:00:00Z",
        kp_index=None,
        solar_wind_speed=None,
        bz_component=None,
        xray_flare=None,
    )
    assessment = RiskAssessment(
        score=0, level=RiskLevel.NORMAL, contributing_factors=[], data=data
    )

    message = await notifier.send_status(assessment)

    assert "X-Ray Flare: None detected" in message
    assert "Solar Wind Speed: N/A" in message
    assert "Bz Component: N/A" in message
    assert "Kp Index: N/A" in message


# ── TelegramNotifier.send_risk_explanation() tests ───────────────────────────


@pytest.mark.asyncio
async def test_send_risk_explanation_with_factors(
    notifier: TelegramNotifier, warning_assessment: RiskAssessment
) -> None:
    """Risk explanation includes factors and score ranges."""
    message = await notifier.send_risk_explanation(warning_assessment)

    assert "Risk Assessment Breakdown" in message
    assert "Current Level: WARNING" in message
    assert "Risk Score: 62/100" in message
    assert "Contributing Factors:" in message
    assert "X-class flare detected (X1.2): +30" in message
    assert "Score Ranges:" in message
    assert "🟢 NORMAL: 0-29" in message
    assert "🔴 EXTREME: 75-100" in message


@pytest.mark.asyncio
async def test_send_risk_explanation_no_factors(
    notifier: TelegramNotifier, normal_assessment: RiskAssessment
) -> None:
    """Risk explanation shows 'no factors' when none exist."""
    message = await notifier.send_risk_explanation(normal_assessment)

    assert "No significant risk factors detected." in message


# ── TelegramNotifier.send_history() tests ────────────────────────────────────


@pytest.mark.asyncio
async def test_send_history_empty(notifier: TelegramNotifier) -> None:
    """History shows 'no history' message when empty."""
    message = await notifier.send_history([])

    assert "Risk History" in message
    assert "No history available yet." in message


@pytest.mark.asyncio
async def test_send_history_shows_last_10(notifier: TelegramNotifier) -> None:
    """History shows only the last 10 entries."""
    history = [
        {"timestamp": f"2026-01-01T{i:02d}:00:00Z", "risk": i * 5}
        for i in range(15)
    ]

    message = await notifier.send_history(history)

    # Should show entries 5-14 (last 10)
    assert "2026-01-01T05:00:00Z" in message
    assert "2026-01-01T14:00:00Z" in message
    # Should NOT show entries 0-4
    assert "2026-01-01T04:00:00Z" not in message


@pytest.mark.asyncio
async def test_send_history_fewer_than_10(notifier: TelegramNotifier) -> None:
    """History shows all entries when fewer than 10."""
    history = [
        {"timestamp": "2026-01-01T00:00:00Z", "risk": 25},
        {"timestamp": "2026-01-01T01:00:00Z", "risk": 42},
    ]

    message = await notifier.send_history(history)

    assert "2026-01-01T00:00:00Z" in message
    assert "Risk: 25" in message
    assert "2026-01-01T01:00:00Z" in message
    assert "Risk: 42" in message
