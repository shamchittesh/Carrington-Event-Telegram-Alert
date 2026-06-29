"""Poll orchestrator for CarringtonWatch Bot.

Coordinates the periodic poll-analyze-notify pipeline as a job callback
compatible with python-telegram-bot's Application.job_queue.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from src.analyzer import RiskAnalyzer
from src.collector import NOAACollector
from src.notifier import TelegramNotifier
from src.state import SentAlertState, StateManager

if TYPE_CHECKING:
    from telegram.ext import CallbackContext

logger = logging.getLogger(__name__)


class PollOrchestrator:
    """Coordinates the periodic poll-analyze-notify pipeline."""

    def __init__(
        self,
        collector: NOAACollector,
        analyzer: RiskAnalyzer,
        notifier: TelegramNotifier,
        state_manager: StateManager,
    ) -> None:
        self._collector = collector
        self._analyzer = analyzer
        self._notifier = notifier
        self._state_manager = state_manager

    async def execute_poll_cycle(self, context: CallbackContext) -> None:
        """Single poll cycle: collect → analyze → decide → notify → persist.

        This method is designed to be used as a job callback with
        python-telegram-bot's JobQueue. All exceptions are caught internally
        to prevent the scheduler from crashing.
        """
        try:
            logger.info("Poll cycle started")

            # 1. Run collector in executor (sync requests calls)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._collector.collect)

            # 2. Compute risk assessment
            assessment = self._analyzer.assess(data)

            # 3. Check if alert should be sent
            previous_state = self._state_manager.read_sent_alerts()
            should_send = self._analyzer.should_alert(assessment, previous_state)

            # 4. Send alert or log suppression
            if should_send:
                sent = await self._notifier.send_alert(assessment)
                if sent:
                    logger.info(
                        "Alert sent: level=%s, score=%d",
                        assessment.level.value,
                        assessment.score,
                    )
                    # Update sent_alerts state only on successful send
                    new_alert_state = SentAlertState(
                        last_status=assessment.level.value,
                        last_score=assessment.score,
                        last_event_id=self._build_event_id(assessment),
                    )
                    self._state_manager.write_sent_alerts(new_alert_state)
                else:
                    logger.error(
                        "Failed to send alert; will retry next cycle"
                    )
            else:
                logger.info(
                    "Alert suppressed: no meaningful change from previous alert"
                )

            # 5. Update state files (latest.json, history.json)
            self._state_manager.write_latest(asdict(data))
            history_entry = {
                "timestamp": data.timestamp,
                "risk": assessment.score,
            }
            self._state_manager.append_history(history_entry)

            # 6. Log poll cycle completion
            logger.info(
                "Poll cycle completed: risk_score=%d, level=%s",
                assessment.score,
                assessment.level.value,
            )

        except Exception:
            # Never let exceptions escape to crash the scheduler
            logger.exception("Error during poll cycle; will retry next cycle")

    @staticmethod
    def _build_event_id(assessment) -> str:
        """Build a unique event identifier from assessment data."""
        timestamp = assessment.data.timestamp
        flare = assessment.data.xray_flare or ""
        return f"{timestamp}-{flare}"
