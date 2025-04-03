import logging, asyncio, os, signal, sys, aiosqlite
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, Defaults, JobQueue, Application
from telegram.constants import ParseMode
import config
from database import db_manager, initialize_database, connect_db, close_db, get_db_connection
from handlers import start, add_habit, mark_done, view_habits, reminders, manage_habits, errors, edit_habit
from utils.checks import require_membership
from utils import constants as c
from handlers.reminders import schedule_all_reminders

logger = logging.getLogger(__name__)

async def post_init(app: Application) -> None: logger.debug(f"post_init: JobQueue {'found' if app.job_queue else 'NOT FOUND'}")
async def post_stop(app: Application) -> None: logger.info("post_stop: Closing DB..."); await close_db(); logger.info("post_stop: DB closed.")

async def main() -> None:
    """Main entry point."""
    if config.RESET_DB_ON_START and os.path.exists(config.DATABASE_FILE):
        logger.warning(f"RESET_DB_ON_START: Deleting DB: {config.DATABASE_FILE}")
        try:
            for suffix in ["", "-wal", "-shm"]:
                fpath = f"{config.DATABASE_FILE}{suffix}"
                if os.path.exists(fpath): os.remove(fpath)
        except OSError as e: logger.error(f"Failed to delete DB files: {e}", exc_info=True)

    try:
        await initialize_database(); await connect_db()
    except (aiosqlite.Error, ConnectionError) as e:
        logger.critical(f"DB init/connection failed: {e}. Exiting.", exc_info=True); return

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=config.USER_TIMEZONE)
    app = ApplicationBuilder().token(config.BOT_TOKEN).defaults(defaults).post_init(post_init).post_stop(post_stop).build()
    logger.info("Application built.")

    try: # Register handlers
        # Decorate handlers requiring membership check
        dec_start = require_membership(start.start)
        dec_help = require_membership(start.help_command)
        dec_mark_done_cmd = require_membership(mark_done.mark_done_command)
        dec_show_today = require_membership(view_habits.show_today)
        dec_show_hist = require_membership(view_habits.show_history)
        dec_show_stats = require_membership(view_habits.show_stats)
        dec_list_reminders = require_membership(reminders.list_reminders)
        dec_mark_done_btn = require_membership(mark_done.mark_done_button_press)
        dec_mark_done_select = require_membership(mark_done.mark_done_select_habit_callback)
        dec_del_reminder_btn = require_membership(reminders.delete_reminder_button)

        # Conversations (decoration handled internally or via entry point)
        app.add_handler(add_habit.add_habit_conv_handler())
        app.add_handler(manage_habits.delete_habit_conv_handler())
        app.add_handler(reminders.set_reminder_conv_handler())
        app.add_handler(edit_habit.edit_habit_conv_handler())

        # Decorated Commands
        app.add_handler(CommandHandler(c.CMD_START, dec_start))
        app.add_handler(CommandHandler(c.CMD_HELP, dec_help))
        app.add_handler(CommandHandler(c.CMD_DONE, dec_mark_done_cmd))
        app.add_handler(CommandHandler(c.CMD_TODAY, dec_show_today))
        app.add_handler(CommandHandler(c.CMD_HISTORY, dec_show_hist))
        app.add_handler(CommandHandler(c.CMD_STATS, dec_show_stats))
        app.add_handler(CommandHandler(c.CMD_MANAGE_REMINDERS, dec_list_reminders))
        app.add_handler(CommandHandler(c.CMD_REFRESH_MEMBERSHIP, start.refresh_membership_command)) # No decorator needed

        # Decorated Callbacks
        app.add_handler(CallbackQueryHandler(dec_mark_done_btn, pattern=f"^{c.CALLBACK_MARK_DONE}"))
        app.add_handler(CallbackQueryHandler(dec_mark_done_select, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}"))
        app.add_handler(CallbackQueryHandler(dec_del_reminder_btn, pattern=f"^{c.CALLBACK_DELETE_REMINDER}"))
        app.add_handler(CallbackQueryHandler(view_habits.show_history_paginated, pattern=f"^{c.CALLBACK_HISTORY_PAGE}")) # No decorator

        app.add_error_handler(errors.error_handler) # Error Handler (last)
        logger.info("Handlers registered.")
    except Exception as e:
        logger.critical(f"FAILED to register handlers: {e}", exc_info=True); await close_db(); return

    # --- Bot Lifecycle ---
    stop_event = asyncio.Event()
    async def run_bot():
        try:
            logger.info("Initializing application...")
            await app.initialize() # Runs post_init
            logger.info("Scheduling reminders...")
            if jq := app.job_queue:
                try:
                    db_conn = await get_db_connection()
                    await schedule_all_reminders(db_conn, jq)
                except ConnectionError: logger.critical("DB UNAVAILABLE during reminder scheduling.")
                except Exception as e: logger.error(f"Reminder scheduling error: {e}", exc_info=True)
            else: logger.error("JobQueue NOT FOUND after init! Reminders skipped.")

            logger.info("Starting polling...")
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            await app.start()
            logger.info(f"Bot running ({config.USER_TIMEZONE}). Press Ctrl+C to stop.")
            await stop_event.wait() # Wait for signal
            logger.info("Stop signal received...")
        except Exception as e: logger.critical(f"Bot startup/run error: {e}", exc_info=True); stop_event.set()
        finally:
             logger.info("Shutting down...")
             if app.updater and app.updater.running: await app.updater.stop()
             if app.running: await app.stop()
             await app.shutdown() # Runs post_stop
             logger.info("run_bot finished.")

    # --- Signal Handling ---
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError: logger.warning(f"Signal {sig} not supported. Use Ctrl+C.")

    await run_bot()

if __name__ == "__main__":
    logger.info("Script starting...")
    logger.info(f"Python: {sys.version.split()[0]} | PTB: {getattr(__import__('telegram'), '__version__', 'N/A')} "
                f"| aiosqlite: {getattr(__import__('aiosqlite'), 'sqlite_version', 'N/A')} "
                f"({getattr(__import__('aiosqlite'), '__version__', 'N/A')})")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): logger.info("Shutdown via KeyboardInterrupt/SystemExit.")
    except Exception as e: logger.critical(f"Unhandled exception in asyncio.run: {e}", exc_info=True)
    finally:
         # Final DB close check
         if db_manager._db_connection:
              logger.warning("Final DB close check...")
              try: asyncio.run(close_db())
              except RuntimeError as re: logger.error(f"Final DB close failed: {re}.")
         logger.info("Script finished.")