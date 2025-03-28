# main.py

import logging
import asyncio
import os
import signal
import sys
import aiosqlite
from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackContext, ConversationHandler, CallbackQueryHandler, Defaults, JobQueue,
    ApplicationHandlerStop
)
from telegram.constants import ParseMode
from typing import Optional

import config
# Import DB functions
from database import (
    db_manager, initialize_database, connect_db, close_db, get_db_connection
)
# Import handlers
from handlers import (
    start, add_habit, mark_done, view_habits, reminders, manage_habits, errors,
    edit_habit
)
# Import the decorator
from utils.checks import require_membership
# Import constants
from utils import constants as c
# Import reminder scheduling function
from handlers.reminders import schedule_all_reminders

logger = logging.getLogger(__name__)

# --- Application Setup (post_init, post_stop unchanged) ---
async def post_init(application: Application) -> None:
    logger.info("Running post_init...")
    if not application.job_queue:
        logger.warning("post_init: application.job_queue is not available at this stage.")
    else:
        logger.info(f"post_init: application.job_queue object found: {application.job_queue}")
    logger.info("post_init finished.")

async def post_stop(application: Application) -> None:
    logger.info("Running post_stop...")
    await close_db()
    logger.info("post_stop: Database connection closed.")


async def main() -> None:
    """Main entry point for the bot."""
    # --- Database Setup (unchanged) ---
    logger.info(f"Checking database file: {config.DATABASE_FILE}")
    if config.RESET_DB_ON_START and os.path.exists(config.DATABASE_FILE):
        logger.warning(f"RESET_DB_ON_START is True. Deleting existing database: {config.DATABASE_FILE}")
        try:
            os.remove(config.DATABASE_FILE)
            if os.path.exists(f"{config.DATABASE_FILE}-wal"): os.remove(f"{config.DATABASE_FILE}-wal")
            if os.path.exists(f"{config.DATABASE_FILE}-shm"): os.remove(f"{config.DATABASE_FILE}-shm")
            logger.info("Database deleted.")
        except OSError as e:
            logger.error(f"Failed to delete database file: {e}", exc_info=True)

    try:
        logger.info("Initializing database schema (if needed)...")
        await initialize_database()
        logger.info("Database schema initialization check complete.")
        logger.info("Establishing global database connection...")
        await connect_db()
        logger.info("Global database connection established.")
    except (aiosqlite.Error, ConnectionError) as e:
        logger.critical(f"!!! FAILED to initialize or connect to the database: {e}. Exiting.", exc_info=True)
        return

    # --- Application Build (unchanged) ---
    logger.info("Building application...")
    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=config.USER_TIMEZONE)
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )
    logger.info("Application built.")

    # --- Register Handlers ---
    logger.info("Registering handlers...")
    try:
        logger.info("Membership pre-check handlers removed. Using decorator instead.")

        # --- Group 0: Regular Handlers (Apply Decorator where needed) ---
        # Decorate simple command/callback handlers here
        decorated_start = require_membership(start.start)
        decorated_help_command = require_membership(start.help_command)
        decorated_mark_done_command = require_membership(mark_done.mark_done_command)
        decorated_show_today = require_membership(view_habits.show_today)
        decorated_show_history = require_membership(view_habits.show_history)
        decorated_show_stats = require_membership(view_habits.show_stats)
        decorated_list_reminders = require_membership(reminders.list_reminders)

        decorated_mark_done_button_press = require_membership(mark_done.mark_done_button_press)
        decorated_mark_done_select_habit_callback = require_membership(mark_done.mark_done_select_habit_callback)
        decorated_delete_reminder_button = require_membership(reminders.delete_reminder_button)
        # Note: Conversation entry points are decorated *inside* their respective handler files


        # --- Register Handlers ---
        # Conversation Handlers (Factory functions handle internal decoration)
        application.add_handler(add_habit.add_habit_conv_handler())
        application.add_handler(manage_habits.delete_habit_conv_handler())
        application.add_handler(reminders.set_reminder_conv_handler())
        application.add_handler(edit_habit.edit_habit_conv_handler())

        # Command Handlers (using decorated functions)
        application.add_handler(CommandHandler(c.CMD_START, decorated_start))
        application.add_handler(CommandHandler(c.CMD_HELP, decorated_help_command))
        application.add_handler(CommandHandler(c.CMD_DONE, decorated_mark_done_command))
        application.add_handler(CommandHandler(c.CMD_TODAY, decorated_show_today))
        application.add_handler(CommandHandler(c.CMD_HISTORY, decorated_show_history))
        application.add_handler(CommandHandler(c.CMD_STATS, decorated_show_stats))
        application.add_handler(CommandHandler(c.CMD_MANAGE_REMINDERS, decorated_list_reminders))
        # --- ADD REFRESH HANDLER ---
        # Get the handler function from the start module
        application.add_handler(CommandHandler(c.CMD_REFRESH_MEMBERSHIP, start.refresh_membership_command))
        # --- END ADD ---

        # CallbackQuery Handlers (using decorated functions where needed)
        application.add_handler(CallbackQueryHandler(decorated_mark_done_button_press, pattern=f"^{c.CALLBACK_MARK_DONE}"))
        application.add_handler(CallbackQueryHandler(decorated_mark_done_select_habit_callback, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}"))
        application.add_handler(CallbackQueryHandler(decorated_delete_reminder_button, pattern=f"^{c.CALLBACK_DELETE_REMINDER}"))
        application.add_handler(CallbackQueryHandler(view_habits.show_history_paginated, pattern=f"^{c.CALLBACK_HISTORY_PAGE}")) # No decorator needed


        # --- Group 1: Error Handler ---
        application.add_error_handler(errors.error_handler)

        logger.info("Handlers registered successfully using decorators (incl. inside conv factories).")
    except Exception as e:
        logger.critical(f"!!! FAILED to register handlers: {e}", exc_info=True)
        await close_db()
        return

    # --- Manual Bot Lifecycle Management (unchanged) ---
    stop_event = asyncio.Event()
    async def run_bot_until_stopped():
        nonlocal stop_event
        initialization_successful = False
        try:
            logger.info("Initializing application (runs post_init)...")
            await application.initialize()
            initialization_successful = True
            logger.info("Application initialization completed.")

            logger.info("Attempting to schedule reminders from database...")
            jq = application.job_queue
            if jq:
                logger.info(f"JobQueue object found after initialize: {jq}. Proceeding with scheduling.")
                try:
                    db_conn = await get_db_connection()
                    await schedule_all_reminders(db_conn, jq)
                    logger.info("Reminder scheduling attempt complete.")
                except ConnectionError:
                    logger.critical("DATABASE CONNECTION UNAVAILABLE during reminder scheduling after initialize.")
                except Exception as e:
                    logger.error(f"Error during reminder scheduling after initialize: {e}", exc_info=True)
            else:
                logger.error("JobQueue object STILL NOT FOUND after application.initialize()! Reminders cannot be scheduled.")

            logger.info("Starting updater polling...")
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("Starting application handlers...")
            await application.start()
            logger.info(f"Bot is running ({config.USER_TIMEZONE})... Press Ctrl+C to stop.")
            await stop_event.wait()
            logger.info("Stop signal received. Initiating shutdown...")

        except Exception as e:
            logger.critical(f"Unhandled exception during bot startup or run: {e}", exc_info=True)
            stop_event.set()

        finally:
             logger.info("Entering shutdown phase...")
             if application.updater and application.updater.running:
                 logger.debug("Stopping updater...")
                 await application.updater.stop()
                 logger.debug("Updater stopped.")
             if application.running:
                 logger.debug("Stopping application...")
                 await application.stop()
                 logger.debug("Application stopped.")
             logger.debug("Shutting down application (runs post_stop)...")
             await application.shutdown()
             logger.debug("Application shutdown finished.")
             logger.info("run_bot_until_stopped finished.")

    # Setup Signal Handling (unchanged)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError: logger.warning(f"Signal handler for {sig} not supported on this platform. Use Ctrl+C.")

    # Start the main bot runner task (unchanged)
    await run_bot_until_stopped()

# Main execution block (unchanged)
if __name__ == "__main__":
    logger.info("Script starting...")
    logger.info(f"Python version: {sys.version}")
    try:
        import telegram
        logger.info(f"python-telegram-bot version: {telegram.__version__}")
        logger.info(f"aiosqlite version: {aiosqlite.sqlite_version}")
        logger.info(f"aiosqlite library version: {aiosqlite.__version__}")
    except ImportError as e:
        logger.warning(f"Could not import library for version check: {e}")

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown initiated from main loop (KeyboardInterrupt/SystemExit). Exiting.")
    except Exception as e:
         logger.critical(f"Unhandled exception in top-level asyncio.run: {e}", exc_info=True)
    finally:
         if db_manager._db_connection:
              logger.warning("Performing final DB close check in main script finally block (post_stop might have failed).")
              try: asyncio.run(close_db())
              except RuntimeError as re: logger.error(f"Could not run final DB close in finally block: {re}. Connection might remain open.")
         logger.info("Script finished.")