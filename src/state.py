"""State management for CarringtonWatch Bot.

Manages JSON state file read/write with atomic operations.
State files: latest.json, history.json, sent_alerts.json
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum number of history records to retain
HISTORY_MAX_RECORDS = 10_000


@dataclass
class SentAlertState:
    """Tracks the most recently sent alert state."""

    last_status: str | None
    last_score: int | None
    last_event_id: str | None


class StateManager:
    """Manages JSON state file read/write with atomic operations."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._latest_path = state_dir / "latest.json"
        self._history_path = state_dir / "history.json"
        self._sent_alerts_path = state_dir / "sent_alerts.json"

    def ensure_state_files(self) -> None:
        """Create missing state files with valid defaults."""
        self._state_dir.mkdir(parents=True, exist_ok=True)

        if not self._latest_path.exists():
            logger.info("Creating default state file: %s", self._latest_path)
            self._atomic_write(self._latest_path, None)

        if not self._history_path.exists():
            logger.info("Creating default state file: %s", self._history_path)
            self._atomic_write(self._history_path, [])

        if not self._sent_alerts_path.exists():
            logger.info("Creating default state file: %s", self._sent_alerts_path)
            default_alerts = SentAlertState(
                last_status=None, last_score=None, last_event_id=None
            )
            self._atomic_write(self._sent_alerts_path, asdict(default_alerts))

    # ── latest.json ──────────────────────────────────────────────────────

    def read_latest(self) -> dict | None:
        """Read the most recent measurements from latest.json.

        Returns None if the file contains null or is missing/corrupted.
        """
        return self._safe_read(self._latest_path, default=None)

    def write_latest(self, data: dict) -> None:
        """Write latest measurements to latest.json.

        Accepts a dict with keys: timestamp, kp_index, solar_wind_speed,
        bz_component, xray_flare. Maps them to the state file format:
        timestamp, kp, solar_wind, bz, flare.
        """
        state_data = {
            "timestamp": data.get("timestamp"),
            "kp": data.get("kp_index"),
            "solar_wind": data.get("solar_wind_speed"),
            "bz": data.get("bz_component"),
            "flare": data.get("xray_flare"),
        }
        self._atomic_write(self._latest_path, state_data)

    # ── history.json ─────────────────────────────────────────────────────

    def read_history(self) -> list[dict]:
        """Read risk history from history.json.

        Returns an empty list if the file is missing or corrupted.
        """
        result = self._safe_read(self._history_path, default=[])
        if not isinstance(result, list):
            logger.error(
                "history.json contained non-list data; resetting to empty list"
            )
            self._atomic_write(self._history_path, [])
            return []
        return result

    def append_history(self, entry: dict) -> None:
        """Append a risk entry to history.json, enforcing the 10,000 record cap.

        Removes oldest records when the limit is exceeded.
        """
        history = self.read_history()
        history.append(entry)

        # Trim oldest records if over the cap
        if len(history) > HISTORY_MAX_RECORDS:
            history = history[-HISTORY_MAX_RECORDS:]

        self._atomic_write(self._history_path, history)

    # ── sent_alerts.json ─────────────────────────────────────────────────

    def read_sent_alerts(self) -> SentAlertState:
        """Read sent alert state from sent_alerts.json.

        Returns a default SentAlertState if the file is missing or corrupted.
        """
        data = self._safe_read(
            self._sent_alerts_path,
            default={"last_status": None, "last_score": None, "last_event_id": None},
        )
        if not isinstance(data, dict):
            logger.error(
                "sent_alerts.json contained non-dict data; resetting to defaults"
            )
            default = SentAlertState(
                last_status=None, last_score=None, last_event_id=None
            )
            self._atomic_write(self._sent_alerts_path, asdict(default))
            return default

        return SentAlertState(
            last_status=data.get("last_status"),
            last_score=data.get("last_score"),
            last_event_id=data.get("last_event_id"),
        )

    def write_sent_alerts(self, state: SentAlertState) -> None:
        """Write sent alert state to sent_alerts.json."""
        self._atomic_write(self._sent_alerts_path, asdict(state))

    # ── Internal helpers ─────────────────────────────────────────────────

    def _atomic_write(self, path: Path, data: object) -> None:
        """Write data to a file atomically using a temp file and os.replace().

        Steps: write to .tmp → flush → fsync → os.replace()
        """
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except OSError as e:
            logger.error("Failed to write state file %s: %s", path, e)
            # Clean up temp file if it still exists
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _safe_read(self, path: Path, default: object) -> object:
        """Read and parse a JSON state file.

        If the file is missing or corrupted, logs the error, recreates the
        file with the provided default, and returns the default.
        """
        if not path.exists():
            logger.warning("State file missing: %s; creating with defaults", path)
            self._atomic_write(path, default)
            return default

        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Corrupted state file %s: %s; recreating with defaults", path, e
            )
            self._atomic_write(path, default)
            return default
