from telegram.ext import Application
from .common.start_help import register_start_help_handlers
from .common.membership import register_membership_handlers
from .habits.add import register_add_habit_handlers
from .habits.edit import register_edit_habit_handlers
from .habits.delete import register_delete_habit_handlers
from .tracking.mark_done import register_mark_done_handlers
from .tracking.view import register_view_handlers
from .reminders.manage import register_reminder_management_handlers

def register_all_handlers(app:Application)->None:
	"""Registers all command, callback, and conversation handlers."""
	register_start_help_handlers(app)
	register_membership_handlers(app)
	register_add_habit_handlers(app)
	register_edit_habit_handlers(app)
	register_delete_habit_handlers(app)
	register_mark_done_handlers(app)
	register_view_handlers(app)
	register_reminder_management_handlers(app)