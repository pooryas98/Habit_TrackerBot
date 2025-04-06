import logging, asyncio, os, sys, aiosqlite, telegram, config
from bot.application import create_application
from bot.lifecycle import run_bot_lifecycle
from database.connection import initialize_database, close_db, _db as db_conn

logging.basicConfig(format="%(asctime)s - %(name)s[%(levelname)s] - %(message)s", level=getattr(logging, config.LOG_LEVEL, logging.INFO))
log = logging.getLogger(__name__)

async def main() -> None:
	log.info("Starting...")
	log.info(f"Python:{sys.version.split()[0]}, PTB:{telegram.__version__}, aiosqlite:{aiosqlite.__version__}(SQLite {aiosqlite.sqlite_version})")
	if config.RESET_DB and os.path.exists(config.DB_FILE):
		log.warning(f"RESET_DB=1. Deleting DB: {config.DB_FILE}")
		try:
			for suf in ["","-wal","-shm"]:
				fp=f"{config.DB_FILE}{suf}"
				if os.path.exists(fp): os.remove(fp); log.debug(f"Removed: {fp}")
		except OSError as e: log.error(f"Failed deleting DB files: {e}", exc_info=True)
	try:
		log.info("Initializing DB schema...")
		await initialize_database(); log.info("DB schema initialized.")
	except (aiosqlite.Error, ConnectionError) as e: log.critical(f"DB init failed: {e}. Exit.", exc_info=True); return

	app = None
	try:
		log.info("Creating PTB app...")
		app = create_application()
		if not app: log.critical("Failed create PTB app. Exit."); return
		log.info("PTB app created.")

		log.info("Starting bot lifecycle...")
		await run_bot_lifecycle(app) # Handles its own PTB shutdown and DB close
		log.info("Bot lifecycle finished (unexpected unless error before interrupt).")

	except (KeyboardInterrupt, SystemExit) as sig:
		log.warning(f"Main caught signal ({type(sig).__name__}). Lifecycle finally should handle cleanup.")
	except Exception as e:
		log.critical(f"Unhandled exception escaping lifecycle/setup: {e}", exc_info=True)

	finally:
		log.info("Main finally: Final checks...")
		# Reduced final check as lifecycle/connection should handle DB closing
		global db_conn
		db_check = db_conn
		if db_check is not None and not getattr(db_check, '_closed', True):
			log.warning("Final check: DB conn still open! Lifecycle/connection cleanup might have failed.")
			# Maybe attempt close again, but risk conflicts if close_db is running elsewhere
			# try:
			#     log.warning("Attempting manual final close_db() again...")
			#     await close_db()
			#     log.info("Manual final close_db() completed.")
			# except Exception as e_close:
			#     log.error(f"Error during manual final close_db(): {e_close}", exc_info=True)
		else:
			log.debug("Final check: DB conn None or closed (expected).")
		log.info("Main finally finished.")

if __name__ == "__main__":
	try:
		asyncio.run(main())
	except (KeyboardInterrupt, SystemExit):
		log.info("Script exit signaled (Interrupt/SystemExit).")
	except Exception as e:
		log.critical(f"Top-level critical error: {e}", exc_info=True)
	finally:
		log.info("Script execution finished.")