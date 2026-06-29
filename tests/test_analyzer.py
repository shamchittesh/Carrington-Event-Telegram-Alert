"""Unit tests for the risk analyzer module."""

import pytest

from src.analyzer import RiskAnalyzer, RiskAssessment, RiskLevel
from src.collector import SpaceWeatherData
from src.config import AppConfig
from src.state import SentAlertState


def _default_config() -> AppConfig:
    """Create a default AppConfig for testing."""
    return AppConfig(
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat-id",
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


def _make_data(
    kp_index=None,
    solar_wind_speed=None,
    bz_component=None,
    xray_flare=None,
) -> SpaceWeatherData:
    """Create a SpaceWeatherData with given values."""
    return SpaceWeatherData(
        timestamp="2026-01-01T00:00:00Z",
        kp_index=kp_index,
        solar_wind_speed=solar_wind_speed,
        bz_component=bz_component,
        xray_flare=xray_flare,
    )


class TestRiskScoring:
    """Tests for the risk score computation."""

    def test_all_none_gives_zero(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data())
        assert result.score == 0
        assert result.level == RiskLevel.NORMAL
        assert result.contributing_factors == []

    def test_x_class_flare_adds_30(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(xray_flare="X1.2"))
        assert result.score == 30
        assert result.level == RiskLevel.WATCH

    def test_m5_flare_adds_15(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(xray_flare="M5.0"))
        assert result.score == 15
        assert result.level == RiskLevel.NORMAL

    def test_m4_flare_adds_nothing(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(xray_flare="M4.9"))
        assert result.score == 0

    def test_solar_wind_above_1000_adds_30(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(solar_wind_speed=1100.0))
        assert result.score == 30

    def test_solar_wind_above_800_adds_20(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(solar_wind_speed=900.0))
        assert result.score == 20

    def test_solar_wind_exactly_1000_adds_20_not_30(self):
        """At exactly 1000, it's not > 1000, so only the > 800 rule applies."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(solar_wind_speed=1000.0))
        assert result.score == 20

    def test_solar_wind_exactly_800_adds_nothing(self):
        """At exactly 800, it's not > 800."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(solar_wind_speed=800.0))
        assert result.score == 0

    def test_bz_below_minus_20_adds_25(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(bz_component=-25.0))
        assert result.score == 25

    def test_bz_below_minus_10_adds_10(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(bz_component=-15.0))
        assert result.score == 10

    def test_bz_exactly_minus_20_adds_10_not_25(self):
        """At exactly -20, it's not < -20, so only the < -10 rule applies."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(bz_component=-20.0))
        assert result.score == 10

    def test_bz_exactly_minus_10_adds_nothing(self):
        """At exactly -10, it's not < -10."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(bz_component=-10.0))
        assert result.score == 0

    def test_kp_8_adds_25(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(kp_index=8.0))
        assert result.score == 25

    def test_kp_7_adds_15(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(kp_index=7.0))
        assert result.score == 15

    def test_kp_7_5_adds_15_not_25(self):
        """Kp 7.5 is >= 7 but < 8, so +15 only."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(kp_index=7.5))
        assert result.score == 15

    def test_superseding_solar_wind_not_additive(self):
        """Solar wind > 1000 gives +30, NOT +20 + +30."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(solar_wind_speed=1500.0))
        assert result.score == 30

    def test_superseding_bz_not_additive(self):
        """Bz < -20 gives +25, NOT +10 + +25."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(bz_component=-30.0))
        assert result.score == 25

    def test_superseding_kp_not_additive(self):
        """Kp >= 8 gives +25, NOT +15 + +25."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(kp_index=9.0))
        assert result.score == 25

    def test_combined_extreme_scenario_clamped_to_100(self):
        """All indicators at max: 30 + 30 + 25 + 25 = 110, clamped to 100."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(
            _make_data(
                xray_flare="X9.9",
                solar_wind_speed=1500.0,
                bz_component=-30.0,
                kp_index=9.0,
            )
        )
        assert result.score == 100
        assert result.level == RiskLevel.EXTREME

    def test_combined_watch_scenario(self):
        """M5 flare (+15) + Kp 7 (+15) = 30 → WATCH."""
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(
            _make_data(xray_flare="M6.0", kp_index=7.0)
        )
        assert result.score == 30
        assert result.level == RiskLevel.WATCH

    def test_contributing_factors_populated(self):
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(
            _make_data(xray_flare="X2.0", solar_wind_speed=900.0)
        )
        assert len(result.contributing_factors) == 2
        assert "X-class flare" in result.contributing_factors[0]
        assert "Solar wind" in result.contributing_factors[1]


class TestRiskLevelClassification:
    """Tests for the risk level classification."""

    def test_normal_range(self):
        analyzer = RiskAnalyzer(_default_config())
        # Score 0 → NORMAL
        result = analyzer.assess(_make_data())
        assert result.level == RiskLevel.NORMAL

    def test_boundary_29_is_normal(self):
        """Score 29 should be NORMAL (the highest NORMAL score)."""
        # Kp 7 (+15) + Bz < -10 (+10) = 25, still NORMAL
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(kp_index=7.0, bz_component=-15.0))
        assert result.score == 25
        assert result.level == RiskLevel.NORMAL

    def test_boundary_30_is_watch(self):
        """Score 30 should be WATCH."""
        # X-class flare (+30) = 30 → WATCH
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(_make_data(xray_flare="X1.0"))
        assert result.score == 30
        assert result.level == RiskLevel.WATCH

    def test_boundary_50_is_warning(self):
        """Score 50 should be WARNING."""
        # X-class (+30) + solar wind > 800 (+20) = 50 → WARNING
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(
            _make_data(xray_flare="X1.0", solar_wind_speed=900.0)
        )
        assert result.score == 50
        assert result.level == RiskLevel.WARNING

    def test_boundary_75_is_extreme(self):
        """Score 75 should be EXTREME."""
        # X-class (+30) + solar wind > 1000 (+30) + Kp >= 7 (+15) = 75 → EXTREME
        analyzer = RiskAnalyzer(_default_config())
        result = analyzer.assess(
            _make_data(xray_flare="X1.0", solar_wind_speed=1100.0, kp_index=7.0)
        )
        assert result.score == 75
        assert result.level == RiskLevel.EXTREME


class TestShouldAlert:
    """Tests for the alert triggering logic."""

    def test_first_alert_always_triggers(self):
        analyzer = RiskAnalyzer(_default_config())
        assessment = analyzer.assess(_make_data())
        prev = SentAlertState(last_status=None, last_score=None, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is True

    def test_level_change_triggers_alert(self):
        analyzer = RiskAnalyzer(_default_config())
        assessment = analyzer.assess(_make_data(xray_flare="X1.0"))  # WATCH
        prev = SentAlertState(last_status="NORMAL", last_score=0, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is True

    def test_score_delta_15_triggers_alert(self):
        analyzer = RiskAnalyzer(_default_config())
        # Kp 7 (+15) → score 15, level NORMAL
        assessment = analyzer.assess(_make_data(kp_index=7.0))
        # Previous was NORMAL with score 0, delta is 15
        prev = SentAlertState(last_status="NORMAL", last_score=0, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is True

    def test_score_delta_14_does_not_trigger(self):
        analyzer = RiskAnalyzer(_default_config())
        # Bz < -10 (+10) → score 10, level NORMAL
        assessment = analyzer.assess(_make_data(bz_component=-15.0))
        # Previous was NORMAL with score 0, delta is 10
        prev = SentAlertState(last_status="NORMAL", last_score=0, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is False

    def test_new_x_class_flare_triggers_alert(self):
        analyzer = RiskAnalyzer(_default_config())
        assessment = analyzer.assess(_make_data(xray_flare="X2.5"))
        prev = SentAlertState(
            last_status="WATCH",
            last_score=30,
            last_event_id="2025-12-31T23:00:00Z-X1.0",
        )
        assert analyzer.should_alert(assessment, prev) is True

    def test_same_x_class_flare_does_not_trigger(self):
        analyzer = RiskAnalyzer(_default_config())
        data = _make_data(xray_flare="X1.0")
        assessment = analyzer.assess(data)
        # Event ID matches current data
        prev = SentAlertState(
            last_status="WATCH",
            last_score=30,
            last_event_id="2026-01-01T00:00:00Z-X1.0",
        )
        assert analyzer.should_alert(assessment, prev) is False

    def test_no_change_suppresses_alert(self):
        analyzer = RiskAnalyzer(_default_config())
        # Score 10, level NORMAL
        assessment = analyzer.assess(_make_data(bz_component=-15.0))
        prev = SentAlertState(last_status="NORMAL", last_score=10, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is False

    def test_m_class_flare_does_not_trigger_x_flare_rule(self):
        """M-class flares shouldn't trigger the 'new X-class flare' alert rule."""
        analyzer = RiskAnalyzer(_default_config())
        assessment = analyzer.assess(_make_data(xray_flare="M7.0"))
        prev = SentAlertState(last_status="NORMAL", last_score=15, last_event_id=None)
        assert analyzer.should_alert(assessment, prev) is False
