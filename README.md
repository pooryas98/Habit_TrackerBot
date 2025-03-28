# Habit Tracker Telegram Bot

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A feature-rich, asynchronous Telegram bot built with `python-telegram-bot` to help users track their habits effectively.

## Features

*   **Habit Management:**
    *   Add new habits with optional descriptions and categories.
    *   Edit existing habit details (name, description, category).
    *   Delete habits (including associated logs and reminders).
*   **Tracking & Viewing:**
    *   Mark habits as 'done' for the current day (via command with name, or interactive keyboard).
    *   View a summary of today's habit statuses with interactive 'done' buttons.
    *   View paginated history of habit completions.
    *   View completion statistics (completion rate, current streak, max streak) over the last 30 days.
*   **Reminders:**
    *   Set daily reminders for specific habits at user-defined times.
    *   Manage (view and delete) active reminders.
    *   Reminders persist across bot restarts.
*   **Channel Membership Enforcement (Optional):**
    *   Require users to be members of specified Telegram channels/groups before using the bot.
    *   Efficient caching of membership status to minimize API calls.
    *   `/refresh_membership` command for users to re-check their status after joining.
*   **User Experience:**
    *   Interactive conversations for adding, editing, and deleting habits/reminders.
    *   Inline keyboards for easy interaction.
    *   Localized interface (currently supports Persian/Farsi).
    *   Graceful error handling with user-friendly messages.
*   **Technical:**
    *   Fully asynchronous using `asyncio`, `python-telegram-bot (v20+)`, and `aiosqlite`.
    *   Modular structure (handlers, database, utils, config).
    *   SQLite database backend with WAL (Write-Ahead Logging) enabled for better concurrency.
    *   Configuration via environment variables (`.env` file).
    *   Developer notifications for errors.
    *   Graceful shutdown handling.

## Prerequisites

*   Python 3.9 or higher (due to usage of `zoneinfo`)
*   A Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather)
*   Optionally:
    *   One or more Telegram Channel/Group IDs (numeric or `@username`) if using the membership requirement feature.
    *   Your Telegram User ID (for developer error notifications).

## Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/habit-tracker-bot.git # Replace with your repo URL
    cd habit-tracker-bot
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables:**
    *   Create a file named `.env` in the project's root directory.
    *   Copy the contents of `.env.example` (see below) into `.env`.
    *   Fill in the required values, especially `BOT_TOKEN`.

    **.env.example:**
    ```dotenv
    # REQUIRED: Get this from @BotFather on Telegram
    BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

    # Optional: Database file path (default: habits_data.db)
    # DATABASE_FILE=habits_data.db

    # Optional: Timezone for date calculations (default: UTC). Use IANA timezone names (e.g., Europe/London, America/New_York)
    # See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    # USER_TIMEZONE=Asia/Tehran

    # Optional: Your Telegram User ID to receive error notifications
    # DEVELOPER_CHAT_ID=YOUR_TELEGRAM_USER_ID

    # Optional: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) (default: INFO)
    # LOG_LEVEL=INFO

    # Optional: Set to "1" to delete and recreate the database on startup (USE WITH CAUTION!)
    # RESET_DB_ON_START=0

    # --- Optional Channel Membership Settings ---
    # Comma-separated list of channel/group IDs (numeric or @username) users must join
    # REQUIRED_CHANNEL_IDS=@mychannel, -1001234567890
    # How long (in seconds) to cache a user's membership status (default: 300)
    # CHANNEL_MEMBERSHIP_CACHE_TTL=300
    ```

## Running the Bot

1.  Make sure your virtual environment is activated.
2.  Run the main script:
    ```bash
    python main.py
    ```
3.  The bot should start polling for updates. You can interact with it on Telegram.
4.  To stop the bot gracefully, press `Ctrl+C`.

## Usage (Bot Commands)

Interact with the bot on Telegram using these commands:

*   `/start` - Shows a welcome message and command list.
*   `/help` - Displays the list of available commands.
*   `/add_habit` - Starts a conversation to add a new habit.
*   `/edit_habit` - Starts a conversation to edit an existing habit's name, description, or category.
*   `/today` - Shows the status of your habits for the current day with buttons to mark them done.
*   `/done [habit name]` - Marks a specific habit as done for today. If no name is provided, shows a list to choose from.
*   `/history` - Displays your recent habit activity log (paginated).
*   `/stats` - Shows your habit completion statistics (streaks, rate) for the last 30 days.
*   `/set_reminder` - Starts a conversation to set or update a daily reminder for a habit.
*   `/manage_reminders` - Shows your active reminders with buttons to delete them.
*   `/delete_habit` - Starts a conversation to permanently delete a habit and its data.
*   `/refresh_membership` - Re-checks your membership status in required channels (if enabled).
*   `/cancel` - Cancels any ongoing conversation (like adding or deleting a habit).

**Note:** You can use `/skip` during conversations (add/edit habit) to skip optional fields like description or category.

## Contributing

Contributions are welcome! Please feel free to open an issue to discuss bugs or feature requests, or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (you would need to create a `LICENSE` file with the MIT license text).
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
