"""Runtime patches for the Railway nanobot wrapper.

Python imports ``sitecustomize`` automatically when this directory is on
``PYTHONPATH``. The wrapper uses this hook to keep upstream ``nanobot-ai``
unvendored while adding Railway-specific Telegram behavior.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
import re
from typing import Any


def _patch_telegram_channel() -> None:
    try:
        from nanobot.channels.telegram import TelegramChannel
    except Exception:
        return

    if getattr(TelegramChannel, "_railway_bot_to_bot_patched", False):
        return

    TelegramChannel.TELEGRAM_BUS_SLASH_COMMAND_RE = re.compile(
        r"^/(?!start(?:@\w+)?(?:\s|$)|help(?:@\w+)?(?:\s|$))"
        r"[A-Za-z0-9_]+(?:@\w+)?(?:\s+.*)?$"
    )

    original_init = TelegramChannel.__init__
    original_is_allowed = TelegramChannel.is_allowed
    original_on_message = TelegramChannel._on_message
    original_forward_command = TelegramChannel._forward_command
    original_sender_id = TelegramChannel._sender_id
    original_build_metadata = TelegramChannel._build_message_metadata

    def _config_value(config: Any, *names: str, default: Any = None) -> Any:
        for name in names:
            if isinstance(config, dict) and name in config:
                return config[name]
            if hasattr(config, name):
                return getattr(config, name)
        return default

    def patched_init(self, config: Any, bus: Any) -> None:
        raw = dict(config) if isinstance(config, dict) else {}
        original_init(self, config, bus)
        bot_to_bot = raw.get("botToBot", raw.get("bot_to_bot", False))
        max_per_minute = raw.get("botToBotMaxPerMinute", raw.get("bot_to_bot_max_per_minute", 12))
        max_chain_depth = raw.get("botToBotMaxChainDepth", raw.get("bot_to_bot_max_chain_depth", 6))
        allow_bots = raw.get("botToBotAllowBots", raw.get("bot_to_bot_allow_bots", []))
        object.__setattr__(self.config, "bot_to_bot", bool(bot_to_bot))
        object.__setattr__(self.config, "bot_to_bot_max_per_minute", int(max_per_minute or 12))
        object.__setattr__(self.config, "bot_to_bot_max_chain_depth", int(max_chain_depth or 6))
        object.__setattr__(self.config, "bot_to_bot_allow_bots", list(allow_bots or []))
        self._bot_to_bot_seen = defaultdict(deque)

    def patched_sender_id(user: Any) -> str:
        sender = original_sender_id(user)
        if getattr(user, "is_bot", False):
            return f"bot:{sender}"
        return sender

    def _is_bot_sender_id(sender_id: Any) -> bool:
        return str(sender_id).startswith("bot:")

    def _bot_identity_from_sender_id(sender_id: Any) -> tuple[str, str | None]:
        raw = str(sender_id).removeprefix("bot:")
        user_id, sep, username = raw.partition("|")
        return user_id, username if sep and username else None

    def patched_build_metadata(message: Any, user: Any) -> dict:
        meta = original_build_metadata(message, user)
        meta["is_bot"] = bool(getattr(user, "is_bot", False))
        if getattr(user, "username", None):
            meta["sender_username"] = user.username
        return meta

    def _bot_allowed(self: Any, user: Any) -> bool:
        allow = _config_value(self.config, "bot_to_bot_allow_bots", default=[]) or []
        if not allow or "*" in allow:
            return True
        user_id = str(getattr(user, "id", ""))
        username = getattr(user, "username", None)
        return bool(user_id in allow or (username and username in allow) or (
            username and f"@{username}".lower() in {str(v).lower() for v in allow}
        ))

    def _bot_sender_allowed_by_id(self: Any, sender_id: Any) -> bool:
        allow = _config_value(self.config, "bot_to_bot_allow_bots", default=[]) or []
        if not _config_value(self.config, "bot_to_bot", default=False):
            return False
        if not allow or "*" in allow:
            return True
        user_id, username = _bot_identity_from_sender_id(sender_id)
        normalized = {str(v).lower() for v in allow}
        return bool(
            user_id in allow
            or (username and username.lower() in normalized)
            or (username and f"@{username}".lower() in normalized)
            or str(sender_id).lower() in normalized
        )

    def patched_is_allowed(self: Any, sender_id: str) -> bool:
        if _is_bot_sender_id(sender_id):
            if _bot_sender_allowed_by_id(self, sender_id):
                return True
            self.logger.debug("bot-to-bot sender {} denied by botToBotAllowBots", sender_id)
            return False
        return original_is_allowed(self, sender_id)

    def _rate_limited(self: Any, user: Any) -> bool:
        max_per_minute = int(_config_value(self.config, "bot_to_bot_max_per_minute", default=12) or 12)
        if max_per_minute <= 0:
            return True
        now = time.monotonic()
        key = str(getattr(user, "id", "unknown"))
        seen = self._bot_to_bot_seen[key]
        while seen and now - seen[0] > 60:
            seen.popleft()
        if len(seen) >= max_per_minute:
            return True
        seen.append(now)
        return False

    async def patched_on_message(self, update: Any, context: Any) -> None:
        user = getattr(update, "effective_user", None)
        if user is not None and getattr(user, "is_bot", False):
            bot_id, _ = await self._ensure_bot_identity()
            if bot_id and getattr(user, "id", None) == bot_id:
                return
            if not _config_value(self.config, "bot_to_bot", default=False):
                self.logger.debug("bot-to-bot message ignored because botToBot is disabled")
                return
            if not _bot_allowed(self, user):
                self.logger.warning("bot-to-bot sender @{} is not allowed", getattr(user, "username", None))
                return
            if _rate_limited(self, user):
                self.logger.warning("bot-to-bot sender @{} rate limited", getattr(user, "username", None))
                return
        await original_on_message(self, update, context)

    async def patched_forward_command(self, update: Any, context: Any) -> None:
        user = getattr(update, "effective_user", None)
        if user is not None and getattr(user, "is_bot", False):
            bot_id, _ = await self._ensure_bot_identity()
            if bot_id and getattr(user, "id", None) == bot_id:
                return
            if not _config_value(self.config, "bot_to_bot", default=False):
                self.logger.debug("bot-to-bot command ignored because botToBot is disabled")
                return
            if not _bot_allowed(self, user):
                self.logger.warning("bot-to-bot command sender @{} is not allowed", getattr(user, "username", None))
                return
            if _rate_limited(self, user):
                self.logger.warning("bot-to-bot command sender @{} rate limited", getattr(user, "username", None))
                return
        await original_forward_command(self, update, context)

    TelegramChannel.__init__ = patched_init
    TelegramChannel.is_allowed = patched_is_allowed
    TelegramChannel._sender_id = staticmethod(patched_sender_id)
    TelegramChannel._build_message_metadata = staticmethod(patched_build_metadata)
    TelegramChannel._on_message = patched_on_message
    TelegramChannel._forward_command = patched_forward_command
    setattr(TelegramChannel, "_railway_bot_to_bot_patched", True)


_patch_telegram_channel()
