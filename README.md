# Telegram Planner Bot

A multi-user Telegram planner bot built with Python and aiogram for managing recurring plans, daily progress ticks, reminders, and activity history.

The bot interface is in Persian and includes Jalali date support.

## Features

- Create and manage multiple independent plans
- Select specific weekdays for each plan
- Configure 1 to 5 required daily progress ticks
- Prevent ticks on unscheduled days
- Prevent users from exceeding the configured daily tick limit
- Store tick history with local time and Jalali date display
- Configure reminder presets for each plan
- Send reminder summaries showing completed and remaining ticks
- Prevent duplicate reminder delivery after application restarts
- Edit plan names, weekdays, tick targets, and reminder settings
- Delete plans with confirmation
- Support multiple Telegram users with isolated data
- Persist data in SQLite
- Optional Telegram proxy configuration
- Recover safely after restarts because persistent state is stored in the database

## Tech Stack

- Python 3.12+
- aiogram 3
- SQLite
- aiosqlite
- asyncio
- python-dotenv
- jdatetime
- aiohttp-socks

## Project Structure

```text
telegram-planner-bot/
├── app/
│   ├── config.py
│   ├── constants.py
│   ├── db.py
│   ├── handlers.py
│   ├── keyboards.py
│   ├── reminders.py
│   ├── states.py
│   └── utils.py
├── bot.py
├── .env.example
├── .gitignore
├── requirements.txt
├── install_windows.bat
├── run_windows.bat
├── check_telegram_connection.bat
└── README.md
```

## Setup

### 1. Create a Telegram bot

Create a bot with `@BotFather` and obtain a bot token.

Do not commit the real token to GitHub.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and set your own bot token:

```env
BOT_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
BOT_TIMEZONE=Asia/Tehran
DATABASE_PATH=data/plan_bot.sqlite3
REMINDER_GRACE_MINUTES=10
TELEGRAM_PROXY=
```

`.env` is ignored by Git and should never be committed.

### 5. Run

```bash
python bot.py
```

On Windows, the included helper scripts can also be used:

- `install_windows.bat`
- `run_windows.bat`
- `check_telegram_connection.bat`

## Data Storage

The default database path is:

```text
data/plan_bot.sqlite3
```

The database contains user IDs, plan data, tick history, and reminder delivery state.

Database files are intentionally excluded from this public repository through `.gitignore`.

## Reminder Scheduling

The bot currently provides three reminder presets:

- 15:00 and 21:00
- 12:00 and 18:00
- 17:00 and 22:00

Reminder calculations use the timezone configured in `BOT_TIMEZONE`.

## Security and Privacy

This public repository intentionally excludes:

- Telegram bot tokens
- `.env`
- SQLite database files
- Runtime user data
- Chat IDs and Telegram user records
- Local logs and editor configuration

Only the application source code and safe configuration examples are included.

## Author

Farid Farahani

Python Developer | Web Developer

Website: https://faridfarahani.ir
