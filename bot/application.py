import logging,config
from telegram.ext import ApplicationBuilder,Defaults,Application
from telegram.constants import ParseMode
from .lifecycle import post_init,post_stop

log=logging.getLogger(__name__)

def create_application()->Application:
	"""Builds and configures the PTB Application."""
	log.debug("Creating PTB App...")
	defaults=Defaults(parse_mode=ParseMode.HTML,tzinfo=config.USER_TIMEZONE)
	builder=ApplicationBuilder().token(config.BOT_TOKEN).defaults(defaults)
	builder.post_init(post_init).post_stop(post_stop)
	app=builder.build()
	log.info("PTB App built.")
	return app