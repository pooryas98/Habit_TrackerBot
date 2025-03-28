# handlers/start.py

import logging
from telegram import Update
from telegram.ext import CommandHandler, CallbackContext

from utils import localization as lang
from utils import constants as c
from database import db_manager # Import db_manager module

logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message, registers user, and shows help."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return # Cannot proceed

    try:
        # Call db_manager function directly, it handles the connection
        await db_manager.add_user_if_not_exists(user.id)
        logger.info(f"User {user.id} ({user.username}) started the bot.")
        await message.reply_text(lang.MSG_WELCOME.format(user_name=user.first_name))
        await help_command(update, context) # Show help after welcome
    except ConnectionError: # Catch error if global connection is unavailable
        logger.error("Database connection unavailable for /start")
        await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error during /start for user {user.id}: {e}", exc_info=True)
        await message.reply_text(lang.MSG_ERROR_GENERAL)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Sends help message with available commands."""
    if update.effective_message:
        await update.effective_message.reply_text(lang.MSG_HELP, disable_web_page_preview=True)

def start_handler() -> CommandHandler:
    return CommandHandler(c.CMD_START, start)

def help_handler() -> CommandHandler:
     return CommandHandler(c.CMD_HELP, help_command)