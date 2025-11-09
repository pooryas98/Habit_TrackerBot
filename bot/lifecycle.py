import logging
from telegram.ext import Application
from database.connection import close_db
from database.service import DatabaseService
from scheduling.reminder_scheduler import sched_all_rems
from handlers import register_all_handlers
from .error_handler import handle_error

log = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """
    Called by PTB after application initialization.

    - Ensures a shared DatabaseService is available in bot_data.
    - Registers all handlers.
    - Registers the central error handler.
    - Schedules all existing reminders.
    """
    log.info("post_init: start")

    # Ensure a DatabaseService is attached (using current global connection).
    # If get_db_connection fails, this will be caught by handlers on usage.
    try:
        if "db_service" not in app.bot_data:
            db_service = DatabaseService()
            app.bot_data["db_service"] = db_service
            log.info("post_init: DatabaseService attached to app.bot_data.")
    except Exception as e:
        log.critical(f"post_init: Failed attaching DatabaseService: {e}", exc_info=True)

    # Register all handlers once.
    try:
        register_all_handlers(app)
        log.info("post_init: handlers registered.")
    except Exception as e:
        log.critical(f"post_init: Failed registering handlers: {e}", exc_info=True)

    # Register central error handler.
    try:
        app.add_error_handler(handle_error)
        log.info("post_init: error handler registered.")
    except Exception as e:
        log.critical(f"post_init: Failed registering error handler: {e}", exc_info=True)

    # Schedule reminders using existing DB state, if possible.
    jq = app.job_queue
    if not jq:
        log.warning("post_init: JobQueue not found; skipping reminder scheduling.")
        return

    try:
        db_service: DatabaseService = app.bot_data.get("db_service") or DatabaseService()
        db_conn = await db_service.get_connection()
        await sched_all_rems(db_conn, jq)
        log.info("post_init: initial reminders scheduled.")
    except Exception as e:
        log.error(f"post_init: Failed to schedule reminders: {e}", exc_info=True)

    log.info("post_init: complete")


async def post_stop(app: Application) -> None:
    """
    Called by PTB when the application is shutting down.
    Ensures the shared DB connection is closed.
    """
    log.info("post_stop: Attempting DB close...")
    try:
        await close_db()
        log.info("post_stop: close_db() finished.")
    except Exception as e:
        log.error(f"post_stop: Error during close_db: {e}", exc_info=True)
    log.info("post_stop: handler finished.")