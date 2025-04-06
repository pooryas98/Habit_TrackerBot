# handlers/base.py
# This file can contain base classes, common context clearing functions,
# or other utilities shared specifically among handlers if needed later.
# For now, it can remain empty.

# Example of a potential shared function:
# from telegram.ext import CallbackContext
# def clear_conversation_context(context: CallbackContext, keys: list[str]):
#     """Removes specified keys from user_data."""
#     for key in keys:
#         context.user_data.pop(key, None)