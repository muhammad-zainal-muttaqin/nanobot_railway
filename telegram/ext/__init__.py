"""telegram.ext — PTB-compatible extension module.

Provides Application, MessageHandler, CallbackQueryHandler,
ContextTypes, and filters — all communicating directly with the
Telegram Bot API over HTTP instead of PTB.
"""

from telegram._application import Application
from telegram._handlers import BaseHandler, MessageHandler, CallbackQueryHandler
from telegram._context_types import CallbackContext, ContextTypes
from telegram._filters import filters

__all__ = [
    "Application",
    "BaseHandler",
    "MessageHandler",
    "CallbackQueryHandler",
    "CallbackContext",
    "ContextTypes",
    "filters",
]
