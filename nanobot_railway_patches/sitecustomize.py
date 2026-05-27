"""Runtime patches for the Railway nanobot wrapper.

Python imports ``sitecustomize`` automatically when this directory is on
``PYTHONPATH``. The wrapper uses this hook to keep upstream ``nanobot-ai``
unvendored while adding Railway-specific Telegram behavior.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
import re
import sys
from pathlib import Path
from typing import Any


_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))


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
    chain_depth_re = re.compile(r"\s*\[nanobot:b2b-depth=(\d+)\]\s*", re.IGNORECASE)

    original_init = TelegramChannel.__init__
    original_is_allowed = TelegramChannel.is_allowed
    original_on_message = TelegramChannel._on_message
    original_forward_command = TelegramChannel._forward_command
    original_sender_id = TelegramChannel._sender_id
    original_build_metadata = TelegramChannel._build_message_metadata
    original_send = TelegramChannel.send
    original_send_delta = TelegramChannel.send_delta

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
        self._bot_to_bot_seen_messages = set()
        self._bot_to_bot_seen_message_order = deque()
        self._bot_to_bot_depth_by_chat = {}
        self._bot_to_bot_marked_streams = set()

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

    def _bot_allow_tokens(user_id: Any, username: Any = None) -> set[str]:
        user_id_text = str(user_id).strip()
        username_text = str(username or "").strip().removeprefix("@")
        tokens = {user_id_text.lower()} if user_id_text else set()
        if username_text:
            username_lower = username_text.lower()
            tokens.update({
                username_lower,
                f"@{username_lower}",
            })
            if user_id_text:
                tokens.update({
                    f"bot:{user_id_text.lower()}|{username_lower}",
                    f"bot:{user_id_text.lower()}|@{username_lower}",
                })
        if user_id_text:
            tokens.add(f"bot:{user_id_text.lower()}")
        return tokens

    def _configured_bot_allowlist(self: Any) -> set[str]:
        raw_allow = _config_value(self.config, "bot_to_bot_allow_bots", default=[]) or []
        if isinstance(raw_allow, str):
            raw_values = [part.strip() for part in raw_allow.split(",")]
        else:
            raw_values = [str(value).strip() for value in raw_allow]
        tokens: set[str] = set()
        for value in raw_values:
            if not value:
                continue
            lowered = value.lower()
            tokens.add(lowered)
            if lowered.startswith("@"):
                tokens.add(lowered.removeprefix("@"))
            elif lowered.startswith("bot:"):
                raw_identity = lowered.removeprefix("bot:")
                user_id, sep, username = raw_identity.partition("|")
                if user_id:
                    tokens.add(user_id)
                    tokens.add(f"bot:{user_id}")
                if sep and username:
                    username = username.removeprefix("@")
                    tokens.update({username, f"@{username}", f"bot:{user_id}|{username}"})
            else:
                tokens.add(f"@{lowered}")
        return tokens

    def patched_build_metadata(message: Any, user: Any) -> dict:
        meta = original_build_metadata(message, user)
        meta["is_bot"] = bool(getattr(user, "is_bot", False))
        if getattr(user, "username", None):
            meta["sender_username"] = user.username
        if hasattr(message, "_bot_to_bot_chain_depth"):
            meta["bot_to_bot_chain_depth"] = getattr(message, "_bot_to_bot_chain_depth")
        if getattr(user, "is_bot", False) and getattr(message, "message_id", None) is not None:
            meta["origin_message_id"] = str(message.message_id)
        return meta

    def _bot_allowed(self: Any, user: Any) -> bool:
        allow = _config_value(self.config, "bot_to_bot_allow_bots", default=[]) or []
        if not allow or "*" in allow:
            return True
        allowed = _configured_bot_allowlist(self)
        return bool(_bot_allow_tokens(getattr(user, "id", ""), getattr(user, "username", None)) & allowed)

    def _bot_sender_allowed_by_id(self: Any, sender_id: Any) -> bool:
        allow = _config_value(self.config, "bot_to_bot_allow_bots", default=[]) or []
        if not _config_value(self.config, "bot_to_bot", default=False):
            return False
        if not allow or "*" in allow:
            return True
        user_id, username = _bot_identity_from_sender_id(sender_id)
        return bool(_bot_allow_tokens(user_id, username) & _configured_bot_allowlist(self))

    def _ensure_legacy_message(update: Any) -> Any:
        if getattr(update, "message", None) is not None:
            return update
        effective = getattr(update, "effective_message", None)
        if effective is None:
            return update
        try:
            object.__setattr__(update, "message", effective)
        except Exception:
            try:
                setattr(update, "message", effective)
            except Exception:
                pass
        return update

    def _apply_chain_depth_marker(message: Any) -> int:
        depth = 0
        for field_name in ("text", "caption"):
            value = getattr(message, field_name, None)
            if not isinstance(value, str):
                continue
            match = chain_depth_re.search(value)
            if not match:
                continue
            depth = max(depth, int(match.group(1)))
            cleaned = chain_depth_re.sub(" ", value).strip()
            try:
                object.__setattr__(message, field_name, cleaned)
            except Exception:
                try:
                    setattr(message, field_name, cleaned)
                except Exception:
                    pass
        try:
            object.__setattr__(message, "_bot_to_bot_chain_depth", depth)
        except Exception:
            try:
                setattr(message, "_bot_to_bot_chain_depth", depth)
            except Exception:
                pass
        return depth

    def _chain_depth_exceeded(self: Any, message: Any) -> bool:
        depth = _apply_chain_depth_marker(message)
        max_depth = int(_config_value(self.config, "bot_to_bot_max_chain_depth", default=6) or 6)
        return max_depth > 0 and depth >= max_depth

    def _bot_message_duplicate(self: Any, update: Any, message: Any, user: Any) -> bool:
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", getattr(message, "chat_id", None))
        message_id = getattr(message, "message_id", None)
        thread_id = getattr(message, "message_thread_id", None)
        update_id = getattr(update, "update_id", None)
        if message_id is None:
            key = ("update", update_id, getattr(user, "id", None))
        else:
            key = ("message", chat_id, thread_id, message_id, getattr(user, "id", None))
        seen = getattr(self, "_bot_to_bot_seen_messages", set())
        order = getattr(self, "_bot_to_bot_seen_message_order", deque())
        if key in seen:
            return True
        seen.add(key)
        order.append(key)
        while len(order) > 1000:
            old = order.popleft()
            seen.discard(old)
        self._bot_to_bot_seen_messages = seen
        self._bot_to_bot_seen_message_order = order
        return False

    def _remember_bot_reply_depth(self: Any, message: Any) -> None:
        chat_id = str(getattr(message, "chat_id", getattr(getattr(message, "chat", None), "id", "")))
        if not chat_id:
            return
        depth = int(getattr(message, "_bot_to_bot_chain_depth", 0) or 0)
        origin_id = getattr(message, "message_id", None)
        by_chat = getattr(self, "_bot_to_bot_depth_by_chat", {})
        by_chat[chat_id] = (depth, time.monotonic())
        if origin_id is not None:
            by_chat[f"{chat_id}:{origin_id}"] = (depth, time.monotonic())
        for key, (_, seen_at) in list(by_chat.items()):
            if time.monotonic() - seen_at > 300:
                by_chat.pop(key, None)
        self._bot_to_bot_depth_by_chat = by_chat

    def _reply_depth_for_metadata(self: Any, chat_id: Any, metadata: dict[str, Any]) -> int | None:
        if not _config_value(self.config, "bot_to_bot", default=False):
            return None
        if "bot_to_bot_chain_depth" in metadata:
            try:
                return int(metadata["bot_to_bot_chain_depth"]) + 1
            except (TypeError, ValueError):
                return None
        depth_map = getattr(self, "_bot_to_bot_depth_by_chat", {})
        origin = metadata.get("origin_message_id") or metadata.get("message_id")
        keys = []
        if origin is not None:
            keys.append(f"{chat_id}:{origin}")
        keys.append(str(chat_id))
        for key in keys:
            if key in depth_map:
                depth, _ = depth_map[key]
                return int(depth) + 1
        return None

    def _prefix_bot_depth(text: str, depth: int | None) -> str:
        if depth is None:
            return text
        if chain_depth_re.search(text):
            return text
        return f"[nanobot:b2b-depth={depth}] {text}"

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
        update = _ensure_legacy_message(update)
        user = getattr(update, "effective_user", None)
        if user is not None and getattr(user, "is_bot", False):
            message = getattr(update, "message", None)
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
            if message is not None and _bot_message_duplicate(self, update, message, user):
                self.logger.debug("bot-to-bot sender @{} duplicate message ignored", getattr(user, "username", None))
                return
            if message is not None and _chain_depth_exceeded(self, message):
                self.logger.warning("bot-to-bot sender @{} exceeded max chain depth", getattr(user, "username", None))
                return
            if message is not None:
                _remember_bot_reply_depth(self, message)
        await original_on_message(self, update, context)

    async def patched_forward_command(self, update: Any, context: Any) -> None:
        update = _ensure_legacy_message(update)
        user = getattr(update, "effective_user", None)
        if user is not None and getattr(user, "is_bot", False):
            message = getattr(update, "message", None)
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
            if message is not None and _bot_message_duplicate(self, update, message, user):
                self.logger.debug(
                    "bot-to-bot command sender @{} duplicate message ignored",
                    getattr(user, "username", None),
                )
                return
            if message is not None and _chain_depth_exceeded(self, message):
                self.logger.warning(
                    "bot-to-bot command sender @{} exceeded max chain depth",
                    getattr(user, "username", None),
                )
                return
            if message is not None:
                _remember_bot_reply_depth(self, message)
        await original_forward_command(self, update, context)

    async def patched_send(self: Any, msg: Any) -> None:
        metadata = dict(getattr(msg, "metadata", {}) or {})
        chat_id_raw = getattr(msg, "chat_id", "")
        depth = _reply_depth_for_metadata(self, chat_id_raw, metadata)
        content = getattr(msg, "content", "")
        if depth is not None and isinstance(content, str) and content and content != "[empty message]":
            try:
                from dataclasses import replace

                msg = replace(msg, content=_prefix_bot_depth(content, depth), metadata=metadata)
            except Exception:
                msg.content = _prefix_bot_depth(content, depth)
                msg.metadata = metadata
            content = getattr(msg, "content", content)
        chat_id_str = str(chat_id_raw).strip()
        if chat_id_str.startswith("@"):
            # Bot API 10 allows private bot-to-bot delivery via @username chat_id,
            # but upstream TelegramChannel.send casts chat_id to int unconditionally.
            # Route through the native Bot.send_message which accepts string chat_ids.
            kwargs: dict[str, Any] = {"chat_id": chat_id_str, "text": content}
            parse_mode = getattr(msg, "parse_mode", None) or metadata.get("parse_mode")
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            await self.bot.send_message(**kwargs)
            return
        await original_send(self, msg)

    async def patched_send_delta(
        self: Any,
        chat_id: str,
        delta: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = dict(metadata or {})
        depth = _reply_depth_for_metadata(self, chat_id, metadata)
        stream_key = metadata.get("_stream_id") or f"{chat_id}:{metadata.get('origin_message_id') or metadata.get('message_id')}"
        marked = getattr(self, "_bot_to_bot_marked_streams", set())
        if (
            depth is not None
            and delta
            and not metadata.get("_stream_end")
            and stream_key not in marked
        ):
            delta = _prefix_bot_depth(delta, depth)
            marked.add(stream_key)
            if len(marked) > 1000:
                marked = set(list(marked)[-500:])
            self._bot_to_bot_marked_streams = marked
        await original_send_delta(self, chat_id, delta, metadata)

    TelegramChannel.__init__ = patched_init
    TelegramChannel.is_allowed = patched_is_allowed
    TelegramChannel._sender_id = staticmethod(patched_sender_id)
    TelegramChannel._build_message_metadata = staticmethod(patched_build_metadata)
    TelegramChannel._on_message = patched_on_message
    TelegramChannel._forward_command = patched_forward_command
    TelegramChannel.send = patched_send
    TelegramChannel.send_delta = patched_send_delta
    setattr(TelegramChannel, "_railway_bot_to_bot_patched", True)


_patch_telegram_channel()
