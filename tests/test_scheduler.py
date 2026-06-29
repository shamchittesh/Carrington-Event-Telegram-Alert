"""Tests for the PollOrchestrator scheduler module."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyzer import RiskAssessment, RiskLevel
from src.collector import SpaceWeatherData
from src.scheduler import PollOrchestrator
from src.state import SentAlertState


@pytest.fixture
def sample_data():
    """Create sample SpaceWeatherData."""
    return SpaceWeatherData(
        timestamp="2026-07-21T12:35:00Z",
        kp_index=6.0,
        solar_wind_speed=780.0,
        bz_component=-17.0,
        xray_flare="X1.2",
    )


@pytest.fixture
def sample_assessment(sample_data):
    """Create sample RiskAssessment."""
    return RiskAssessment(
        score=62,
        level=RiskLevel.WARNING,
        contributing_factors=["X-class flare detected (X1.2): +30"],
        data=sample_data,
    )


@pytest.fixture
def mock_collector(sample_data):
    """Create a mock collector that returns sample data."""
    collector = MagicMock()
    collector.collect.return_value = sample_data
    return collector


@pytest.fixture
def mock_analyzer(sample_assessment):
    """Create a mock analyzer that returns sample assessment."""
    analyzer = MagicMock()
    analyzer.assess.return_value = sample_assessment
    analyzer.should_alert.return_value = True
    return analyzer


@pytest.fixture
def mock_notifier():
    """Create a mock notifier."""
    notifier = MagicMock()
    notifier.send_alert = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    state_manager = MagicMock()
    state_manager.read_sent_alerts.return_value = SentAlertState(
        last_status=None, last_score=None, last_event_id=None
    )
    return state_manager


@pytest.fixture
def orchestrator(mock_collector, mock_analyzer, mock_notifier, mock_state_manager):
    """Create a PollOrchestrator with mock dependencies."""
    return PollOrchestrator(
        collector=mock_collector,
        analyzer=mock_analyzer,
        notifier=mock_notifier,
        state_manager=mock_state_manager,
    )


@pytest.fixture
def mock_context():
    """Create a mock CallbackContext."""
    return MagicMock()


@pytest.mark.asyncio
async def test_execute_poll_cycle_sends_alert(
    orchestrator, mock_collector, mock_analyzer, mock_notifier, mock_state_manager, mock_context, sample_data, sample_assessment
):
    """Test full poll cycle sends alert when should_alert returns True."""
    await orchestrator.execute_poll_cycle(mock_context)

    # Collector was called
    mock_collector.collect.assert_called_once()

    # Analyzer assess was called with the collected data
    mock_analyzer.assess.assert_called_once_with(sample_data)

    # should_alert was called
    mock_analyzer.should_alert.assert_called_once()

    # Alert was sent
    mock_notifier.send_alert.assert_awaited_once_with(sample_assessment)

    # State was updated
    mock_state_manager.write_latest.assert_called_once_with(asdict(sample_data))
    mock_state_manager.append_history.assert_called_once_with(
        {"timestamp": sample_data.timestamp, "risk": sample_assessment.score}
    )
    mock_state_manager.write_sent_alerts.assert_called_once()


@pytest.mark.asyncio
async def test_execute_poll_cycle_suppresses_alert(
    orchestrator, mock_analyzer, mock_notifier, mock_state_manager, mock_context
):
    """Test poll cycle suppresses alert when should_alert returns False."""
    mock_analyzer.should_alert.return_value = False

    await orchestrator.execute_poll_cycle(mock_context)

    # Alert was NOT sent
    mock_notifier.send_alert.assert_not_awaited()

    # State files still updated (latest, history)
    mock_state_manager.write_latest.assert_called_once()
    mock_state_manager.append_history.assert_called_once()

    # Sent alerts state NOT updated (no alert was sent)
    mock_state_manager.write_sent_alerts.assert_not_called()


@pytest.mark.asyncio
async def test_execute_poll_cycle_handles_send_failure(
    orchestrator, mock_notifier, mock_state_manager, mock_context
):
    """Test poll cycle handles Telegram send failure gracefully."""
    mock_notifier.send_alert = AsyncMock(return_value=False)

    await orchestrator.execute_poll_cycle(mock_context)

    # Alert send attempted
    mock_notifier.send_alert.assert_awaited_once()

    # Sent alerts state NOT updated on failure
    mock_state_manager.write_sent_alerts.assert_not_called()

    # Latest and history still updated
    mock_state_manager.write_latest.assert_called_once()
    mock_state_manager.append_history.assert_called_once()


@pytest.mark.asyncio
async def test_execute_poll_cycle_handles_collector_exception(
    orchestrator, mock_collector, mock_notifier, mock_state_manager, mock_context
):
    """Test poll cycle catches collector exceptions without crashing."""
    mock_collector.collect.side_effect = Exception("Network error")

    # Should not raise
    await orchestrator.execute_poll_cycle(mock_context)

    # Nothing else should have been called after the failure
    mock_notifier.send_alert.assert_not_awaited()
    mock_state_manager.write_latest.assert_not_called()


@pytest.mark.asyncio
async def test_execute_poll_cycle_handles_analyzer_exception(
    orchestrator, mock_analyzer, mock_notifier, mock_state_manager, mock_context
):
    """Test poll cycle catches analyzer exceptions without crashing."""
    mock_analyzer.assess.side_effect = RuntimeError("Scoring error")

    # Should not raise
    await orchestrator.execute_poll_cycle(mock_context)

    # Alert should not be sent
    mock_notifier.send_alert.assert_not_awaited()
    mock_state_manager.write_latest.assert_not_called()


@pytest.mark.asyncio
async def test_execute_poll_cycle_handles_state_read_exception(
    orchestrator, mock_state_manager, mock_notifier, mock_context
):
    """Test poll cycle catches state read exceptions without crashing."""
    mock_state_manager.read_sent_alerts.side_effect = OSError("File read error")

    # Should not raise
    await orchestrator.execute_poll_cycle(mock_context)

    # Alert should not be sent
    mock_notifier.send_alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_poll_cycle_updates_sent_alert_state_correctly(
    orchestrator, mock_state_manager, mock_context, sample_assessment
):
    """Test that sent_alerts state is updated with correct values after alert send."""
    await orchestrator.execute_poll_cycle(mock_context)

    call_args = mock_state_manager.write_sent_alerts.call_args[0][0]
    assert call_args.last_status == sample_assessment.level.value
    assert call_args.last_score == sample_assessment.score
    assert call_args.last_event_id == f"{sample_assessment.data.timestamp}-{sample_assessment.data.xray_flare}"


@pytest.mark.asyncio
async def test_execute_poll_cycle_never_propagates_exceptions(
    mock_context,
):
    """Test that no exception escapes execute_poll_cycle regardless of error source."""
    # Create orchestrator with all-failing mocks
    collector = MagicMock()
    collector.collect.side_effect = Exception("boom")
    analyzer = MagicMock()
    notifier = MagicMock()
    state_manager = MagicMock()

    orchestrator = PollOrchestrator(
        collector=collector,
        analyzer=analyzer,
        notifier=notifier,
        state_manager=state_manager,
    )

    # Must not raise
    await orchestrator.execute_poll_cycle(mock_context)
