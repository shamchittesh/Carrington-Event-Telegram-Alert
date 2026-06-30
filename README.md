# CarringtonWatch 🛰️

A Python Telegram bot that monitors NOAA space weather data and sends alerts when conditions suggest an increased probability of a severe geomagnetic storm or a potential Carrington-class event.

## Features

- Serverless monitoring of NOAA Space Weather Prediction Center data feeds via GitHub Actions
- Heuristic risk scoring from multiple solar weather indicators (0–100)
- Automatic Telegram alerts when risk conditions change
- On-demand status queries via Telegram commands
- JSON file-based state persistence — no database required
- Configurable thresholds and polling intervals

---

## Installation

### 🚀 Serverless Deployment (Recommended)

**No installation required!** CarringtonWatch runs entirely on GitHub Actions.

**Quick Start:**
1. **[Fork this repository](https://github.com/shamchittesh/Carrington-Event-Telegram-Alert/fork)** to your GitHub account
2. **Follow the [GitHub Actions Setup Guide](#-github-actions-serverless-deployment)** below
3. **Done!** Your bot runs automatically every 15 minutes

**Benefits:**
- ✅ **Zero infrastructure**: No servers, VPS, or hosting needed
- ✅ **Always online**: Runs on GitHub's reliable infrastructure  
- ✅ **Free forever**: Uses GitHub's free tier (2000 minutes/month)
- ✅ **Zero maintenance**: Automatic updates and reliability

### 🛠️ Local Development Setup

**Only needed for development, testing, or custom modifications.**

#### Prerequisites
- Python 3.13 or higher
- Git

#### Steps

```bash
# Clone your forked repository (or the original)
git clone https://github.com/YOUR-USERNAME/Carrington-Event-Telegram-Alert.git
cd Carrington-Event-Telegram-Alert

# Create a virtual environment (recommended)
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your Telegram credentials
# Then run single poll cycle for testing:
python main.py
```

**Note:** Local runs execute **one poll cycle** and exit (serverless design). For continuous monitoring, use the GitHub Actions deployment.

---

## Configuration

CarringtonWatch is designed for **serverless deployment** on GitHub Actions. Configuration is handled entirely through **environment variables** (GitHub Secrets) with optional fallback to `config/settings.json` for advanced threshold tuning.

### GitHub Actions Configuration (Serverless)

For serverless deployment, all configuration is managed through **GitHub repository secrets**:

| Secret Name | Required | Default | Description |
|-------------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | ✅ **Yes** | — | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ **Yes** | — | Your Telegram chat ID for receiving alerts |
| `POLL_INTERVAL_MINUTES` | No | `15` | Polling frequency (GitHub Actions runs every 15 min) |
| `ENABLE_DEBUG` | No | `false` | Enable verbose logging in GitHub Actions |

**How to add secrets:** See the [GitHub Actions Setup Guide](#-github-actions-serverless-deployment) below.

### Local Development Configuration

For local testing and development:

#### Environment Variables (`.env`)

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

#### Advanced Threshold Configuration (`config/settings.json`)

Optional: Customize risk scoring thresholds without code changes:

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

**Note:** Environment variables (GitHub Secrets) always take precedence over `settings.json` values.

### State Management

The serverless version uses **minimal state storage**:

- **`bot_state.json`**: Stores only essential data for alert suppression
- **Auto-committed**: GitHub Actions automatically commits state changes
- **No complex files**: No `state/` directory or historical data storage
- **Stateless design**: Each run is independent, perfect for serverless execution

---

## Usage

### Serverless Usage (Recommended)

**CarringtonWatch is designed to run serverless on GitHub Actions.** See the [GitHub Actions Setup Guide](#-github-actions-serverless-deployment) for complete deployment instructions.

Once deployed:
- ✅ **Automatic monitoring**: Checks space weather every 15 minutes
- ✅ **Smart alerts**: Only sends notifications on meaningful changes  
- ✅ **Rich data**: Each alert includes current space weather metrics
- ✅ **Zero maintenance**: Runs automatically on GitHub's infrastructure

### Local Development Usage

For local testing and development:

```bash
python main.py
```

The bot will run **one poll cycle** and exit (serverless design). For continuous monitoring during development, use the GitHub Actions deployment or run the script manually at intervals.

On startup the bot will:
1. Validate configuration  
2. Collect current NOAA space weather data
3. Compute risk assessment
4. Send alert if conditions warrant (or suppress if no change)
5. Update `bot_state.json` 
6. Exit cleanly

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
├── main.py                  # Serverless entry point (single poll cycle)
├── bot_state.json          # Minimal state (auto-updated by GitHub Actions)
├── src/
│   ├── config.py            # Configuration loading and validation
│   ├── collector.py         # NOAA data fetching and parsing
│   ├── analyzer.py          # Risk scoring engine
│   └── notifier.py          # Telegram message formatting and sending
├── config/
│   └── settings.json        # Optional threshold configuration
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions serverless deployment
├── tests/                   # Test suite
├── requirements.txt         # Python dependencies
├── .env.example             # Local development template
└── README.md
```

### Key Architecture Changes

**Serverless-First Design:**
- ✅ **`main.py`**: Single execution entry point (not continuous loop)
- ✅ **`bot_state.json`**: Minimal state in repository (not complex file structure)  
- ✅ **GitHub Actions scheduling**: Replaces internal Python scheduler
- ✅ **Stateless execution**: Each run is independent and clean
- ❌ **Removed**: `state/` directory, `scheduler.py`, `logs/` management

---

## 🚀 GitHub Actions Serverless Deployment

**CarringtonWatch can run completely serverless on GitHub Actions** — no server, VPS, or hosting required! The bot runs every 15 minutes automatically and stores its state directly in your repository.

### Quick Start (Fork & Deploy)

1. **Fork this repository** to your GitHub account
2. **Set up Telegram bot** (see instructions below) 
3. **Configure GitHub secrets** (see instructions below)
4. **Enable GitHub Actions** in your forked repository
5. **Done!** The bot will start running automatically every 15 minutes

### 🤖 Step 1: Create a Telegram Bot

1. **Message [@BotFather](https://t.me/BotFather)** on Telegram
2. **Send** `/newbot` and follow the prompts
3. **Choose a name** (e.g., "My CarringtonWatch Bot")
4. **Choose a username** (e.g., "mycarringtonwatch_bot")
5. **Copy the bot token** — you'll need this for GitHub secrets

### 📋 Step 2: Get Your Chat ID

You need your Telegram chat ID to receive alerts:

**Option A: Use @userinfobot**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your chat ID (a number like `123456789`)

**Option B: Use your bot**
1. Start a chat with your new bot (from Step 1)
2. Send any message to your bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Replace `<YOUR_BOT_TOKEN>` with your actual bot token
5. Look for `"chat":{"id":123456789` in the response

### 🔧 Step 3: Configure GitHub Secrets

Your forked repository needs access to your Telegram credentials:

1. Go to your forked repository on GitHub
2. Click **Settings** tab
3. In left sidebar: **Secrets and variables** → **Actions**
4. Click **"New repository secret"** for each:

| Secret Name | Value | Example |
|-------------|--------|---------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 | `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `TELEGRAM_CHAT_ID` | Your chat ID from Step 2 | `123456789` |

### ⚡ Step 4: Enable GitHub Actions

1. Go to your forked repository on GitHub
2. Click **Actions** tab  
3. If prompted, click **"I understand my workflows, go ahead and enable them"**
4. The bot will start running automatically every 15 minutes

### 📊 Step 5: Monitor and Test

#### **Manual Test Run**
- Go to **Actions** tab → **CarringtonWatch Bot** workflow
- Click **"Run workflow"** button to test immediately

#### **Check Logs** 
- Click on any workflow run to see detailed logs
- Look for "✅ CarringtonWatch serverless cycle completed" 

#### **Verify Alerts**
- Your bot should send a welcome message on first run
- Check your Telegram chat for the initial alert

### 🔧 Optional Configuration

#### **Custom Polling Interval**
Add these optional repository secrets to customize behavior:

| Secret Name | Default | Description |
|-------------|---------|-------------|
| `POLL_INTERVAL_MINUTES` | `15` | How often to check (GitHub Actions minimum: 5 min) |
| `ENABLE_DEBUG` | `false` | Enable verbose logging |

#### **Modify Alert Thresholds**
Edit `config/settings.json` in your fork to adjust when alerts are triggered.

### 🎯 What You Get

- **🆓 Zero cost**: Runs on GitHub's free tier (2000 minutes/month)
- **🔄 Automatic**: Checks space weather every 15 minutes
- **📱 Smart alerts**: Only notifies on meaningful changes
- **📊 Rich data**: Each alert includes current space weather metrics
- **🛠 No maintenance**: GitHub handles all infrastructure
- **📈 Scalable**: Can handle multiple bots in different repositories

### 🔍 Troubleshooting

#### **No alerts received:**
- Check GitHub Actions logs for errors
- Verify secrets are set correctly (no extra spaces)
- Test your bot token: message your bot directly first

#### **"Permission denied" errors:**
- Ensure GitHub Actions is enabled in your repository
- Check that secrets are added to the correct repository/environment

#### **"Configuration error" messages:**
- Double-check secret names are exactly: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- Verify secret values don't have extra spaces or characters

#### **Bot stops working:**
- GitHub Actions may pause inactive workflows after 60 days
- Simply run the workflow manually to reactivate it

### 📚 Advanced Usage

#### **Multiple Alert Recipients**
- Create a Telegram group
- Add your bot to the group  
- Use the group chat ID instead of your personal chat ID

#### **Custom Schedules**
- Edit `.github/workflows/ci.yml`
- Modify the `cron` schedule (minimum 5 minutes on GitHub)
- Use [crontab.guru](https://crontab.guru) to build custom schedules

#### **Fork Maintenance** 
- Occasionally pull upstream changes: `git pull upstream master`
- GitHub will preserve your secrets and configuration

---

## Deployment Considerations

### Serverless Deployment (Recommended)

**CarringtonWatch is designed for serverless deployment** and runs perfectly on GitHub Actions with zero infrastructure requirements:

- ✅ **Zero cost**: Free GitHub Actions tier (2000 minutes/month)
- ✅ **Zero maintenance**: No servers, updates, or monitoring needed
- ✅ **Built-in reliability**: GitHub's enterprise-grade infrastructure
- ✅ **Auto-scaling**: Handles traffic spikes automatically
- ✅ **State persistence**: Commits state changes back to repository

**Resource Usage (GitHub Actions):**
- CPU: ~30 seconds per run (every 15 minutes)
- Memory: ~100 MB during execution
- Storage: Minimal (`bot_state.json` ~200 bytes)
- Network: Outbound HTTPS to NOAA and Telegram APIs only

### Traditional Server Deployment (Advanced)

For advanced users who prefer traditional hosting, you can run as a service or container:

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

### Resource Usage (Traditional Hosting)

- Memory: ~50 MB typical
- CPU: Negligible (one HTTP poll cycle every 15 minutes)
- Disk: Minimal state storage (`bot_state.json` only)
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
