"""Unit tests for StateManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.state import HISTORY_MAX_RECORDS, SentAlertState, StateManager


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Provide a temporary state directory."""
    return tmp_path / "state"


@pytest.fixture
def manager(state_dir: Path) -> StateManager:
    """Provide a StateManager with a fresh temp directory."""
    mgr = StateManager(state_dir)
    mgr.ensure_state_files()
    return mgr


class TestEnsureStateFiles:
    """Tests for ensure_state_files()."""

    def test_creates_directory_and_files(self, state_dir: Path) -> None:
        mgr = StateManager(state_dir)
        mgr.ensure_state_files()

        assert state_dir.exists()
        assert (state_dir / "latest.json").exists()
        assert (state_dir / "history.json").exists()
        assert (state_dir / "sent_alerts.json").exists()

    def test_default_latest_is_null(self, state_dir: Path) -> None:
        mgr = StateManager(state_dir)
        mgr.ensure_state_files()

        with open(state_dir / "latest.json") as f:
            assert json.load(f) is None

    def test_default_history_is_empty_list(self, state_dir: Path) -> None:
        mgr = StateManager(state_dir)
        mgr.ensure_state_files()

        with open(state_dir / "history.json") as f:
            assert json.load(f) == []

    def test_default_sent_alerts_has_null_fields(self, state_dir: Path) -> None:
        mgr = StateManager(state_dir)
        mgr.ensure_state_files()

        with open(state_dir / "sent_alerts.json") as f:
            data = json.load(f)
        assert data == {
            "last_status": None,
            "last_score": None,
            "last_event_id": None,
        }

    def test_does_not_overwrite_existing_files(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        latest_path = state_dir / "latest.json"
        latest_path.write_text(json.dumps({"timestamp": "test"}))

        mgr = StateManager(state_dir)
        mgr.ensure_state_files()

        with open(latest_path) as f:
            assert json.load(f) == {"timestamp": "test"}


class TestLatest:
    """Tests for read_latest() / write_latest()."""

    def test_read_latest_returns_none_initially(self, manager: StateManager) -> None:
        assert manager.read_latest() is None

    def test_write_and_read_latest(self, manager: StateManager) -> None:
        data = {
            "timestamp": "2026-07-21T12:35:00Z",
            "kp_index": 6.0,
            "solar_wind_speed": 780.0,
            "bz_component": -17.0,
            "xray_flare": "X1.2",
        }
        manager.write_latest(data)
        result = manager.read_latest()

        assert result == {
            "timestamp": "2026-07-21T12:35:00Z",
            "kp": 6.0,
            "solar_wind": 780.0,
            "bz": -17.0,
            "flare": "X1.2",
        }

    def test_write_latest_with_none_values(self, manager: StateManager) -> None:
        data = {
            "timestamp": "2026-07-21T12:35:00Z",
            "kp_index": None,
            "solar_wind_speed": None,
            "bz_component": None,
            "xray_flare": None,
        }
        manager.write_latest(data)
        result = manager.read_latest()

        assert result["timestamp"] == "2026-07-21T12:35:00Z"
        assert result["kp"] is None
        assert result["solar_wind"] is None
        assert result["bz"] is None
        assert result["flare"] is None


class TestHistory:
    """Tests for read_history() / append_history()."""

    def test_read_history_returns_empty_initially(
        self, manager: StateManager
    ) -> None:
        assert manager.read_history() == []

    def test_append_and_read_history(self, manager: StateManager) -> None:
        entry = {"timestamp": "2026-07-21T12:35:00Z", "risk": 62}
        manager.append_history(entry)

        history = manager.read_history()
        assert len(history) == 1
        assert history[0] == entry

    def test_append_preserves_order(self, manager: StateManager) -> None:
        for i in range(5):
            manager.append_history({"timestamp": f"t{i}", "risk": i * 10})

        history = manager.read_history()
        assert len(history) == 5
        assert history[0]["risk"] == 0
        assert history[4]["risk"] == 40

    def test_history_cap_removes_oldest(self, manager: StateManager, state_dir: Path) -> None:
        # Write a history with exactly HISTORY_MAX_RECORDS entries
        history = [{"timestamp": f"t{i}", "risk": i} for i in range(HISTORY_MAX_RECORDS)]
        with open(state_dir / "history.json", "w") as f:
            json.dump(history, f)

        # Append one more
        manager.append_history({"timestamp": "new", "risk": 999})

        result = manager.read_history()
        assert len(result) == HISTORY_MAX_RECORDS
        # Oldest (t0) should be gone, newest should be last
        assert result[0]["timestamp"] == "t1"
        assert result[-1] == {"timestamp": "new", "risk": 999}


class TestSentAlerts:
    """Tests for read_sent_alerts() / write_sent_alerts()."""

    def test_read_sent_alerts_returns_defaults_initially(
        self, manager: StateManager
    ) -> None:
        state = manager.read_sent_alerts()
        assert state.last_status is None
        assert state.last_score is None
        assert state.last_event_id is None

    def test_write_and_read_sent_alerts(self, manager: StateManager) -> None:
        state = SentAlertState(
            last_status="WARNING",
            last_score=62,
            last_event_id="2026-07-21T12:35Z-X1.2",
        )
        manager.write_sent_alerts(state)

        result = manager.read_sent_alerts()
        assert result.last_status == "WARNING"
        assert result.last_score == 62
        assert result.last_event_id == "2026-07-21T12:35Z-X1.2"


class TestCorruptedFiles:
    """Tests for corrupted state file recovery."""

    def test_corrupted_latest_returns_default(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "latest.json").write_text("not valid json{{{")

        mgr = StateManager(state_dir)
        result = mgr.read_latest()

        assert result is None
        # File should be recreated with default
        with open(state_dir / "latest.json") as f:
            assert json.load(f) is None

    def test_corrupted_history_returns_empty_list(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "history.json").write_text("{corrupted")

        mgr = StateManager(state_dir)
        result = mgr.read_history()

        assert result == []

    def test_corrupted_sent_alerts_returns_defaults(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "sent_alerts.json").write_text("???invalid")

        mgr = StateManager(state_dir)
        result = mgr.read_sent_alerts()

        assert result.last_status is None
        assert result.last_score is None
        assert result.last_event_id is None

    def test_history_with_non_list_data_resets(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "history.json").write_text(json.dumps({"not": "a list"}))

        mgr = StateManager(state_dir)
        result = mgr.read_history()

        assert result == []

    def test_sent_alerts_with_non_dict_data_resets(self, state_dir: Path) -> None:
        state_dir.mkdir(parents=True)
        (state_dir / "sent_alerts.json").write_text(json.dumps([1, 2, 3]))

        mgr = StateManager(state_dir)
        result = mgr.read_sent_alerts()

        assert result.last_status is None


class TestAtomicWrites:
    """Tests for atomic write behavior."""

    def test_no_tmp_file_remains_after_write(self, manager: StateManager, state_dir: Path) -> None:
        manager.write_latest(
            {
                "timestamp": "t",
                "kp_index": 1.0,
                "solar_wind_speed": 400.0,
                "bz_component": -5.0,
                "xray_flare": "C1.0",
            }
        )

        tmp_files = list(state_dir.glob("*.tmp"))
        assert tmp_files == []
