import logging,asyncio,config
from typing import Optional
from telegram import Update
from telegram.ext import Application, JobQueue
from database.connection import connect_db, close_db, get_db_connection
from scheduling.reminder_scheduler import sched_all_rems
from handlers import register_all_handlers
from .error_handler import handle_error

log = logging.getLogger(__name__)

async def post_init(app: Application) -> None:
	log.info("App initialized.")
	jq = app.job_queue
	if not jq: log.warning("! JobQueue NOT FOUND post init!")

async def post_stop(app: Application) -> None:
	log.info("post_stop: Attempting DB close...")
	try: await close_db(); log.info("post_stop: close_db() finished.")
	except Exception as e: log.error(f"Error in post_stop during close_db: {e}", exc_info=True)
	log.info("post_stop: handler finished.")

async def run_bot_lifecycle(app: Application) -> None:
	"""Manages bot start, run loop, and PTB shutdown via finally."""
	try:
		log.info("Connecting DB..."); await connect_db(); log.info("DB connected.")
		log.info("Initializing PTB app..."); await app.initialize(); log.info("PTB app initialized.") # Runs post_init
		log.info("Registering handlers..."); register_all_handlers(app); log.info("Handlers registered.")
		log.info("Registering error handler..."); app.add_error_handler(handle_error); log.info("Error handler registered.")

		log.info("Scheduling reminders...")
		jq = app.job_queue
		if jq:
			try: await sched_all_rems(await get_db_connection(), jq); log.info("Initial reminder sched done.")
			except ConnectionError: log.critical("DB unavailable for initial reminder sched. Skipped.")
			except Exception as e: log.error(f"Err initial reminder sched: {e}", exc_info=True)
		else: log.error("! JobQueue not found! Reminder sched skipped.")

		if app.updater:
			log.info("Starting polling..."); await app.updater.start_polling(allowed_updates=Update.ALL_TYPES); log.info("Polling started.")
		else: log.warning("Updater not avail, cannot poll.")

		await app.start()
		log.info(f"Bot running (TZ:{config.USER_TIMEZONE}). Press Ctrl+C to stop.")
		await asyncio.Future() # Wait indefinitely until cancelled
		log.info("asyncio.Future completed (unexpected).")

	except (KeyboardInterrupt, SystemExit, asyncio.CancelledError) as sig:
		log.warning(f"Lifecycle recv shutdown ({type(sig).__name__}). Entering finally...")
	except ConnectionError as e: log.critical(f"DB conn error during lifecycle: {e}", exc_info=True)
	except Exception as e: log.critical(f"Critical unexpected err in lifecycle: {e}", exc_info=True)

	finally:
		log.warning(">>> LIFECYCLE FINALLY START <<<")
		if app:
			log.info("PTB shutdown sequence initiated...")
			if app.updater and app.updater.running:
				log.info("Stopping updater...")
				try: await app.updater.stop(); log.info("Updater stopped.")
				except Exception as e: log.error(f"Err stopping updater: {e}", exc_info=True)
			if app.running:
				log.info("Stopping app (dispatcher/JQ)...")
				try: await app.stop(); log.info("App stopped.") # Includes JQ stop
				except Exception as e: log.error(f"Err stopping app: {e}", exc_info=True)
			log.info("Shutting down app (runs post_stop)...")
			try: await app.shutdown(); log.info("App shutdown complete.")
			except Exception as e: log.error(f"Err during app shutdown: {e}", exc_info=True)
			# Explicit post_stop call (keep as safeguard if shutdown unreliable)
			log.info("Attempting explicit post_stop call (safeguard)...")
			try: await post_stop(app); log.info("Explicit post_stop finished.")
			except Exception as e_ps: log.error(f"Error during explicit post_stop: {e_ps}", exc_info=True)
			log.info("PTB shutdown sequence finished.")
		else: log.warning("App obj None in finally, skipping PTB shutdown.")
		log.warning(">>> LIFECYCLE FINALLY END <<<")