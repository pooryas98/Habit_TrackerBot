# Telegram Habit Tracker Bot

A flexible and asynchronous Telegram bot designed to help users track habits, set daily reminders, view progress statistics, and manage their habit journey effectively. Built with `python-telegram-bot`.

## Table of Contents

- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup Steps](#setup-steps)
- [Usage](#usage)
  - [Available Commands](#available-commands)
  - [Conversations & Interactions](#conversations--interactions)
  - [Channel Membership](#channel-membership)
- [Features](#features)
- [Getting Started (Quick Start)](#getting-started-quick-start)
- [Technologies Used](#technologies-used)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Installation

Follow these steps to get the bot up and running on your own system.

### Prerequisites

*   **Python:** Version 3.8 or higher is recommended (due to `python-telegram-bot` v22+ features and `zoneinfo`).
*   **pip:** Python package installer.
*   **Git:** For cloning the repository.
*   **Telegram Bot Token:** Obtain one from BotFather on Telegram.

### Setup Steps

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
    *(Replace `<repository-url>` and `<repository-directory>` with the actual URL and the name of the cloned folder)*

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Linux/macOS
    source venv/bin/activate
    # On Windows
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a file named `.env` in the project's root directory. Add the following required and optional variables:

    ```dotenv
    # REQUIRED: Get this from BotFather on Telegram
    BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"

    # OPTIONAL: Database file path (defaults to 'habits_data.db' in the root)
    # DATABASE_FILE="data/my_habits.db"

    # OPTIONAL: User's local timezone (defaults to UTC). Use TZ Database names (e.g., "America/New_York", "Europe/London", "Asia/Tehran")
    USER_TIMEZONE="UTC"

    # OPTIONAL: Your Telegram User ID for receiving error notifications
    # DEVELOPER_CHAT_ID="YOUR_TELEGRAM_USER_ID"

    # OPTIONAL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Defaults to INFO.
    # LOG_LEVEL="DEBUG"

    # OPTIONAL: Set to "1" to delete and recreate the database schema on startup. USE WITH CAUTION! Defaults to "0" (off).
    # RESET_DB_ON_START="0"

    # OPTIONAL: Comma-separated list of channel IDs/usernames required for bot access.
    # Starts with '@' for public channels, numeric ID for private. Example: "@mychannel,-1001234567890"
    # REQUIRED_CHANNEL_IDS=""

    # OPTIONAL: Cache duration (seconds) for channel membership checks. Defaults to 300 (5 minutes).
    # CHANNEL_MEMBERSHIP_CACHE_TTL="600"
    ```
    *   **Crucially, set `BOT_TOKEN`**.
    *   Adjust `USER_TIMEZONE` to match your users' primary timezone for correct daily tracking and reminders.
    *   Configure `REQUIRED_CHANNEL_IDS` if you want to restrict bot access.

5.  **Run the Bot:**
    ```bash
    python main.py
    ```
    The bot should now be running and connected to Telegram.

## Usage

Interact with the bot on Telegram using the commands listed below.

### Available Commands

*   **/start:** Displays a welcome message and initializes the user profile in the database.
*   **/help:** Shows the list of available commands and their descriptions.

**Habit Management:**

*   **/add\_habit:** Starts a conversation to add a new habit (name, optional description, optional category).
*   **/edit\_habit:** Starts a conversation to edit an existing habit's name, description, or category.
*   **/delete\_habit:** Starts a conversation to permanently delete a habit and all associated data (logs, reminders).

**Tracking:**

*   **/today:** Shows the status (done/pending) of your habits for the current day with buttons to mark pending habits as done.
*   **/done `[habit_name]`:** Marks a specific habit as done for today. If `[habit_name]` is omitted, it shows a list of habits to choose from.
*   **/history:** Displays a paginated history of your habit completion logs.
*   **/stats:** Shows your habit completion statistics for the last 30 days (completion rate, current streak, max streak).

**Reminders:**

*   **/set\_reminder:** Starts a conversation to set a daily reminder time for a specific habit.
*   **/manage\_reminders:** Lists all your active reminders with options to delete them.

**Other:**

*   **/cancel:** Cancels the current ongoing operation (like adding or editing a habit).
*   **/refresh\_membership:** If channel membership is required, this command forces a re-check of your membership status.

### Conversations & Interactions

*   Adding, editing, deleting habits, and setting reminders are handled through guided conversations. Follow the bot's prompts.
*   Commands like `/today`, `/history`, `/manage_reminders`, and selecting habits for `/done`, `/edit_habit`, `/delete_habit`, and `/set_reminder` use inline keyboard buttons for easy interaction.

### Channel Membership

*   If the `REQUIRED_CHANNEL_IDS` environment variable is set, users must be members of the specified channel(s) to use the bot.
*   If access is denied, the bot will prompt the user to join the required channels and use `/refresh_membership` after joining.

## Features

*   **Habit Management:** Easily add, edit, and delete habits with optional descriptions and categories.
*   **Daily Tracking:** View daily habit status and mark habits as completed via commands or interactive buttons.
*   **History Logging:** Keep track of your habit completion history with pagination support.
*   **Progress Statistics:** Get insights into your performance with completion rates and streak information (current and maximum).
*   **Customizable Reminders:** Set daily reminders for specific habits at your preferred time. Manage active reminders easily.
*   **Asynchronous:** Built using `asyncio` and asynchronous libraries (`python-telegram-bot` v20+, `aiosqlite`) for efficient operation.
*   **Persistent Storage:** Uses SQLite (`aiosqlite`) to store user data, habits, logs, and reminders.
*   **Conversation-Based Workflows:** User-friendly guided conversations for multi-step actions.
*   **Inline Keyboards:** Interactive buttons for quick actions and selections.
*   **Timezone Aware:** Uses configurable timezones for accurate daily tracking based on `USER_TIMEZONE`.
*   **Optional Membership Gate:** Restrict bot usage to members of specific Telegram channels.
*   **Error Handling:** Centralized error handler logs issues and notifies the developer (if configured).
*   **Localization:** Basic support for localization (English and Persian included in `localization.py`).

## Getting Started (Quick Start)

1.  Clone the repository: `git clone <repository-url>`
2.  Navigate into the directory: `cd <repository-directory>`
3.  Install requirements: `pip install -r requirements.txt`
4.  Create a `.env` file and add `BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"`. Optionally set `USER_TIMEZONE`.
5.  Run the bot: `python main.py`
6.  Open Telegram, find your bot, and send `/start`. Use `/help` to see available commands.

## Technologies Used

*   **Language:** Python 3 (3.8+ Recommended)
*   **Telegram Bot Framework:** `python-telegram-bot` (v22+)
*   **Database:** SQLite via `aiosqlite` (asynchronous wrapper)
*   **Timezones:** `pytz`, `zoneinfo` (Python standard library)
*   **Configuration:** `python-dotenv`
*   **Asynchronous Programming:** `asyncio` (Python standard library)

## Contributing

Contributions are welcome! Please follow these steps:

1.  **Fork the repository.**
2.  **Create a new branch:**
    ```bash
    git checkout -b feature/your-amazing-feature
    ```
3.  **Make your changes.** Adhere to the existing code style (e.g., use logging, type hints where appropriate).
4.  **Commit your changes:**
    ```bash
    git commit -m 'Add some amazing feature'
    ```
5.  **Push to the branch:**
    ```bash
    git push origin feature/your-amazing-feature
    ```
6.  **Open a Pull Request** against the `main` branch of the original repository.

## License

No license file was specified in the provided codebase. Please check the repository or contact the maintainers for licensing information before reusing or distributing the code.

## Support

*   For bugs, feature requests, or issues, please use the **GitHub Issue Tracker** associated with the repository.
*   If `DEVELOPER_CHAT_ID` is configured, critical errors will be automatically reported to that user.