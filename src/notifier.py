"""Telegram notification and command handling for CarringtonWatch Bot.

Formats alert messages based on risk level, sends notifications via the
Telegram Bot API, and provides interactive command handlers for on-demand
status queries.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.analyzer import RiskAssessment, RiskLevel

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

    from src.state import StateManager

logger = logging.getLogger(__name__)

# ── Emoji mapping by risk level ──────────────────────────────────────────────
LEVEL_EMOJI = {
    RiskLevel.NORMAL: "🟢",
    RiskLevel.WATCH: "🟡",
    RiskLevel.WARNING: "🟠",
    RiskLevel.EXTREME: "🔴",
}

# ── Header text by risk level ────────────────────────────────────────────────
LEVEL_HEADER = {
    RiskLevel.NORMAL: "Space Weather Status: NORMAL",
    RiskLevel.WATCH: "CarringtonWatch: WATCH",
    RiskLevel.WARNING: "CarringtonWatch Warning",
    RiskLevel.EXTREME: "CarringtonWatch Extreme Alert",
}

CARRINGTON_DISCLAIMER = (
    "⚠️ DISCLAIMER: This alert is based on heuristic analysis of publicly "
    "available data. It does NOT confirm a Carrington-class event. Please refer "
    "to official NOAA/SWPC advisories for authoritative guidance."
)


class TelegramNotifier:
    """Formats and sends Telegram messages."""

    def __init__(self, bot: Bot, chat_id: str) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def send_alert(self, assessment: RiskAssessment) -> bool:
        """Format and send an alert message based on risk level.

        Returns True on success, False on Telegram API failure.
        """
        message = self._format_alert(assessment)
        return await self._send_message(message)

    async def send_status(self, assessment: RiskAssessment) -> str:
        """Format a status response showing current measurements.

        Returns the formatted message string.
        """
        return self._format_status(assessment)

    async def send_risk_explanation(self, assessment: RiskAssessment) -> str:
        """Format a risk breakdown showing contributing factors.

        Returns the formatted message string.
        """
        return self._format_risk_explanation(assessment)

    async def send_history(self, history: list[dict]) -> str:
        """Format the last 10 risk snapshots for display.

        Returns the formatted message string.
        """
        return self._format_history(history)

    # ── Message formatting ───────────────────────────────────────────────

    def _format_alert(self, assessment: RiskAssessment) -> str:
        """Build the full alert message for a given risk assessment."""
        emoji = LEVEL_EMOJI[assessment.level]
        header = LEVEL_HEADER[assessment.level]
        data = assessment.data

        lines: list[str] = []
        lines.append(f"{emoji} {header}")
        lines.append("")
        lines.append(f"Risk Score: {assessment.score}/100")

        # Add current measurements section
        lines.append("")
        lines.append("📊 Current Measurements:")
        lines.append(f"  🌞 X-Ray Flare: {data.xray_flare or 'None detected'}")
        lines.append(
            f"  💨 Solar Wind: "
            f"{f'{data.solar_wind_speed:.0f} km/s' if data.solar_wind_speed is not None else 'N/A'}"
        )
        lines.append(
            f"  🧲 Bz Component: "
            f"{f'{data.bz_component:.1f} nT' if data.bz_component is not None else 'N/A'}"
        )
        lines.append(
            f"  📈 Kp Index: "
            f"{f'{data.kp_index:.1f}' if data.kp_index is not None else 'N/A'}"
        )

        # Include contributing factors at WATCH level and higher
        if assessment.level in (RiskLevel.WATCH, RiskLevel.WARNING, RiskLevel.EXTREME):
            lines.append("")
            lines.append("⚠️ Contributing Factors:")
            for factor in assessment.contributing_factors:
                lines.append(f"  • {factor}")

        # Include Carrington disclaimer at EXTREME level
        if assessment.level == RiskLevel.EXTREME:
            lines.append("")
            lines.append(CARRINGTON_DISCLAIMER)

        # Add timestamp
        lines.append("")
        lines.append(f"🕐 Data Time: {data.timestamp}")

        return "\n".join(lines)

    def _format_status(self, assessment: RiskAssessment) -> str:
        """Build the status message showing current measurements."""
        emoji = LEVEL_EMOJI[assessment.level]
        data = assessment.data

        lines: list[str] = []
        lines.append(f"{emoji} Current Space Weather Status")
        lines.append("")
        lines.append(f"Risk Level: {assessment.level.value}")
        lines.append(f"Risk Score: {assessment.score}/100")
        lines.append("")
        lines.append("Measurements:")
        lines.append(f"  X-Ray Flare: {data.xray_flare or 'None detected'}")
        lines.append(
            f"  Solar Wind Speed: "
            f"{f'{data.solar_wind_speed:.0f} km/s' if data.solar_wind_speed is not None else 'N/A'}"
        )
        lines.append(
            f"  Bz Component: "
            f"{f'{data.bz_component:.1f} nT' if data.bz_component is not None else 'N/A'}"
        )
        lines.append(
            f"  Kp Index: "
            f"{f'{data.kp_index:.1f}' if data.kp_index is not None else 'N/A'}"
        )
        lines.append("")
        lines.append(f"Last Update: {data.timestamp}")

        return "\n".join(lines)

    def _format_risk_explanation(self, assessment: RiskAssessment) -> str:
        """Build the risk explanation message with factor breakdown."""
        emoji = LEVEL_EMOJI[assessment.level]

        lines: list[str] = []
        lines.append(f"{emoji} Risk Assessment Breakdown")
        lines.append("")
        lines.append(f"Current Level: {assessment.level.value}")
        lines.append(f"Risk Score: {assessment.score}/100")
        lines.append("")

        if assessment.contributing_factors:
            lines.append("Contributing Factors:")
            for factor in assessment.contributing_factors:
                lines.append(f"  • {factor}")
        else:
            lines.append("No significant risk factors detected.")

        lines.append("")
        lines.append("Score Ranges:")
        lines.append("  🟢 NORMAL: 0-29")
        lines.append("  🟡 WATCH: 30-49")
        lines.append("  🟠 WARNING: 50-74")
        lines.append("  🔴 EXTREME: 75-100")

        return "\n".join(lines)

    def _format_history(self, history: list[dict]) -> str:
        """Build the history message from the last 10 snapshots."""
        lines: list[str] = []
        lines.append("📊 Risk History (last 10 snapshots)")
        lines.append("")

        if not history:
            lines.append("No history available yet.")
            return "\n".join(lines)

        # Take only the last 10 entries
        recent = history[-10:]

        for entry in recent:
            timestamp = entry.get("timestamp", "Unknown")
            risk = entry.get("risk", "?")
            lines.append(f"  {timestamp} — Risk: {risk}")

        return "\n".join(lines)

    # ── Telegram send helper ─────────────────────────────────────────────

    async def _send_message(self, text: str) -> bool:
        """Send a message via the Telegram Bot API.

        Returns True on success. Logs and returns False on failure.
        """
        try:
            await self._bot.send_message(chat_id=self._chat_id, text=text)
            return True
        except TelegramError as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False


def register_commands(
    application: Application,
    notifier: TelegramNotifier,
    state_manager: "StateManager",
    analyzer: object,
) -> None:
    """Register all Telegram command handlers on the application.

    Args:
        application: The python-telegram-bot Application instance.
        notifier: TelegramNotifier instance for formatting messages.
        state_manager: StateManager for reading state files.
        analyzer: RiskAnalyzer instance for computing assessments on demand.
    """
    from src.analyzer import RiskAnalyzer
    from src.collector import SpaceWeatherData

    async def _cmd_start(update: Update, context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /start command."""
        welcome = (
            "👋 Welcome to CarringtonWatch!\n\n"
            "I monitor NOAA space weather data and alert you when geomagnetic "
            "storm risk increases.\n\n"
            "Commands:\n"
            "  /status — Current space weather status\n"
            "  /risk — Risk score breakdown\n"
            "  /history — Last 10 risk snapshots\n"
            "  /ping — Check if bot is online\n"
            "  /help — Show this help message"
        )
        if update.effective_message:
            await update.effective_message.reply_text(welcome)

    async def _cmd_status(update: Update, context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /status command."""
        if not update.effective_message:
            return

        assessment = _build_current_assessment(state_manager, analyzer)
        if assessment is None:
            await update.effective_message.reply_text(
                "No data available yet. The bot is still collecting initial measurements."
            )
            return

        message = await notifier.send_status(assessment)
        await update.effective_message.reply_text(message)

    async def _cmd_risk(update: Update, context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /risk command."""
        if not update.effective_message:
            return

        assessment = _build_current_assessment(state_manager, analyzer)
        if assessment is None:
            await update.effective_message.reply_text(
                "No data available yet. The bot is still collecting initial measurements."
            )
            return

        message = await notifier.send_risk_explanation(assessment)
        await update.effective_message.reply_text(message)

    async def _cmd_history(
        update: Update, context: "ContextTypes.DEFAULT_TYPE"
    ) -> None:
        """Handle /history command."""
        if not update.effective_message:
            return

        history = state_manager.read_history()
        message = await notifier.send_history(history)
        await update.effective_message.reply_text(message)

    async def _cmd_ping(update: Update, context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /ping command."""
        if update.effective_message:
            await update.effective_message.reply_text("Bot online")

    async def _cmd_help(update: Update, context: "ContextTypes.DEFAULT_TYPE") -> None:
        """Handle /help command."""
        help_text = (
            "CarringtonWatch Bot Commands:\n\n"
            "  /start — Welcome message and introduction\n"
            "  /status — Current space weather status and measurements\n"
            "  /risk — Detailed risk score breakdown\n"
            "  /history — Last 10 risk assessment snapshots\n"
            "  /ping — Check if bot is online\n"
            "  /help — Show this help message"
        )
        if update.effective_message:
            await update.effective_message.reply_text(help_text)

    async def _handle_unknown(
        update: Update, context: "ContextTypes.DEFAULT_TYPE"
    ) -> None:
        """Handle unrecognized commands."""
        if update.effective_message:
            await update.effective_message.reply_text(
                "Unknown command. Use /help to see available commands."
            )

    def _build_current_assessment(
        sm: "StateManager", anlzr: object
    ) -> RiskAssessment | None:
        """Build a RiskAssessment from the current latest state."""
        latest = sm.read_latest()
        if latest is None:
            return None

        # Reconstruct SpaceWeatherData from stored state
        data = SpaceWeatherData(
            timestamp=latest.get("timestamp", ""),
            kp_index=latest.get("kp"),
            solar_wind_speed=latest.get("solar_wind"),
            bz_component=latest.get("bz"),
            xray_flare=latest.get("flare"),
        )

        if isinstance(anlzr, RiskAnalyzer):
            return anlzr.assess(data)

        return None

    # Register command handlers
    application.add_handler(CommandHandler("start", _cmd_start))
    application.add_handler(CommandHandler("status", _cmd_status))
    application.add_handler(CommandHandler("risk", _cmd_risk))
    application.add_handler(CommandHandler("history", _cmd_history))
    application.add_handler(CommandHandler("ping", _cmd_ping))
    application.add_handler(CommandHandler("help", _cmd_help))

    # Handle unrecognized commands (must be added last)
    application.add_handler(
        MessageHandler(filters.COMMAND, _handle_unknown)
    )
