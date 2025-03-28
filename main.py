# main.py (Connect DB before build, fix shutdown typo)
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

import config
# Import DB functions
from database import db_manager, initialize_database, connect_db, close_db, get_db_connection
# Import handlers
from handlers import (
    start, add_habit, mark_done, view_habits, reminders, manage_habits, errors
)
from handlers.reminders import schedule_all_reminders

logger = logging.getLogger(__name__)

# --- Application Setup ---

async def post_init(application: Application) -> None:
    """Only schedules jobs. Assumes DB connection is already established."""
    logger.info("Running post_init for job scheduling...")
    try:
        # Schedule Reminders from DB
        job_queue = application.job_queue
        if job_queue:
             logger.info("post_init: JobQueue found. Scheduling reminders...")
             # Get the globally established connection
             db = await get_db_connection()
             await schedule_all_reminders(db, job_queue) # Pass connection
             logger.info("post_init: Reminder scheduling complete.")
        else:
             logger.warning("post_init: JobQueue not found. Reminders will not be scheduled.")

    except Exception as e:
        # Log error but don't close DB here, let shutdown handle it.
        logger.critical(f"!!! CRITICAL ERROR during post_init (job scheduling): {e}", exc_info=True)
        # Don't necessarily halt startup just because reminders failed, but log critically.


async def post_stop(application: Application) -> None:
    """Closes the global database connection."""
    logger.info("Running post_stop to close DB connection...")
    await close_db()
    logger.info("post_stop: DB connection closed.")


async def main() -> None:
    """Initializes DB connection and runs the bot."""
    logger.info("--- Starting Habit Tracker Bot ---")
    db_connection_established_main = False # Track if connection succeeded here

    # --- Establish DB Connection FIRST ---
    try:
        logger.info("main: Attempting DB Connection...")
        await connect_db() # Establish global connection
        db_connection_established_main = True
        logger.info("main: Global DB Connection established successfully.")

        # Initialize Schema after connection is up
        logger.info("main: Initializing DB schema...")
        await initialize_database()
        logger.info("main: DB Schema initialization complete.")

    except Exception as e:
        logger.critical(f"!!! CRITICAL ERROR establishing DB connection or initializing schema: {e}", exc_info=True)
        # If connection was made but init failed, try closing
        if db_connection_established_main:
            await close_db()
        return # Cannot continue without DB connection

    # --- DB Reset Check (AFTER initial connection attempt) ---
    if config.RESET_DB_ON_START:
        if os.path.exists(config.DATABASE_FILE):
            logger.warning(f"RESET_DB_ON_START: Deleting existing DB file: {config.DATABASE_FILE}")
            try:
                await close_db() # Close the connection we just made
                db_connection_established_main = False # It's no longer valid
                os.remove(config.DATABASE_FILE)
                wal_file = f"{config.DATABASE_FILE}-wal"; shm_file = f"{config.DATABASE_FILE}-shm"
                if os.path.exists(wal_file): os.remove(wal_file)
                if os.path.exists(shm_file): os.remove(shm_file)
                # Re-establish connection and re-initialize schema
                logger.info("RESET_DB_ON_START: Re-establishing DB connection...")
                await connect_db()
                db_connection_established_main = True
                logger.info("RESET_DB_ON_START: Re-initializing schema...")
                await initialize_database()
                logger.info("RESET_DB_ON_START: Schema re-initialized.")
            except Exception as e:
                logger.critical(f"Failed during DB reset/re-init: {e}", exc_info=True)
                if db_connection_established_main: await close_db() # Try closing if re-connect worked
                return # Cannot continue
        else:
             logger.info(f"RESET_DB_ON_START: DB file not found ({config.DATABASE_FILE}), continuing.")

    # --- Application Build (AFTER DB connection is confirmed) ---
    logger.info("Building application...")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .defaults(defaults)
        .post_init(post_init) # Still used for scheduling
        .post_stop(post_stop) # Still used for closing DB
        .build()
    )
    logger.info("Application built.")

    # --- Register Handlers ---
    # (Handler registration remains the same)
    logger.info("Registering handlers...")
    try:
        application.add_handler(start.start_handler()); application.add_handler(start.help_handler())
        application.add_handler(add_habit.add_habit_conv_handler()); application.add_handler(manage_habits.delete_habit_conv_handler())
        application.add_handler(mark_done.mark_done_command_handler()); application.add_handler(mark_done.mark_done_button_handler())
        application.add_handler(view_habits.today_handler()); application.add_handler(view_habits.history_handler()); application.add_handler(view_habits.stats_handler())
        application.add_handler(reminders.set_reminder_conv_handler()); application.add_handler(reminders.manage_reminders_handler()); application.add_handler(reminders.delete_reminder_button_handler())
        application.add_error_handler(errors.error_handler)
        logger.info("Handlers registered successfully.")
    except Exception as e:
        logger.critical(f"!!! FAILED to register handlers: {e}", exc_info=True)
        await close_db() # Close DB if setup fails here
        return

    # --- Manual Bot Lifecycle Management ---
    stop_event = asyncio.Event()
    async def run_bot_until_stopped():
        nonlocal stop_event
        initialization_successful = False
        try:
            logger.info("Initializing application (runs post_init for jobs)...")
            await application.initialize() # post_init runs here
            initialization_successful = True
            logger.info("Application initialization completed.")

            logger.info("Starting updater polling...")
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            logger.info("Starting application handlers...")
            await application.start()

            logger.info("Bot is running. Waiting for stop signal...")
            await stop_event.wait()

            logger.info("Stop signal received. Initiating shutdown...")

        except Exception as e:
            logger.critical(f"Unhandled exception during bot startup/run: {e}", exc_info=True)
            stop_event.set()

        finally:
             logger.info("Entering shutdown phase...")
             # Use 'running' attribute for both application and updater
             if application.updater and application.updater.running:
                 logger.debug("Stopping updater...")
                 await application.updater.stop()
                 logger.debug("Updater stopped.")
             else:
                 logger.debug("Updater not running or not present.")

             if application.running:
                 logger.debug("Stopping application...")
                 await application.stop()
                 logger.debug("Application stopped.")
             else:
                 logger.debug("Application not running.")

             logger.debug("Shutting down application (runs post_stop)...")
             await application.shutdown() # Runs post_stop which closes global DB conn
             logger.debug("Application shutdown finished.")
             logger.info("run_bot_until_stopped finished.")


    # Setup Signal Handling
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
             loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
             logger.warning(f"Signal handler for {sig} not supported on this platform. Use Ctrl+C.")

    # Start the bot runner task
    await run_bot_until_stopped()


if __name__ == "__main__":
    logger.info("Script starting...")
    # ... (version logging) ...
    logger.info(f"Python version: {sys.version}")
    try:
        import telegram; import aiosqlite
        logger.info(f"python-telegram-bot version: {telegram.__version__}")
        logger.info(f"aiosqlite version: {aiosqlite.sqlite_version}")
        logger.info(f"aiosqlite library version: {aiosqlite.__version__}")
    except ImportError as e: logger.warning(f"Could not import library: {e}")

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal detected (main loop). Exiting.")
    except Exception as e:
         logger.critical(f"Unhandled exception in top-level asyncio.run: {e}", exc_info=True)
    finally:
         # Ensure DB is closed if main() fails before shutdown sequence completes
         if db_manager._db_connection: # Check internal variable directly (not ideal, but necessary here)
              logger.warning("Performing final DB close check in main script finally block.")
              # Need to run this async close in a new event loop if the main one is closing/closed
              try:
                   asyncio.run(close_db())
              except RuntimeError as re:
                   logger.error(f"Could not run final DB close: {re}") # e.g., loop already closed
         logger.info("Script finished.")