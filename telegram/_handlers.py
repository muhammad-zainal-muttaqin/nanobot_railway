"""Handler classes — PTB-compatible."""

from __future__ import annotations

from typing import Any, Callable

from telegram._types import Update


class BaseHandler:
    def check_update(self, update: Update) -> bool:
        raise NotImplementedError

    async def handle(self, update: Update, application: Any) -> None:
        raise NotImplementedError


class MessageHandler(BaseHandler):
    def __init__(self, _filter: Any, callback: Callable):
        self._filter = _filter
        self._callback = callback

    def check_update(self, update: Update) -> bool:
        message = update.effective_message
        if message is None:
            return False
        return bool(self._filter(message))

    async def handle(self, update: Update, application: Any) -> None:
        await self._callback(update, application)


class CallbackQueryHandler(BaseHandler):
    def __init__(self, callback: Callable):
        self._callback = callback

    def check_update(self, update: Update) -> bool:
        return update.callback_query is not None

    async def handle(self, update: Update, application: Any) -> None:
        await self._callback(update, application)
