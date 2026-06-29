"""CarringtonWatch Bot — Application entry point.

Wires all components together, verifies connectivity, and starts the
scheduled polling loop via python-telegram-bot's Application event loop.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from telegram.error import TelegramError
from telegram.ext import Application

from src.analyzer import RiskAnalyzer
from src.collector import NOAACollector
from src.config import load_config, validate_config
from src.notifier import TelegramNotifier, register_commands
from src.scheduler import PollOrchestrator
from src.state import StateManager

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent
STATE_DIR = PROJECT_ROOT / "state"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "bot.log"


def setup_logging(enable_debug: bool) -> None:
    """Configure logging to file and console with structured format."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if enable_debug else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def verify_telegram_connectivity(application: Application, chat_id: str) -> bool:
    """Send a test message to verify Telegram API connectivity.

    Returns True on success, False on failure.
    """
    logger = logging.getLogger(__name__)
    try:
        await application.bot.send_message(
            chat_id=chat_id,
            text="🛰️ CarringtonWatch Bot starting up — connectivity verified.",
        )
        logger.info("Telegram connectivity verified")
        return True
    except TelegramError as e:
        logger.error("Telegram connectivity test failed: %s", e)
        return False


async def run_bot() -> None:
    """Main async entry point: initialize and run the bot."""
    logger = logging.getLogger(__name__)

    # ── 1. Load and validate configuration ───────────────────────────────
    config = load_config()
    errors = validate_config(config)
    if errors:
        # Set up minimal logging so the error is visible
        setup_logging(config.enable_debug)
        for error in errors:
            logger.error("Configuration error: %s", error)
        logger.error("Bot cannot start due to configuration errors. Exiting.")
        sys.exit(1)

    # ── 2. Configure logging ─────────────────────────────────────────────
    setup_logging(config.enable_debug)

    # ── 3. Initialize state manager ──────────────────────────────────────
    state_manager = StateManager(STATE_DIR)
    state_manager.ensure_state_files()
    logger.info("State files initialized in %s", STATE_DIR)

    # ── 4. Build python-telegram-bot Application ─────────────────────────
    application = Application.builder().token(config.telegram_bot_token).build()

    # ── 5. Create components ─────────────────────────────────────────────
    collector = NOAACollector()
    analyzer = RiskAnalyzer(config)
    notifier = TelegramNotifier(bot=application.bot, chat_id=config.telegram_chat_id)
    orchestrator = PollOrchestrator(
        collector=collector,
        analyzer=analyzer,
        notifier=notifier,
        state_manager=state_manager,
    )

    # ── 6. Verify Telegram connectivity ──────────────────────────────────
    async with application:
        connected = await verify_telegram_connectivity(
            application, config.telegram_chat_id
        )
        if not connected:
            logger.error(
                "Failed to connect to Telegram. Check TELEGRAM_BOT_TOKEN and "
                "TELEGRAM_CHAT_ID. Exiting."
            )
            sys.exit(1)

        # ── 7. Register command handlers ─────────────────────────────────
        register_commands(application, notifier, state_manager, analyzer)
        logger.info("Command handlers registered")

        # ── 8. Schedule periodic poll ────────────────────────────────────
        interval_seconds = config.poll_interval_minutes * 60
        application.job_queue.run_repeating(
            orchestrator.execute_poll_cycle,
            interval=interval_seconds,
            first=interval_seconds,
            name="poll_cycle",
        )
        logger.info(
            "Scheduled polling every %d minutes", config.poll_interval_minutes
        )

        # ── 9. Run one immediate poll cycle ──────────────────────────────
        logger.info("Running initial poll cycle")
        await orchestrator.execute_poll_cycle(context=None)

        # ── 10. Log success and start event loop ─────────────────────────
        logger.info("Bot initialized successfully")

        await application.start()
        await application.updater.start_polling()

        # Keep running until interrupted
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            await application.updater.stop()
            await application.stop()


def main() -> None:
    """Synchronous entry point."""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
