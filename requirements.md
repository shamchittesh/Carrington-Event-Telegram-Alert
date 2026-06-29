# Project Specification: CarringtonWatch Telegram Bot

## Overview

CarringtonWatch is a lightweight Python application that continuously monitors publicly available NOAA space weather data and sends Telegram alerts when conditions suggest an increased probability of a severe geomagnetic storm or a potential Carrington-class event.

The project is intentionally designed to be simple to deploy and maintain:

- No database
- No web dashboard
- No email notifications
- No Discord or webhook integrations
- No frontend
- No cloud dependencies
- All persistent state stored in JSON files committed or generated within the repository

The primary interface for the user is Telegram.

---

# Goals

The bot should:

- Poll NOAA data sources periodically.
- Combine multiple indicators into a single heuristic risk assessment.
- Notify the user through Telegram when predefined thresholds are crossed.
- Avoid duplicate notifications for the same event.
- Maintain lightweight historical state using JSON files.
- Generate concise, human-readable summaries suitable for mobile notifications.

The bot is intended as an informational monitoring tool and must not claim to predict solar storms with certainty.

---

# Technology Stack

- Python 3.13+
- requests
- python-telegram-bot (or direct Telegram Bot API usage)
- APScheduler or schedule
- Standard library JSON module
- Standard logging module

No database should be used.

No ORM should be used.

No web framework should be used.

---

# Repository Structure

```
carrington-watch/
│
├── main.py
├── collector.py
├── analyzer.py
├── notifier.py
├── scheduler.py
├── config.py
│
├── config/
│   └── settings.json
│
├── state/
│   ├── latest.json
│   ├── history.json
│   └── sent_alerts.json
│
├── logs/
│   └── bot.log
│
├── requirements.txt
├── README.md
└── .env
```

---

# Configuration

All configurable values should be centralized.

Example:

```
POLL_INTERVAL_MINUTES = 5

TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID

X_FLARE_THRESHOLD = "X1"

HIGH_SOLAR_WIND = 800

HIGH_NEGATIVE_BZ = -20

KP_WARNING = 7

KP_EXTREME = 8

ENABLE_DEBUG = false
```

---

# State Management

Use JSON files only.

## latest.json

Stores the most recent processed measurements.

Example:

```json
{
  "timestamp": "...",
  "kp": 6,
  "solar_wind": 640,
  "bz": -11,
  "flare": "M8.2"
}
```

---

## history.json

Append-only chronological history.

Example:

```json
[
  {
    "timestamp": "...",
    "risk": 18
  },
  {
    "timestamp": "...",
    "risk": 41
  }
]
```

Limit file size by retaining only the newest 10,000 records.

---

## sent_alerts.json

Tracks previously issued alerts to prevent duplicates.

Example:

```json
{
  "last_status": "WATCH",
  "last_event_id": "2026-07-21T12:10Z-X2.1"
}
```

---

# Polling Schedule

Run every 5 minutes.

Each execution should:

1. Download latest NOAA data.
2. Parse relevant metrics.
3. Compute risk score.
4. Compare against previous state.
5. Send Telegram notification if status changed.
6. Update JSON state files.

---

# NOAA Indicators

Monitor at minimum:

- GOES X-ray flare classification
- Solar wind speed
- Interplanetary magnetic field Bz
- Kp index
- NOAA-issued watches or warnings when available

The architecture should allow additional indicators to be added later without major refactoring.

---

# Risk Engine

Compute a heuristic score.

Example:

```
score = 0

X-class flare           +30
Major M-class flare     +15

Solar wind >800 km/s    +20
Solar wind >1000 km/s   +30

Bz < -10                +10
Bz < -20                +25

Kp >= 7                 +15
Kp >= 8                 +25
```

Clamp score to 0–100.

---

# Risk Levels

## NORMAL

Score: 0–29

Telegram message only on transition from another state.

Example:

```
🟢 Space Weather Status

Risk: NORMAL

Conditions remain quiet.
No immediate concern.
```

---

## WATCH

Score: 30–49

Example:

```
🟡 CarringtonWatch

Space weather activity is elevated.

Risk Score: 41/100

Drivers:
• Strong solar flare
• Elevated solar wind

Monitoring closely.
```

---

## WARNING

Score: 50–74

Example:

```
🟠 CarringtonWatch Warning

Several indicators are elevated.

Risk Score: 62/100

Strong geomagnetic activity may develop.
```

---

## EXTREME

Score: 75–100

Example:

```
🔴 CarringtonWatch Extreme Alert

Risk Score: 87/100

Multiple severe indicators are present.

This does NOT confirm a Carrington-class event but warrants close monitoring.
```

---

# Duplicate Suppression

Do not resend identical alerts.

Send a new alert only if:

- Risk level changes.
- Risk score changes by at least 15 points.
- A new major flare classification appears.
- NOAA publishes a materially different warning.

---

# Telegram Commands

## /start

Returns welcome message.

---

## /status

Returns current metrics.

Example:

```
CarringtonWatch Status

Risk: WATCH

Risk Score: 43

Flare: X1.2
Solar Wind: 780 km/s
Bz: -17 nT
Kp: 6

Last Updated:
2026-07-21 12:35 UTC
```

---

## /risk

Returns explanation of the current score and contributing factors.

---

## /history

Displays the last ten recorded risk snapshots.

---

## /ping

Returns:

```
Bot online.
```

---

## /help

Lists supported commands.

---

# Logging

Write structured logs to `logs/bot.log`.

Include:

- Poll start
- Poll completion
- Download failures
- Parsing errors
- Telegram send attempts
- Alert decisions
- Risk calculations

---

# Error Handling

The bot should never terminate because of a temporary network issue.

If a poll fails:

- Log the exception.
- Retry on the next scheduled cycle.
- Preserve previous state.

---

# Startup Behavior

On startup:

- Create missing JSON files with valid defaults.
- Validate configuration.
- Verify Telegram connectivity.
- Perform one immediate poll before entering the scheduled loop.

---

# README Requirements

Document:

- Project purpose
- Installation
- Environment variables
- Running locally
- Telegram setup
- JSON state files
- Scheduler behavior
- Limitations of heuristic risk scoring

---

# Future Extensibility

The codebase should make it straightforward to add:

- CME arrival-time estimation
- Historical trend analysis
- Additional NOAA indicators
- Machine-learning-based scoring
- Richer Telegram summaries
- Daily or weekly digest messages

These enhancements should not require replacing the JSON-based persistence layer.

---

# Non-Goals

This project must **not** include:

- SQL databases
- PostgreSQL
- MySQL
- SQLite
- Redis
- Web dashboards
- Streamlit
- Flask
- FastAPI
- Email notifications
- Discord integrations
- Webhooks
- Authentication systems
- User accounts
- Multi-user support

The design target is a single-user, low-maintenance Telegram bot that can run continuously on a small server or local machine with minimal operational overhead.