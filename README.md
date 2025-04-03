# Telegram Habit Tracker Bot

A comprehensive Telegram bot built with Python and `python-telegram-bot` to help users track daily habits, set reminders, view progress statistics, and manage their habit data directly within Telegram.

## Table of Contents

- [Features](#features)
- [Technologies Used](#technologies-used)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Getting Started (Quick Start)](#getting-started-quick-start)
- [Usage](#usage)
  - [Commands](#commands)
  - [Conversations](#conversations)
- [Localization](#localization)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

*   **Habit Management:** Add, edit (name, description, category), and delete habits.
*   **Daily Tracking:** Mark habits as 'done' for the current day using commands or interactive buttons.
*   **Today View:** Quickly see the status (done/pending) of all your habits for the current day (`/today`).
*   **History:** View a paginated log of your habit completion history (`/history`).
*   **Statistics:** Get insights into your habit performance over the last 30 days, including completion rates and streaks (`/stats`).
*   **Reminders:** Set daily reminders for specific habits at your preferred time (`/set_reminder`).
*   **Reminder Management:** List and delete active reminders (`/manage_reminders`).
*   **Conversation Flow:** Guided conversations for adding, editing, deleting habits, and setting reminders, with cancellation support (`/cancel`).
*   **Optional Channel Membership:** Restrict bot access to members of specified Telegram channels (configurable).
*   **Timezone Aware:** Uses user-configured timezones for accurate daily tracking and reminders.
*   **Error Handling:** Graceful error handling and optional developer notifications for exceptions.
*   **Localization:** User interface messages localized (currently in Persian/Farsi).

## Technologies Used

*   **Programming Language:** Python 3
*   **Telegram Bot Framework:** [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (v22.0+)
*   **Database:** SQLite (via `aiosqlite` for asynchronous operations)
*   **Scheduling:** `python-telegram-bot`'s built-in `JobQueue` (for reminders)
*   **Timezones:** `pytz`, `zoneinfo` (Python standard library)
*   **Configuration:** `python-dotenv` (for loading environment variables)
*   **Asynchronous Programming:** `asyncio`

## Prerequisites

*   Python 3 (check `python-telegram-bot` documentation for specific version requirements, likely 3.8+)
*   `pip` (Python package installer)
*   Git (for cloning the repository)
*   A Telegram Bot Token (obtainable from [@BotFather](https://t.me/BotFather) on Telegram)
*   Optionally: One or more Telegram Channel IDs (numeric or `@username`) if you want to enforce channel membership.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Create a `.env` file** in the root directory of the project. You can copy/rename `.env.example` if one exists, or create it manually.

2.  **Add the following environment variables** to your `.env` file:

    ```dotenv
    # REQUIRED: Your Telegram Bot Token from BotFather
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

    # Optional: Path to the SQLite database file (defaults to "habits_data.db")
    DATABASE_FILE="habits_data.db"

    # Optional: User's timezone (e.g., "UTC", "Europe/London", "America/New_York"). Defaults to "UTC".
    # See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    USER_TIMEZONE="UTC"

    # Optional: Your Telegram User ID to receive error notifications
    # DEVELOPER_CHAT_ID="YOUR_TELEGRAM_USER_ID"

    # Optional: Comma-separated list of channel IDs (numeric or @username) users must join. Leave empty to disable.
    # REQUIRED_CHANNEL_IDS="@mychannel,-1001234567890"
    REQUIRED_CHANNEL_IDS=""

    # Optional: Cache duration (seconds) for channel membership checks (defaults to 300 seconds / 5 minutes)
    # CHANNEL_MEMBERSHIP_CACHE_TTL=300

    # Optional: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
    LOG_LEVEL="INFO"

    # Optional: Set to "1" to delete the database file on startup (USE WITH CAUTION!). Defaults to "0" (off).
    # RESET_DB_ON_START="0"
    ```

3.  **Save the `.env` file.** The bot will load these variables automatically on startup.

## Running the Bot

Once installed and configured, run the bot using:

```bash
python main.py
```

The bot will initialize, connect to the database, schedule any existing reminders, and start polling for updates from Telegram. Press Ctrl+C to stop the bot gracefully.

## Getting Started (Quick Start)

Clone the repository: ```bash git clone <repo-url> && cd <repo-dir> ```

Install dependencies: pip install -r requirements.txt

Create a .env file and add your BOT_TOKEN.

Run the bot: python main.py

Open Telegram and talk to your bot! Start with /start.

## Usage

Interact with the bot using the commands below within your Telegram chat.

## Commands

/start: Welcome message and initializes user data.

/help: Shows the list of available commands and basic instructions.

/add_habit: Starts a conversation to add a new habit (name, description, category).

/edit_habit: Starts a conversation to edit an existing habit's details.

/today: Shows the status of your habits for the current day with buttons to mark pending habits as done.

/done:

Without arguments: Shows a keyboard to select which habit to mark as done.

With habit name (e.g., /done Exercise): Marks the specified habit as done for today.

/history: Displays your recent habit completion log (paginated).

/stats: Shows your habit completion statistics (rate, streaks) for the last 30 days.

/set_reminder: Starts a conversation to set a daily reminder for a specific habit.

/manage_reminders: Lists your active reminders with buttons to delete them.

/delete_habit: Starts a conversation to permanently delete a habit and its associated data (log, reminders).

/cancel: Cancels any ongoing conversation (like adding or editing a habit).

/refresh_membership: (If channel membership is enabled) Clears the cache and re-checks your membership in the required channels.

## Conversations

Several commands (/add_habit, /edit_habit, /delete_habit, /set_reminder) trigger multi-step conversations. Follow the bot's prompts. You can use /cancel at any time to exit the conversation. When prompted for optional information (like description or category), you can type /skip (or the localized equivalent) to omit it.

## Localization

The bot's user interface text is managed in utils/localization.py. Currently, the provided localization is in Persian (Farsi). You can adapt this file to support other languages.

## Contributing

Contributions are welcome! Please follow these steps:

Fork the repository on GitHub.

Create a new branch for your feature or bug fix:

```bash
git checkout -b feature/your-feature-name
```

Make your changes. Adhere to the existing code style (PEP 8, type hints, async/await).

Commit your changes:

```bash
git commit -m "feat: Add feature X" -m "Detailed description of changes."
```

Push to your branch:

```bash
git push origin feature/your-feature-name
```

Open a Pull Request on the original repository, describing your changes clearly.

## License

No explicit license file was found in the provided codebase. Please assume the code is under the repository owner's copyright unless otherwise stated. If you plan to use or distribute this code, consider adding a license file (e.g., MIT, GPL) or contacting the author.

## Support

If you encounter issues or have questions, please use the GitHub Issues section of the repository.