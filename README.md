# Telegram Habit Tracker Bot (Persian)

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v22+-blue)](https://python-telegram-bot.org/)
[![aiosqlite](https://img.shields.io/badge/database-aiosqlite-orange)](https://github.com/omnilib/aiosqlite)

A Telegram bot built with Python and `python-telegram-bot` to help users track their daily habits. It supports adding habits, marking them as done, viewing progress, statistics, and setting daily reminders. The bot interface is primarily in Persian (Farsi).

## Features

*   ✅ **Add Habits:** Define new habits with optional descriptions and categories.
*   ✅ **Mark Done:** Mark habits as completed for the day via command (`/done`) or inline buttons.
*   ✅ **Today View:** See the status (pending/done) of all your habits for the current day with quick "Done" buttons.
*   ✅ **History:** View a log of recently completed (or missed) habits.
*   ✅ **Statistics:** Get insights into your habit consistency over the last 30 days, including completion rates and streaks (current and maximum).
*   ✅ **Reminders:** Set, view, and delete daily reminders for specific habits at your chosen time.
*   ✅ **Manage Habits:** Delete habits you no longer want to track (this also removes associated logs and reminders).
*   ✅ **User-Friendly:** Conversation-based flows for adding/deleting habits and setting reminders.
*   ✅ **Robust:** Asynchronous design using `asyncio` and `aiosqlite`, proper error handling, and configuration management.
*   ✅ **Localization:** User-facing text is stored separately for easier modification (currently in Persian).

## Requirements

*   Python 3.9+
*   pip (Python package installer)
*   Telegram Bot Token (get one from @BotFather on Telegram)

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a Virtual Environment:**
    (Recommended to isolate dependencies)
    ```bash
    # On Linux/macOS
    python3 -m venv venv
    source venv/bin/activate

    # On Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a file named `.env` in the root project directory. You can copy `.env.example` if one exists, or create it from scratch. Add the following variables:

    ```dotenv
    # --- REQUIRED ---
    # Get this from @BotFather on Telegram
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

    # --- RECOMMENDED / DEFAULTS ---
    # Timezone for scheduling reminders and determining 'today'
    # Use a valid IANA timezone name (e.g., Asia/Tehran, Europe/London, UTC)
    # List: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    USER_TIMEZONE="Asia/Tehran"

    # Path to the SQLite database file
    DATABASE_FILE="habits_data.db"

    # --- OPTIONAL ---
    # Your Telegram User ID (integer) to receive detailed error reports
    # DEVELOPER_CHAT_ID=123456789

    # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    # LOG_LEVEL="INFO"

    # Set to "1" to delete and re-initialize the database on startup (USE WITH CAUTION!)
    # RESET_DB_ON_START="0"
    ```
    **Important:** Make sure to replace `"YOUR_TELEGRAM_BOT_TOKEN"` with the actual token you received from BotFather. Adjust `USER_TIMEZONE` to your local timezone.

## Running the Bot

Once the setup is complete, run the main script:

```bash
python main.py


The bot should start, connect to Telegram, initialize the database (if needed), schedule any existing reminders, and begin polling for updates. You can stop the bot by pressing Ctrl+C.

Usage

Interact with the bot on Telegram using the following commands:

/start - Display welcome message and help.

/help - Show the list of available commands.

/add_habit - Start the process to add a new habit.

/today - Show the status of your habits for today with "Mark Done" buttons.

/done [habit_name] - Mark a specific habit as done for today (case-insensitive).

/history - Display recent habit completion history.

/stats - Show habit completion statistics for the last 30 days.

/set_reminder - Start the process to set or update a daily reminder for a habit.

/manage_reminders - View your active reminders with options to delete them.

/delete_habit - Start the process to permanently delete a habit and its data.

/cancel - Cancel the current multi-step operation (like adding/deleting a habit).

Project Structure
.
├── database/             # Database interaction logic (schema, queries)
│   ├── __init__.py
│   └── db_manager.py
├── handlers/             # Telegram update handlers (commands, conversations, callbacks)
│   ├── __init__.py
│   ├── add_habit.py
│   ├── errors.py
│   ├── manage_habits.py
│   ├── mark_done.py
│   ├── reminders.py
│   ├── start.py
│   └── view_habits.py
├── utils/                # Helper functions, constants, localization, keyboards
│   ├── __init__.py
│   ├── constants.py
│   ├── helpers.py
│   ├── keyboards.py
│   └── localization.py   # User-facing strings (Persian)
├── .env                  # Environment variables (contains secrets - DO NOT COMMIT)
├── .gitignore            # Specifies intentionally untracked files
├── config.py             # Loads configuration and sets up logging
├── main.py               # Main application entry point, setup, and run
└── requirements.txt      # Project dependencies
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
IGNORE_WHEN_COPYING_END
Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue. If you'd like to contribute code, please fork the repository and submit a pull request.

License

This project is licensed under the MIT License - see the LICENSE file for details (if a LICENSE file is present).

IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
IGNORE_WHEN_COPYING_END
