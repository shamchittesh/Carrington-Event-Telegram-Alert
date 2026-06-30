#!/usr/bin/env python3
"""
CarringtonWatch Serverless Bot

Designed for serverless execution (GitHub Actions cron).
Runs one data collection → analysis → notification cycle and exits.
Stores minimal state as JSON in repository.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from src.analyzer import RiskAnalyzer
from src.collector import NOAACollector
from src.config import load_config, validate_config
from src.notifier import TelegramNotifier
from src.state import SentAlertState
from telegram.ext import Application


# Minimal state file for serverless execution
STATE_FILE = Path("bot_state.json")


def load_minimal_state() -> Optional[SentAlertState]:
    """Load minimal state needed for alert suppression."""
    if not STATE_FILE.exists():
        return None
    
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
            return SentAlertState(
                last_status=data.get("last_status"),
                last_score=data.get("last_score"), 
                last_event_id=data.get("last_event_id")
            )
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None


def save_minimal_state(alert_state: SentAlertState) -> None:
    """Save minimal state for next run."""
    data = {
        "last_status": alert_state.last_status,
        "last_score": alert_state.last_score,
        "last_event_id": alert_state.last_event_id,
        "updated_at": "auto-updated by GitHub Actions"
    }
    
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def setup_logging(enable_debug: bool) -> None:
    """Configure logging for serverless execution."""
    log_level = logging.DEBUG if enable_debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def run_single_poll_cycle() -> None:
    """Run a single poll cycle: collect → analyze → notify → exit."""
    logger = logging.getLogger(__name__)

    try:
        logger.info("🛰️ CarringtonWatch: Starting serverless poll cycle")

        # ── 1. Load and validate configuration ───────────────────────────
        config = load_config()
        errors = validate_config(config)
        if errors:
            for error in errors:
                logger.error("Configuration error: %s", error)
            logger.error("Cannot start due to configuration errors")
            sys.exit(1)

        # ── 2. Configure logging ─────────────────────────────────────────
        setup_logging(config.enable_debug)

        # ── 3. Initialize components ─────────────────────────────────────
        collector = NOAACollector()
        analyzer = RiskAnalyzer(config)

        # ── 4. Setup Telegram bot ───────────────────────────────────────
        application = Application.builder().token(config.telegram_bot_token).build()
        notifier = TelegramNotifier(
            bot=application.bot, 
            chat_id=config.telegram_chat_id
        )

        # ── 5. Execute single poll cycle ────────────────────────────────
        async with application:
            logger.info("Collecting NOAA space weather data")
            data = collector.collect()

            logger.info("Computing risk assessment")
            assessment = analyzer.assess(data)

            logger.info(
                "Risk computed: level=%s, score=%d", 
                assessment.level.value, 
                assessment.score
            )

            # Load previous alert state for suppression logic
            previous_state = load_minimal_state()
            if previous_state is None:
                logger.info("No previous state found - first run")
                previous_state = SentAlertState(None, None, None)

            # Check if alert should be sent
            should_send = analyzer.should_alert(assessment, previous_state)

            if should_send:
                logger.info("Sending alert notification")
                sent = await notifier.send_alert(assessment)
                if sent:
                    logger.info("✅ Alert sent successfully")
                    # Save new alert state
                    new_alert_state = SentAlertState(
                        last_status=assessment.level.value,
                        last_score=assessment.score,
                        last_event_id=f"{assessment.data.timestamp}-{assessment.data.xray_flare or ''}",
                    )
                    save_minimal_state(new_alert_state)
                    logger.info("State updated for next run")
                else:
                    logger.error("❌ Failed to send alert")
                    sys.exit(1)
            else:
                logger.info("🔇 Alert suppressed: no meaningful change detected")

            logger.info(
                "✅ CarringtonWatch serverless cycle completed: risk_score=%d, level=%s",
                assessment.score,
                assessment.level.value,
            )

    except Exception as e:
        logger.exception("❌ Error during poll cycle: %s", e)
        sys.exit(1)


def main() -> None:
    """Entry point for serverless execution."""
    try:
        asyncio.run(run_single_poll_cycle())
    except KeyboardInterrupt:
        print("\n🛑 CarringtonWatch cycle interrupted")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()