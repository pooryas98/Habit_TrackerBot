import logging
import asyncio
import os
import sys
import aiosqlite
import telegram

from config import settings
from bot.application import create_application
from bot.lifecycle import post_init, post_stop
from database.connection import initialize_database, connect_db, close_db

logging.basicConfig(
    format="%(asctime)s - %(name)s[%(levelname)s] - %(message)s",
    level=getattr(logging, settings.log_level, logging.INFO),
)
log = logging.getLogger(__name__)


def main() -> None:
    log.info("Starting...")
    log.info(
        f"Python:{sys.version.split()[0]}, "
        f"PTB:{telegram.__version__}, "
        f"aiosqlite:{aiosqlite.__version__}(SQLite {aiosqlite.sqlite_version})"
    )

    if settings.reset_db_on_start and os.path.exists(settings.database_file):
        log.warning(f"RESET_DB=1. Deleting DB: {settings.database_file}")
        try:
            for suf in ["", "-wal", "-shm"]:
                fp = f"{settings.database_file}{suf}"
                if os.path.exists(fp):
                    os.remove(fp)
                    log.debug(f"Removed: {fp}")
        except OSError as e:
            log.error(f"Failed deleting DB files: {e}", exc_info=True)

    try:
        log.info("Initializing DB schema...")
        asyncio.run(initialize_database())
        log.info("DB schema initialized.")
    except (aiosqlite.Error, ConnectionError) as e:
        log.critical(f"DB init failed: {e}. Exit.", exc_info=True)
        return

    try:
        log.info("Connecting DB...")
        asyncio.run(connect_db())
        log.info("DB connected.")
    except ConnectionError as e:
        log.critical(f"DB connection failed after schema init: {e}. Exit.", exc_info=True)
        return

    try:
        log.info("Creating PTB app...")
        app = create_application()
        if not app:
            log.critical("Failed to create PTB app. Exit.")
            return
        log.info("PTB app created.")

        # Run polling using PTB's synchronous helper (controls its own loop).
        log.info("Starting bot with run_polling...")
        app.run_polling(allowed_updates=telegram.Update.ALL_TYPES)
        log.info("Bot run_polling completed.")
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutdown signal received in main.")
    except Exception as e:
        log.critical(f"Unhandled exception in main: {e}", exc_info=True)
    finally:
        # Ensure DB is closed; close_db is async, run it in a fresh loop.
        try:
            asyncio.run(close_db())
        except Exception as e:
            log.error(f"Error during final DB close: {e}", exc_info=True)
        log.info("Main cleanup finished.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        log.info("Script exit signaled (Interrupt/SystemExit).")
    except Exception as e:
        log.critical(f"Top-level critical error: {e}", exc_info=True)
    finally:
        log.info("Script execution finished.")