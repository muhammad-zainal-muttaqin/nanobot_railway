"""Application — polling loop and handler dispatch for Telegram Bot API."""

from __future__ import annotations

import asyncio
import inspect
from contextlib import suppress
from typing import Any, Callable

from telegram._bot import Bot
from telegram._context_types import CallbackContext
from telegram._handlers import BaseHandler
from telegram.error import Conflict, NetworkError, TimedOut

_POLL_TIMEOUT = 30
_POLL_RETRY_DELAY = 3
_DEFAULT_LIMIT = 100
_V10_MESSAGE_UPDATES = ("business_message", "edited_business_message", "guest_message")


def _expand_allowed_updates(allowed_updates: list[str] | None) -> list[str] | None:
    if allowed_updates is None or "message" not in allowed_updates:
        return allowed_updates
    expanded = list(allowed_updates)
    for update_type in _V10_MESSAGE_UPDATES:
        if update_type not in expanded:
            expanded.append(update_type)
    return expanded


class Updater:
    """PTB-compatible updater facade; polling is managed by Application."""

    def __init__(self, application: "Application"):
        self._application = application

    async def start_polling(
        self,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        await self._application.start_polling(
            allowed_updates=allowed_updates,
            drop_pending_updates=drop_pending_updates,
            error_callback=error_callback,
        )

    async def stop(self) -> None:
        await self._application.stop()


class Application:
    """PTB-compatible Application with polling loop."""

    def __init__(self, bot: Bot, managed_clients: list[Any] | None = None):
        self.bot = bot
        self.updater = Updater(self)
        self._handlers: list[BaseHandler] = []
        self._error_handlers: list[Callable[[object, Any], None]] = []
        self._running = False
        self._polling_task: asyncio.Task | None = None
        self._managed_clients = managed_clients or []

    @classmethod
    def builder(cls) -> "ApplicationBuilder":
        return ApplicationBuilder()

    def add_handler(self, handler: BaseHandler) -> None:
        self._handlers.append(handler)

    def add_error_handler(self, callback: Callable[[object, Any], None]) -> None:
        self._error_handlers.append(callback)

    async def initialize(self) -> None:
        self._running = True

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._running = False
        await self._cancel_polling_task()

    async def shutdown(self) -> None:
        self._running = False
        await self._cancel_polling_task()
        await self.bot._close_client()
        await self._close_managed_clients()

    async def _cancel_polling_task(self) -> None:
        task = self._polling_task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._polling_task = None

    async def _close_managed_clients(self) -> None:
        closed: set[int] = set()
        for client in self._managed_clients:
            if client is None or id(client) in closed:
                continue
            close = getattr(client, "aclose", None)
            if close is None:
                continue
            closed.add(id(client))
            await close()

    async def process_update(self, update: Any) -> None:
        for handler in self._handlers:
            try:
                if handler.check_update(update):
                    ctx = CallbackContext(application=self)
                    await handler.handle(update, ctx)
                    return
            except Exception as e:
                await self._call_error_handlers(update, e)

    async def _call_error_handlers(self, update: object, error: Exception) -> None:
        for handler in self._error_handlers:
            try:
                ctx = CallbackContext(application=self, error=error)
                result = handler(update, ctx)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass

    async def start_polling(
        self,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        """Start the long-polling update loop as a background task."""
        self._error_callback = error_callback
        self._running = True
        allowed_updates = _expand_allowed_updates(allowed_updates)
        self._polling_task = asyncio.create_task(
            self._polling_loop(allowed_updates=allowed_updates,
                               drop_pending_updates=drop_pending_updates)
        )

    async def _polling_loop(
        self,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool = False,
    ) -> None:
        offset = 0

        if drop_pending_updates:
            try:
                await self.bot.get_updates(offset=-1, timeout=0)
            except Exception:
                pass

        while self._running:
            try:
                p: dict[str, Any] = {"timeout": _POLL_TIMEOUT, "limit": _DEFAULT_LIMIT}
                if offset is not None:
                    p["offset"] = offset
                if allowed_updates is not None:
                    p["allowed_updates"] = allowed_updates

                updates = await self.bot.get_updates(**p)

                for update in updates:
                    await self.process_update(update)
                    if self._running:
                        offset = update.update_id + 1

            except Conflict:
                await self._call_error_handlers(None, Conflict("Another poller/webhook instance"))
                await asyncio.sleep(_POLL_RETRY_DELAY)
            except (NetworkError, TimedOut):
                await asyncio.sleep(_POLL_RETRY_DELAY)
            except Exception as e:
                await self._call_error_handlers(None, e)
                await asyncio.sleep(_POLL_RETRY_DELAY)


class ApplicationBuilder:
    def __init__(self):
        self._token: str | None = None
        self._request: Any = None
        self._get_updates_request: Any = None

    def token(self, token: str) -> "ApplicationBuilder":
        self._token = token
        return self

    def request(self, request: Any) -> "ApplicationBuilder":
        self._request = request
        return self

    def get_updates_request(self, request: Any) -> "ApplicationBuilder":
        self._get_updates_request = request
        return self

    def build(self) -> Application:
        bot = Bot(token=self._token or "", request=self._request)
        managed_clients = [
            client
            for client in (self._request, self._get_updates_request)
            if client is not None
        ]
        return Application(bot, managed_clients=managed_clients)
