import logging
import asyncio
import os
import signal
import sys
import aiosqlite
from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, ConversationHandler, CallbackQueryHandler, Defaults, JobQueue
)
from telegram.constants import ParseMode
from typing import Optional
import config
from database import db_manager, initialize_database, connect_db, close_db, get_db_connection
from handlers import (
    start, add_habit, mark_done, view_habits, reminders, manage_habits, errors, edit_habit
)
from utils.checks import require_membership
from utils import constants as c
from handlers.reminders import schedule_all_reminders

logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    logger.info("post_init executed.")
    if application.job_queue: logger.debug(f" JobQueue available in post_init: {application.job_queue}")
    else: logger.warning(" JobQueue NOT available in post_init.")

async def post_stop(application: Application) -> None:
    logger.info("Running post_stop...")
    await close_db()
    logger.info("Database connection closed in post_stop.")

async def main() -> None:
    """Main entry point."""
    # --- DB Setup ---
    if config.RESET_DB_ON_START and os.path.exists(config.DATABASE_FILE):
        logger.warning(f"RESET_DB_ON_START: Deleting DB: {config.DATABASE_FILE}")
        try:
            os.remove(config.DATABASE_FILE)
            if os.path.exists(f"{config.DATABASE_FILE}-wal"): os.remove(f"{config.DATABASE_FILE}-wal")
            if os.path.exists(f"{config.DATABASE_FILE}-shm"): os.remove(f"{config.DATABASE_FILE}-shm")
        except OSError as e: logger.error(f"Failed to delete DB: {e}", exc_info=True)
    try:
        await initialize_database()
        await connect_db()
    except (aiosqlite.Error, ConnectionError) as e:
        logger.critical(f"DB init/connection failed: {e}. Exiting.", exc_info=True)
        return

    # --- App Build ---
    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=config.USER_TIMEZONE)
    application = ( ApplicationBuilder().token(config.BOT_TOKEN).defaults(defaults)
                    .post_init(post_init).post_stop(post_stop).build() )
    logger.info("Application built.")

    # --- Register Handlers ---
    try:
        # Apply membership decorator where needed for simple handlers
        decorated_start = require_membership(start.start)
        decorated_help = require_membership(start.help_command)
        decorated_mark_done_cmd = require_membership(mark_done.mark_done_command)
        decorated_show_today = require_membership(view_habits.show_today)
        decorated_show_hist = require_membership(view_habits.show_history)
        decorated_show_stats = require_membership(view_habits.show_stats)
        decorated_list_reminders = require_membership(reminders.list_reminders)
        decorated_mark_done_btn = require_membership(mark_done.mark_done_button_press)
        decorated_mark_done_select = require_membership(mark_done.mark_done_select_habit_callback)
        decorated_del_reminder_btn = require_membership(reminders.delete_reminder_button)
        # Conversation entry points are decorated within their handler files

        # Conversations (factories handle internal decoration)
        application.add_handler(add_habit.add_habit_conv_handler())
        application.add_handler(manage_habits.delete_habit_conv_handler())
        application.add_handler(reminders.set_reminder_conv_handler())
        application.add_handler(edit_habit.edit_habit_conv_handler())

        # Commands (using decorated functions)
        application.add_handler(CommandHandler(c.CMD_START, decorated_start))
        application.add_handler(CommandHandler(c.CMD_HELP, decorated_help))
        application.add_handler(CommandHandler(c.CMD_DONE, decorated_mark_done_cmd))
        application.add_handler(CommandHandler(c.CMD_TODAY, decorated_show_today))
        application.add_handler(CommandHandler(c.CMD_HISTORY, decorated_show_hist))
        application.add_handler(CommandHandler(c.CMD_STATS, decorated_show_stats))
        application.add_handler(CommandHandler(c.CMD_MANAGE_REMINDERS, decorated_list_reminders))
        application.add_handler(CommandHandler(c.CMD_REFRESH_MEMBERSHIP, start.refresh_membership_command)) # No decorator needed

        # Callbacks (using decorated functions where needed)
        application.add_handler(CallbackQueryHandler(decorated_mark_done_btn, pattern=f"^{c.CALLBACK_MARK_DONE}"))
        application.add_handler(CallbackQueryHandler(decorated_mark_done_select, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}"))
        application.add_handler(CallbackQueryHandler(decorated_del_reminder_btn, pattern=f"^{c.CALLBACK_DELETE_REMINDER}"))
        application.add_handler(CallbackQueryHandler(view_habits.show_history_paginated, pattern=f"^{c.CALLBACK_HISTORY_PAGE}")) # No decorator needed

        # Error Handler (last)
        application.add_error_handler(errors.error_handler)
        logger.info("Handlers registered.")
    except Exception as e:
        logger.critical(f"FAILED to register handlers: {e}", exc_info=True)
        await close_db()
        return

    # --- Bot Lifecycle ---
    stop_event = asyncio.Event()
    async def run_bot_until_stopped():
        nonlocal stop_event
        try:
            logger.info("Initializing application...")
            await application.initialize() # Runs post_init
            logger.info("Scheduling reminders...")
            jq = application.job_queue
            if jq:
                try:
                    db_conn = await get_db_connection()
                    await schedule_all_reminders(db_conn, jq)
                except ConnectionError: logger.critical("DB UNAVAILABLE during reminder scheduling.")
                except Exception as e: logger.error(f"Reminder scheduling error: {e}", exc_info=True)
            else: logger.error("JobQueue NOT FOUND after init! Reminders skipped.")

            logger.info("Starting polling...")
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            await application.start()
            logger.info(f"Bot is running ({config.USER_TIMEZONE}). Press Ctrl+C to stop.")
            await stop_event.wait() # Wait for signal
            logger.info("Stop signal received...")

        except Exception as e: logger.critical(f"Bot startup/run error: {e}", exc_info=True); stop_event.set()
        finally:
             logger.info("Shutting down...")
             if application.updater and application.updater.running: await application.updater.stop()
             if application.running: await application.stop()
             await application.shutdown() # Runs post_stop
             logger.info("run_bot_until_stopped finished.")

    # --- Signal Handling ---
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError: logger.warning(f"Signal {sig} not supported. Use Ctrl+C.")

    await run_bot_until_stopped()

if __name__ == "__main__":
    logger.info("Script starting...")
    logger.info(f" Python: {sys.version.split()[0]} | PTB: {getattr(__import__('telegram'), '__version__', 'N/A')} "
                f"| aiosqlite: {getattr(__import__('aiosqlite'), 'sqlite_version', 'N/A')} "
                f"({getattr(__import__('aiosqlite'), '__version__', 'N/A')})")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): logger.info("Shutdown via KeyboardInterrupt/SystemExit.")
    except Exception as e: logger.critical(f"Unhandled exception in asyncio.run: {e}", exc_info=True)
    finally:
         # Final check for DB connection closure, post_stop might fail
         if db_manager._db_connection:
              logger.warning("Final DB close check (post_stop might have failed)...")
              try: asyncio.run(close_db())
              except RuntimeError as re: logger.error(f"Final DB close failed: {re}.")
         logger.info("Script finished.")