# CarringtonWatch 🛰️

A Python Telegram bot that monitors NOAA space weather data and sends alerts when conditions suggest an increased probability of a severe geomagnetic storm or a potential Carrington-class event.

## Features

- Continuous monitoring of NOAA Space Weather Prediction Center data feeds
- Heuristic risk scoring from multiple solar weather indicators (0–100)
- Automatic Telegram alerts when risk conditions change
- On-demand status queries via Telegram commands
- JSON file-based state persistence — no database required
- Configurable thresholds and polling intervals

---

## Installation

### Prerequisites

- Python 3.13 or higher
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A Telegram chat ID to receive alerts

### Steps

```bash
# Clone the repository
git clone https://github.com/your-username/Carrington-Event-Telegram-Alert.git
cd Carrington-Event-Telegram-Alert

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

CarringtonWatch uses a two-layer configuration system: environment variables (`.env`) for secrets and runtime settings, and `config/settings.json` for scoring thresholds.

### Environment Variables (`.env`)

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | — | Target chat ID for alerts |
| `POLL_INTERVAL_MINUTES` | No | `15` | Minutes between NOAA data polls |
| `ENABLE_DEBUG` | No | `false` | Enable verbose debug logging |

### Threshold Configuration (`config/settings.json`)

Scoring thresholds can be tuned without code changes:

```json
{
  "x_flare_threshold": "X1",
  "high_solar_wind": 800,
  "extreme_solar_wind": 1000,
  "high_negative_bz": -10,
  "extreme_negative_bz": -20,
  "kp_warning": 7,
  "kp_extreme": 8,
  "poll_interval_minutes": 15,
  "enable_debug": false
}
```

Environment variables take precedence over values in `settings.json`.

---

## Usage

### Running the Bot

```bash
python main.py
```

On startup the bot will:
1. Validate configuration
2. Initialize state files (if missing)
3. Verify Telegram connectivity by sending a test message
4. Run an initial data poll
5. Begin scheduled polling at the configured interval

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and bot introduction |
| `/status` | Current risk level, score, and all indicator readings |
| `/risk` | Detailed explanation of the current risk score and contributing factors |
| `/history` | Last 10 recorded risk snapshots with timestamps |
| `/ping` | Responds with "Bot online" — quick connectivity check |
| `/help` | List of all supported commands |

---

## Risk Scoring Methodology

The bot computes a heuristic risk score (0–100) by summing points from multiple space weather indicators. Higher-tier thresholds supersede lower-tier thresholds for the same indicator (they do not stack).

### Scoring Rules

| Condition | Points | Notes |
|-----------|--------|-------|
| X-class flare detected | +30 | Any X1.0 or higher |
| M5+ flare detected | +15 | M5.0 through M9.9 |
| Solar wind > 1000 km/s | +30 | Supersedes the 800 km/s rule |
| Solar wind > 800 km/s | +20 | Only applies if ≤ 1000 km/s |
| Bz < −20 nT | +25 | Supersedes the −10 nT rule |
| Bz < −10 nT | +10 | Only applies if ≥ −20 nT |
| Kp ≥ 8 | +25 | Supersedes the Kp 7 rule |
| Kp ≥ 7 | +15 | Only applies if Kp < 8 |

The final score is clamped to the range [0, 100].

### Risk Level Classification

| Level | Score Range | Indicator |
|-------|-------------|-----------|
| 🟢 NORMAL | 0–29 | No significant activity |
| 🟡 WATCH | 30–49 | Elevated indicators, monitoring advised |
| 🟠 WARNING | 50–74 | Significant activity detected |
| 🔴 EXTREME | 75–100 | Severe conditions — potential Carrington-class event |

### Alert Triggers

An alert is sent when any of these conditions are met:
- Risk level changes (e.g., NORMAL → WATCH)
- Risk score changes by ≥ 15 points since the last alert
- A new X-class flare (X1+) appears that wasn't in the previous alert

Duplicate alerts with identical content are suppressed.

---

## Data Sources

All data is fetched from [NOAA Space Weather Prediction Center](https://www.swpc.noaa.gov/) public APIs:

| Indicator | Endpoint |
|-----------|----------|
| Solar wind speed | `services.swpc.noaa.gov/products/summary/solar-wind-speed.json` |
| Magnetic field (Bz) | `services.swpc.noaa.gov/products/summary/solar-wind-mag-field.json` |
| Kp index | `services.swpc.noaa.gov/products/noaa-planetary-k-index.json` |
| X-ray flares | `services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json` |

---

## Project Structure

```
├── main.py                  # Application entry point
├── src/
│   ├── config.py            # Configuration loading and validation
│   ├── collector.py         # NOAA data fetching and parsing
│   ├── analyzer.py          # Risk scoring engine
│   ├── notifier.py          # Telegram message formatting and sending
│   ├── scheduler.py         # Poll cycle orchestration
│   └── state.py             # JSON state file management
├── config/
│   └── settings.json        # Threshold configuration
├── state/                   # Runtime state files (auto-created)
│   ├── latest.json          # Most recent measurements
│   ├── history.json         # Risk score history (max 10,000 entries)
│   └── sent_alerts.json     # Last sent alert tracking
├── logs/
│   └── bot.log              # Application logs
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
└── README.md
```

---

## Deployment Considerations

### Running as a Service

For persistent deployment, run the bot as a systemd service or in a container:

**systemd example** (`/etc/systemd/system/carringtonwatch.service`):

```ini
[Unit]
Description=CarringtonWatch Telegram Bot
After=network.target

[Service]
Type=simple
User=carringtonwatch
WorkingDirectory=/opt/carringtonwatch
ExecStart=/opt/carringtonwatch/.venv/bin/python main.py
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

**Docker** (minimal example):

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Resource Usage

- Memory: ~50 MB typical
- CPU: Negligible (one HTTP poll cycle every 15 minutes)
- Disk: State files remain small (history capped at 10,000 entries)
- Network: Periodic outbound HTTPS to NOAA and Telegram APIs

### Security Notes

- Store `TELEGRAM_BOT_TOKEN` securely — never commit `.env` to version control
- The `.env` file is listed in `.gitignore`
- The bot makes outbound HTTPS connections only; no inbound ports required
- NOAA endpoints are public and do not require authentication

### Reliability

- The bot is designed to never crash on transient failures
- Network errors during data collection are logged and retried on the next cycle
- Telegram send failures are logged; the alert is retried on the next cycle
- Corrupted state files are automatically recreated with valid defaults
- Atomic file writes (temp file + rename) prevent state corruption

---

## Development

### Running Tests

```bash
# Install dev dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run the test suite
pytest

# Run with verbose output
pytest -v

# Run property-based tests with more examples
pytest --hypothesis-seed=0
```

### Dependencies

**Runtime:**
- `python-telegram-bot>=21.0` — Telegram bot framework (async)
- `requests>=2.31.0` — HTTP client for NOAA data
- `python-dotenv>=1.0.0` — Environment variable loading

**Development:**
- `hypothesis>=6.100.0` — Property-based testing
- `pytest>=8.0.0` — Test framework
- `pytest-asyncio>=0.23.0` — Async test support
- `pytest-mock>=3.12.0` — Mocking utilities

---

## License

This project is for personal/educational use. Space weather data is provided by NOAA and is in the public domain.

> **Disclaimer:** CarringtonWatch provides heuristic risk estimates based on publicly available data. It is not a substitute for official NOAA space weather alerts or professional guidance. An EXTREME risk level does not confirm a Carrington-class event is occurring.
