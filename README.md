# Habit Tracker Bot

A feature-rich Telegram bot built with Python and the python-telegram-bot library that helps users track and manage their daily habits with reminders and analytics.

## 🌟 Features

- **Habit Management**: Add, edit, and delete habits
- **Progress Tracking**: Mark habits as done, pending, or skipped
- **Daily View**: View today's habits with completion status
- **History**: Browse habit completion history with pagination
- **Statistics**: Detailed analytics including completion rates and streaks
- **Reminders**: Customizable daily reminders for habits
- **Membership Check**: Optional channel membership verification
- **Multi-user Support**: Each user manages their own habits independently

## 🛠️ Tech Stack

- **Python 3.10+**
- **python-telegram-bot** (v22.5 with JobQueue)
- **aiosqlite** (async SQLite interface)
- **Pydantic** (v2.x for configuration management)
- **Pydantic Settings** (for environment configuration)
- **APScheduler** (for reminder scheduling)

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pooryas98/Habit_TrackerBot.git
   cd Habit_TrackerBot
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your bot token and other configuration

## ⚙️ Configuration

The bot uses Pydantic Settings for configuration management. All parameters are loaded from environment variables:

### Required:
- `BOT_TOKEN`: Your Telegram bot token from @BotFather

### Optional:
- `DATABASE_FILE`: Path to SQLite database file (default: `habits_data.db`)
- `USER_TIMEZONE`: User timezone for scheduling (default: `UTC`, e.g., `America/New_York`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `RESET_DB_ON_START`: Set to `1` to reset database on startup (default: `0`)
- `DEVELOPER_CHAT_ID`: Chat ID for receiving error notifications (optional)
- `REQUIRED_CHANNEL_IDS`: Comma-separated list of required channels for access (optional)
- `CHANNEL_MEMBERSHIP_CACHE_TTL`: Cache TTL in seconds for membership checks (default: `300`)

## 🏃‍♂️ Running the Bot

```bash
python main.py
```

The bot will connect to Telegram and start processing messages.

## 🤖 Available Commands

### Core Commands
- `/start` - Welcome message and initial setup
- `/help` - Show help information and available commands

### Habit Management
- `/add_habit` - Add a new habit
- `/edit_habit` - Edit an existing habit
- `/delete_habit` - Delete a habit and all related data

### Tracking & Reporting
- `/today` - View today's habits and mark them as done
- `/done [habit_name]` - Mark a specific habit as done
- `/history` - View habit completion history
- `/stats` - View habit completion statistics

### Reminders
- `/set_reminder` - Set daily reminders for a habit
- `/manage_reminders` - View and manage active reminders

### Other
- `/refresh_membership` - Refresh channel membership status (if channel lock is enabled)
- `/cancel` - Cancel ongoing conversations

## 🏗️ Architecture

### Database Layer
- **DatabaseService**: Central service for all database operations with dependency injection
- **Optimized queries**: Single-query approach for fetching habit statuses
- **SQLite**: Local database with WAL mode for better concurrency

### Configuration
- **Pydantic Settings**: Robust configuration management with validation
- **Environment variables**: Secure configuration loading from `.env`

### Structure
```
habit-tracker-bot/
├── main.py                 # Entry point
├── config.py              # Configuration management
├── database/              # Database layer
│   ├── service.py         # DatabaseService class
│   └── connection.py      # Connection management
├── bot/                   # Bot application lifecycle
├── handlers/              # Command handlers
│   ├── common/            # Shared functionality
│   ├── habits/            # Habit management
│   ├── tracking/          # Habit tracking
│   └── reminders/         # Reminder management
├── scheduling/            # Reminder scheduling
├── utils/                 # Utilities and helpers
└── requirements.txt       # Dependencies
```

## 🧪 Testing

To run tests (Comimg soon!):

## 🔒 Security

- Environment variables for sensitive configuration
- Input validation through Pydantic
- Proper error handling and logging
- Optional channel membership verification

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

If you encounter any issues or have questions, please open an issue in the repository.

## 🙏 Acknowledgments

- [python-telegram-bot](https://python-telegram-bot.org/) for the excellent Telegram bot framework
- [Pydantic](https://pydantic.dev/) for configuration management
- All contributors who help maintain and improve this project