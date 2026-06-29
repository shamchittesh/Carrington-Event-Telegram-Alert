"""Risk analysis engine for CarringtonWatch Bot.

Computes heuristic risk scores from space weather indicators and determines
whether alerts should be sent based on state changes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from src.collector import SpaceWeatherData
from src.config import AppConfig
from src.state import SentAlertState

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level classification derived from risk score."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    EXTREME = "EXTREME"


@dataclass
class RiskAssessment:
    """Result of heuristic risk scoring."""

    score: int  # 0-100, clamped
    level: RiskLevel
    contributing_factors: list[str]  # Human-readable driver descriptions
    data: SpaceWeatherData  # Source measurements


class RiskAnalyzer:
    """Computes heuristic risk score from space weather data."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def assess(self, data: SpaceWeatherData) -> RiskAssessment:
        """Compute risk score and classify level.

        Applies additive scoring rules with higher-tier thresholds superseding
        lower-tier thresholds for the same indicator. Final score is clamped
        to [0, 100].
        """
        score = 0
        factors: list[str] = []

        # ── X-ray flare scoring ──────────────────────────────────────────
        score, factors = self._score_flare(data, score, factors)

        # ── Solar wind speed scoring ─────────────────────────────────────
        score, factors = self._score_solar_wind(data, score, factors)

        # ── Bz component scoring ─────────────────────────────────────────
        score, factors = self._score_bz(data, score, factors)

        # ── Kp index scoring ─────────────────────────────────────────────
        score, factors = self._score_kp(data, score, factors)

        # ── Clamp to [0, 100] ────────────────────────────────────────────
        score = max(0, min(100, score))

        # ── Classify risk level ──────────────────────────────────────────
        level = self._classify(score)

        return RiskAssessment(
            score=score,
            level=level,
            contributing_factors=factors,
            data=data,
        )

    def should_alert(
        self,
        current: RiskAssessment,
        previous_state: SentAlertState,
    ) -> bool:
        """Determine if an alert should be sent based on suppression rules.

        An alert is sent when at least one condition is true:
        1. Risk level changed from previous alert
        2. Risk score changed by >= 15 points since last alert
        3. A new X-class flare appeared that wasn't in the previous alert
        """
        # If no previous alert has been sent, always alert (unless NORMAL with no data)
        if previous_state.last_status is None:
            return True

        # Condition 1: Level changed
        if current.level.value != previous_state.last_status:
            return True

        # Condition 2: Score delta >= 15
        if previous_state.last_score is not None:
            delta = abs(current.score - previous_state.last_score)
            if delta >= 15:
                return True

        # Condition 3: New X-class flare
        if current.data.xray_flare and self._is_x_class(current.data.xray_flare):
            # Build a current event ID from the data
            current_event_id = self._build_event_id(current)
            if current_event_id != previous_state.last_event_id:
                return True

        return False

    def _score_flare(
        self,
        data: SpaceWeatherData,
        score: int,
        factors: list[str],
    ) -> tuple[int, list[str]]:
        """Score X-ray flare indicator."""
        if data.xray_flare is None:
            return score, factors

        flare = data.xray_flare.strip()
        if not flare:
            return score, factors

        if self._is_x_class(flare):
            score += 30
            factors.append(f"X-class flare detected ({flare}): +30")
        elif self._is_m5_or_higher(flare):
            score += 15
            factors.append(f"M5+ flare detected ({flare}): +15")

        return score, factors

    def _score_solar_wind(
        self,
        data: SpaceWeatherData,
        score: int,
        factors: list[str],
    ) -> tuple[int, list[str]]:
        """Score solar wind speed indicator. Higher tier supersedes lower."""
        if data.solar_wind_speed is None:
            return score, factors

        speed = data.solar_wind_speed

        if speed > self._config.extreme_solar_wind:
            score += 30
            factors.append(
                f"Solar wind > {self._config.extreme_solar_wind} km/s ({speed:.0f}): +30"
            )
        elif speed > self._config.high_solar_wind:
            score += 20
            factors.append(
                f"Solar wind > {self._config.high_solar_wind} km/s ({speed:.0f}): +20"
            )

        return score, factors

    def _score_bz(
        self,
        data: SpaceWeatherData,
        score: int,
        factors: list[str],
    ) -> tuple[int, list[str]]:
        """Score Bz component indicator. Higher tier supersedes lower."""
        if data.bz_component is None:
            return score, factors

        bz = data.bz_component

        if bz < self._config.extreme_negative_bz:
            score += 25
            factors.append(
                f"Bz < {self._config.extreme_negative_bz} nT ({bz:.1f}): +25"
            )
        elif bz < self._config.high_negative_bz:
            score += 10
            factors.append(
                f"Bz < {self._config.high_negative_bz} nT ({bz:.1f}): +10"
            )

        return score, factors

    def _score_kp(
        self,
        data: SpaceWeatherData,
        score: int,
        factors: list[str],
    ) -> tuple[int, list[str]]:
        """Score Kp index indicator. Higher tier supersedes lower."""
        if data.kp_index is None:
            return score, factors

        kp = data.kp_index

        if kp >= self._config.kp_extreme:
            score += 25
            factors.append(f"Kp >= {self._config.kp_extreme} ({kp:.1f}): +25")
        elif kp >= self._config.kp_warning:
            score += 15
            factors.append(f"Kp >= {self._config.kp_warning} ({kp:.1f}): +15")

        return score, factors

    @staticmethod
    def _classify(score: int) -> RiskLevel:
        """Classify a clamped score into a risk level."""
        if score >= 75:
            return RiskLevel.EXTREME
        elif score >= 50:
            return RiskLevel.WARNING
        elif score >= 30:
            return RiskLevel.WATCH
        else:
            return RiskLevel.NORMAL

    @staticmethod
    def _is_x_class(flare: str) -> bool:
        """Check if a flare classification is X-class."""
        return flare.upper().startswith("X")

    @staticmethod
    def _is_m5_or_higher(flare: str) -> bool:
        """Check if a flare classification is M5.0 or higher (but not X-class)."""
        upper = flare.upper()
        if not upper.startswith("M"):
            return False
        # Extract the numeric portion after the M
        match = re.match(r"M(\d+\.?\d*)", upper)
        if match:
            value = float(match.group(1))
            return value >= 5.0
        return False

    @staticmethod
    def _build_event_id(assessment: RiskAssessment) -> str:
        """Build a unique event identifier from assessment data."""
        timestamp = assessment.data.timestamp
        flare = assessment.data.xray_flare or ""
        return f"{timestamp}-{flare}"
