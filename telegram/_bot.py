"""Telegram Bot v10 API — thin HTTP client to api.telegram.org."""

from __future__ import annotations

import contextvars
import re
from pathlib import Path
from typing import Any

import httpx

from telegram.error import NetworkError, TimedOut, raise_for_status
from telegram._types import (
    BotCommand,
    BotCommandScopeDefault,
    BusinessConnection,
    ChatAdministratorRights,
    ChatFullInfo,
    ChatInviteLink,
    ChatMember,
    ChatPermissions,
    File,
    ForumTopic,
    GameHighScore,
    Gifts,
    InlineKeyboardMarkup,
    InputMedia,
    MenuButton,
    Message,
    Poll,
    ReactionTypeEmoji,
    ReplyParameters,
    SentGuestMessage,
    StarTransactions,
    Sticker,
    StickerSet,
    Update,
    User,
    WebhookInfo,
)

_BOT_INSTANCE: contextvars.ContextVar["Bot | None"] = contextvars.ContextVar("_BOT_INSTANCE", default=None)


def _redact_token(text: object, token: str) -> str:
    value = str(text)
    if token:
        value = value.replace(token, "<redacted-token>")
    return re.sub(r"/bot[^/\s]+/", "/bot<redacted-token>/", value)


def _parse_update(data: dict) -> Update:
    """Parse a raw JSON dict into an Update dataclass."""
    return _parse_obj(Update, data)


def _parse_obj(cls: type, data: Any) -> Any:
    """Recursively parse JSON into dataclasses."""
    if data is None:
        return None
    if cls in (int, float, str, bool):
        return data
    if isinstance(data, list):
        inner = getattr(cls, "__args__", [dict])[0] if hasattr(cls, "__args__") else dict
        return [_parse_field(inner, item) for item in data]

    if isinstance(data, dict):
        import typing as _ty
        hints = _ty.get_type_hints(cls)
        annotations = getattr(cls, "__dataclass_fields__", {})
        parsed = {}
        for key, value in data.items():
            py_key = key
            if key == "from":
                py_key = "from_user"
            if py_key not in annotations:
                continue
            target_type = hints.get(py_key, annotations[py_key].type)
            parsed[py_key] = _parse_field(target_type, value)
        return cls(**parsed)

    return data


def _parse_field(target_type: Any, value: Any) -> Any:
    """Parse a single field value, handling Union/Optional and generics."""
    import typing as _ty

    if value is None:
        return None

    origin = _ty.get_origin(target_type)
    args = _ty.get_args(target_type)

    # Handle Union[X, None] or X | None — unwrap to the non-None type
    if origin is _ty.Union:
        non_none = [a for a in args if a is not type(None)]  # noqa: E721
        if non_none:
            value = _parse_field(non_none[0], value)
            return value
        return value

    # Handle UnionType (X | None syntax)
    import types as _tmod
    if origin is _tmod.UnionType or origin is type.__class__:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _parse_field(non_none[0], value)
        return value

    # Handle list[X]
    if origin is list and isinstance(value, list):
        inner = args[0] if args else dict
        return [_parse_field(inner, item) for item in value]

    # Plain scalar types
    if isinstance(value, (str, int, float, bool)):
        return value

    # Dict that maps to a known dataclass type
    if isinstance(value, dict):
        resolved = target_type
        resolved_origin = _ty.get_origin(resolved)
        resolved_args = _ty.get_args(resolved)
        if resolved_origin is _ty.Union or resolved_origin is _tmod.UnionType:
            non_none = [a for a in resolved_args if a is not type(None)]
            resolved = non_none[0] if non_none else resolved
        if isinstance(resolved, type) and hasattr(resolved, "__dataclass_fields__"):
            return _parse_obj(resolved, value)
        try:
            from telegram._types import TelegramObject

            if isinstance(resolved, type) and issubclass(resolved, TelegramObject):
                return resolved(**value)
        except Exception:
            pass
        return value

    return value


class Bot:
    """Direct HTTP client for the Telegram Bot API v10."""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    FILE_URL = "https://api.telegram.org/file/bot{token}/"

    def __init__(self, token: str, request: httpx.AsyncClient | None = None):
        self.token = token
        self._client = request or httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=15.0))
        self._owns_client = request is None
        _BOT_INSTANCE.set(self)

    async def _close_client(self) -> None:
        """Close the underlying HTTP client (renamed to avoid Bot API close() conflict)."""
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        url = self.BASE_URL.format(token=self.token, method=method)
        try:
            if files:
                data = {}
                if params:
                    for k, v in params.items():
                        if v is not None:
                            data[k] = _serialize_form_value(v)
                resp = await self._client.post(url, data=data, files=files)
            else:
                body = {}
                if params:
                    for k, v in params.items():
                        if v is not None:
                            body[k] = _serialize(v)
                resp = await self._client.post(url, json=body)
        except httpx.TimeoutException as e:
            raise TimedOut(_redact_token(e, self.token)) from e
        except httpx.RequestError as e:
            raise NetworkError(_redact_token(e, self.token)) from e

        try:
            data = resp.json()
        except Exception as e:
            body = _redact_token(getattr(resp, "text", "")[:500], self.token)
            raise NetworkError(f"Invalid JSON from Telegram API {method}: {body}") from e

        if not isinstance(data, dict):
            raise NetworkError(f"Invalid Telegram API envelope for {method}")

        if not data.get("ok"):
            raise_for_status(
                resp.status_code,
                _redact_token(data.get("description", ""), self.token),
                data.get("parameters"),
            )
        if "result" not in data:
            raise NetworkError(f"Telegram API response for {method} is missing result")
        return data["result"]

    # ═══════════════════════════════════════════
    # Getting updates
    # ═══════════════════════════════════════════

    async def get_updates(
        self, offset: int | None = None, limit: int | None = None,
        timeout: int | None = None, allowed_updates: list[str] | None = None,
    ) -> list[Update]:
        data = await self._request("getUpdates", {
            "offset": offset, "limit": limit, "timeout": timeout,
            "allowed_updates": allowed_updates,
        })
        return [_parse_update(item) for item in data]

    async def set_webhook(
        self, url: str,
        certificate: bytes | None = None,
        ip_address: str | None = None,
        max_connections: int | None = None,
        allowed_updates: list[str] | None = None,
        drop_pending_updates: bool | None = None,
        secret_token: str | None = None,
    ) -> bool:
        p: dict[str, Any] = {
            "url": url, "ip_address": ip_address,
            "max_connections": max_connections,
            "allowed_updates": allowed_updates,
            "drop_pending_updates": drop_pending_updates,
            "secret_token": secret_token,
        }
        files = None
        if certificate is not None:
            files = {"certificate": ("cert.pem", certificate, "application/x-pem-file")}
        return bool(await self._request("setWebhook", p, files=files))

    async def delete_webhook(self, drop_pending_updates: bool | None = None) -> bool:
        return bool(await self._request("deleteWebhook", {"drop_pending_updates": drop_pending_updates}))

    async def get_webhook_info(self) -> WebhookInfo:
        return _parse_field(WebhookInfo, await self._request("getWebhookInfo"))

    # ═══════════════════════════════════════════
    # Available methods — Bot identity
    # ═══════════════════════════════════════════

    async def get_me(self) -> User:
        return _parse_field(User, await self._request("getMe"))

    async def log_out(self) -> bool:
        return bool(await self._request("logOut"))

    async def close(self) -> bool:
        return bool(await self._request("close"))

    # ═══════════════════════════════════════════
    # Messages — send
    # ═══════════════════════════════════════════

    async def send_message(
        self, chat_id: int | str, text: str,
        parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        link_preview_options: dict | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        allow_paid_broadcast: bool | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "text": text,
            "parse_mode": parse_mode, "message_thread_id": message_thread_id,
            "link_preview_options": link_preview_options,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendMessage", p))

    async def send_photo(
        self, chat_id: int | str, photo: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        has_spoiler: bool | None = None,
        show_caption_above_media: bool | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendPhoto", "photo", chat_id, photo,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      has_spoiler=has_spoiler,
                                      show_caption_above_media=show_caption_above_media,
                                      filename=filename, **kwargs)

    async def send_video(
        self, chat_id: int | str, video: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        supports_streaming: bool | None = None,
        has_spoiler: bool | None = None,
        show_caption_above_media: bool | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendVideo", "video", chat_id, video,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      supports_streaming=supports_streaming,
                                      has_spoiler=has_spoiler,
                                      show_caption_above_media=show_caption_above_media,
                                      filename=filename, **kwargs)

    async def send_voice(
        self, chat_id: int | str, voice: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendVoice", "voice", chat_id, voice,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      filename=filename, **kwargs)

    async def send_audio(
        self, chat_id: int | str, audio: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendAudio", "audio", chat_id, audio,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      filename=filename, **kwargs)

    async def send_document(
        self, chat_id: int | str, document: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        disable_content_type_detection: bool | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendDocument", "document", chat_id, document,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      disable_content_type_detection=disable_content_type_detection,
                                      filename=filename, **kwargs)

    async def send_sticker(
        self, chat_id: int | str, sticker: str | bytes | Path,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendSticker", "sticker", chat_id, sticker,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      filename=filename, **kwargs)

    async def send_video_note(
        self, chat_id: int | str, video_note: str | bytes | Path,
        duration: int | None = None, length: int | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "duration": duration, "length": length,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return await self._send_media("sendVideoNote", "video_note", chat_id, video_note,
                                      filename=filename, extra_params=p)

    async def send_animation(
        self, chat_id: int | str, animation: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        has_spoiler: bool | None = None,
        filename: str | None = None, **kwargs: Any,
    ) -> Message:
        return await self._send_media("sendAnimation", "animation", chat_id, animation,
                                      caption=caption, parse_mode=parse_mode,
                                      reply_parameters=reply_parameters,
                                      reply_markup=reply_markup,
                                      message_thread_id=message_thread_id,
                                      has_spoiler=has_spoiler,
                                      filename=filename, **kwargs)

    async def send_media_group(
        self, chat_id: int | str, media: list[InputMedia],
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        reply_parameters: ReplyParameters | None = None,
        allow_paid_broadcast: bool | None = None,
        **kwargs: Any,
    ) -> list[Message]:
        p: dict[str, Any] = {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
        }
        p["media"] = _serialize(media)
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        p.update(kwargs)
        data = await self._request("sendMediaGroup", p)
        return [_parse_field(Message, item) for item in data]

    async def send_location(
        self, chat_id: int | str, latitude: float, longitude: float,
        horizontal_accuracy: float | None = None,
        live_period: int | None = None,
        heading: int | None = None,
        proximity_alert_radius: int | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "latitude": latitude, "longitude": longitude,
            "horizontal_accuracy": horizontal_accuracy,
            "live_period": live_period, "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendLocation", p))

    async def send_venue(
        self, chat_id: int | str, latitude: float, longitude: float,
        title: str, address: str,
        foursquare_id: str | None = None,
        foursquare_type: str | None = None,
        google_place_id: str | None = None,
        google_place_type: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "latitude": latitude, "longitude": longitude,
            "title": title, "address": address,
            "foursquare_id": foursquare_id, "foursquare_type": foursquare_type,
            "google_place_id": google_place_id, "google_place_type": google_place_type,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendVenue", p))

    async def send_contact(
        self, chat_id: int | str, phone_number: str, first_name: str,
        last_name: str | None = None,
        vcard: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "phone_number": phone_number,
            "first_name": first_name, "last_name": last_name,
            "vcard": vcard, "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendContact", p))

    async def send_poll(
        self, chat_id: int | str, question: str, options: list[str],
        is_anonymous: bool | None = None,
        type: str | None = None,
        allows_multiple_answers: bool | None = None,
        correct_option_id: int | None = None,
        correct_option_ids: list[int] | None = None,
        explanation: str | None = None,
        explanation_parse_mode: str | None = None,
        description: str | None = None,
        description_parse_mode: str | None = None,
        description_entities: list[Any] | None = None,
        media: Any | None = None,
        explanation_media: Any | None = None,
        members_only: bool | None = None,
        country_codes: list[str] | None = None,
        allows_revoting: bool | None = None,
        shuffle_options: bool | None = None,
        allow_adding_options: bool | None = None,
        hide_results_until_closes: bool | None = None,
        open_period: int | None = None,
        close_date: int | None = None,
        is_closed: bool | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "question": question, "options": options,
            "is_anonymous": is_anonymous, "type": type,
            "allows_multiple_answers": allows_multiple_answers,
            "correct_option_id": correct_option_id,
            "correct_option_ids": correct_option_ids,
            "explanation": explanation,
            "explanation_parse_mode": explanation_parse_mode,
            "description": description,
            "description_parse_mode": description_parse_mode,
            "description_entities": _serialize(description_entities) if description_entities is not None else None,
            "media": _serialize(media) if media is not None else None,
            "explanation_media": _serialize(explanation_media) if explanation_media is not None else None,
            "members_only": members_only,
            "country_codes": country_codes,
            "allows_revoting": allows_revoting,
            "shuffle_options": shuffle_options,
            "allow_adding_options": allow_adding_options,
            "hide_results_until_closes": hide_results_until_closes,
            "open_period": open_period, "close_date": close_date,
            "is_closed": is_closed,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendPoll", p))

    async def send_dice(
        self, chat_id: int | str,
        emoji: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "emoji": emoji,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendDice", p))

    async def send_chat_action(self, chat_id: int | str, action: str,
                                message_thread_id: int | None = None) -> bool:
        return bool(await self._request("sendChatAction", {
            "chat_id": chat_id, "action": action, "message_thread_id": message_thread_id,
        }))

    async def forward_message(
        self, chat_id: int | str, from_chat_id: int | str,
        message_id: int,
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
    ) -> Message:
        return _parse_field(Message, await self._request("forwardMessage", {
            "chat_id": chat_id, "from_chat_id": from_chat_id,
            "message_id": message_id, "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
        }))

    async def forward_messages(
        self, chat_id: int | str, from_chat_id: int | str,
        message_ids: list[int],
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
    ) -> list[Message]:
        data = await self._request("forwardMessages", {
            "chat_id": chat_id, "from_chat_id": from_chat_id,
            "message_ids": message_ids, "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
        })
        return [_parse_field(Message, item) for item in data]

    async def copy_message(
        self, chat_id: int | str, from_chat_id: int | str,
        message_id: int,
        caption: str | None = None,
        parse_mode: str | None = None,
        caption_entities: list | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        allow_paid_broadcast: bool | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "from_chat_id": from_chat_id,
            "message_id": message_id, "caption": caption,
            "parse_mode": parse_mode, "caption_entities": caption_entities,
            "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "allow_paid_broadcast": allow_paid_broadcast,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("copyMessage", p))

    async def copy_messages(
        self, chat_id: int | str, from_chat_id: int | str,
        message_ids: list[int],
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        remove_caption: bool | None = None,
    ) -> list[Message]:
        data = await self._request("copyMessages", {
            "chat_id": chat_id, "from_chat_id": from_chat_id,
            "message_ids": message_ids, "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
            "remove_caption": remove_caption,
        })
        return [_parse_field(Message, item) for item in data]

    async def send_paid_media(
        self, chat_id: int | str, star_count: int, media: list[InputMedia],
        caption: str | None = None,
        parse_mode: str | None = None,
        show_caption_above_media: bool | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        payload: str | None = None,
        allow_paid_broadcast: bool | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "star_count": star_count,
            "media": _serialize(media),
            "caption": caption, "parse_mode": parse_mode,
            "show_caption_above_media": show_caption_above_media,
            "payload": payload,
            "allow_paid_broadcast": allow_paid_broadcast,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        return _parse_field(Message, await self._request("sendPaidMedia", p))

    # ═══════════════════════════════════════════
    # Messages — edit
    # ═══════════════════════════════════════════

    async def edit_message_text(
        self, text: str,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        parse_mode: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        link_preview_options: dict | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "text": text, "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id, "parse_mode": parse_mode,
            "link_preview_options": link_preview_options,
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("editMessageText", p))

    async def edit_message_caption(
        self,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        caption: str | None = None,
        parse_mode: str | None = None,
        caption_entities: list | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        show_caption_above_media: bool | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
            "caption": caption, "parse_mode": parse_mode,
            "caption_entities": caption_entities,
            "show_caption_above_media": show_caption_above_media,
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("editMessageCaption", p))

    async def edit_message_media(
        self, media: InputMedia,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
            "media": _serialize(media),
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("editMessageMedia", p))

    async def edit_message_reply_markup(
        self,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        return _parse_field(Message, await self._request("editMessageReplyMarkup", p))

    async def stop_poll(
        self, chat_id: int | str, message_id: int,
        reply_markup: InlineKeyboardMarkup | None = None,
        **kwargs: Any,
    ) -> Poll:
        p: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Poll, await self._request("stopPoll", p))

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        return bool(await self._request("deleteMessage", {
            "chat_id": chat_id, "message_id": message_id,
        }))

    async def delete_messages(self, chat_id: int | str, message_ids: list[int]) -> bool:
        return bool(await self._request("deleteMessages", {
            "chat_id": chat_id, "message_ids": message_ids,
        }))

    # ═══════════════════════════════════════════
    # Messages — reactions
    # ═══════════════════════════════════════════

    async def set_message_reaction(
        self, chat_id: int | str, message_id: int,
        reaction: list[ReactionTypeEmoji] | None = None,
        is_big: bool | None = None,
    ) -> bool:
        p: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "is_big": is_big}
        if reaction is not None:
            p["reaction"] = [{"type": r.type, "emoji": r.emoji} for r in reaction]
        else:
            p["reaction"] = []
        return bool(await self._request("setMessageReaction", p))

    async def delete_message_reaction(self, chat_id: int | str, message_id: int) -> bool:
        return bool(await self._request("deleteMessageReaction", {
            "chat_id": chat_id, "message_id": message_id,
        }))

    async def delete_all_message_reactions(self, chat_id: int | str, message_id: int) -> bool:
        return bool(await self._request("deleteAllMessageReactions", {
            "chat_id": chat_id, "message_id": message_id,
        }))

    # ═══════════════════════════════════════════
    # Live Location
    # ═══════════════════════════════════════════

    async def edit_message_live_location(
        self, latitude: float, longitude: float,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        live_period: int | None = None,
        horizontal_accuracy: float | None = None,
        heading: int | None = None,
        proximity_alert_radius: int | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        p: dict[str, Any] = {
            "latitude": latitude, "longitude": longitude,
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
            "live_period": live_period,
            "horizontal_accuracy": horizontal_accuracy,
            "heading": heading,
            "proximity_alert_radius": proximity_alert_radius,
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        return _parse_field(Message, await self._request("editMessageLiveLocation", p))

    async def stop_message_live_location(
        self,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
        }
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        return _parse_field(Message, await self._request("stopMessageLiveLocation", p))

    # ═══════════════════════════════════════════
    # Stickers
    # ═══════════════════════════════════════════

    async def get_sticker_set(self, name: str) -> StickerSet:
        return _parse_field(StickerSet, await self._request("getStickerSet", {"name": name}))

    async def get_custom_emoji_stickers(self, custom_emoji_ids: list[str]) -> list[Sticker]:
        data = await self._request("getCustomEmojiStickers", {"custom_emoji_ids": custom_emoji_ids})
        return [_parse_field(Sticker, item) for item in data]

    async def upload_sticker_file(
        self, user_id: int, sticker: bytes | Path,
        sticker_format: str = "static",
        filename: str | None = None,
    ) -> File:
        fname = filename or "sticker.png"
        media_bytes, _ = _resolve_media(sticker)
        files = {"sticker": (fname, media_bytes, _guess_mime("sticker", fname))}
        return _parse_field(File, await self._request("uploadStickerFile", {
            "user_id": user_id, "sticker_format": sticker_format,
        }, files=files))

    async def create_new_sticker_set(
        self, user_id: int, name: str, title: str,
        stickers: list[dict],
        sticker_format: str = "static",
        sticker_type: str | None = None,
        needs_repainting: bool | None = None,
    ) -> bool:
        return bool(await self._request("createNewStickerSet", {
            "user_id": user_id, "name": name, "title": title,
            "stickers": stickers, "sticker_format": sticker_format,
            "sticker_type": sticker_type,
            "needs_repainting": needs_repainting,
        }))

    async def add_sticker_to_set(
        self, user_id: int, name: str, sticker: dict,
    ) -> bool:
        return bool(await self._request("addStickerToSet", {
            "user_id": user_id, "name": name, "sticker": sticker,
        }))

    async def set_sticker_position_in_set(self, sticker: str, position: int) -> bool:
        return bool(await self._request("setStickerPositionInSet", {
            "sticker": sticker, "position": position,
        }))

    async def delete_sticker_from_set(self, sticker: str) -> bool:
        return bool(await self._request("deleteStickerFromSet", {"sticker": sticker}))

    async def set_sticker_emoji_list(self, sticker: str, emoji_list: list[str]) -> bool:
        return bool(await self._request("setStickerEmojiList", {
            "sticker": sticker, "emoji_list": emoji_list,
        }))

    async def set_sticker_keywords(self, sticker: str, keywords: list[str]) -> bool:
        return bool(await self._request("setStickerKeywords", {
            "sticker": sticker, "keywords": keywords,
        }))

    async def set_sticker_mask_position(self, sticker: str, mask_position: dict) -> bool:
        return bool(await self._request("setStickerMaskPosition", {
            "sticker": sticker, "mask_position": mask_position,
        }))

    async def set_sticker_set_title(self, name: str, title: str) -> bool:
        return bool(await self._request("setStickerSetTitle", {
            "name": name, "title": title,
        }))

    async def set_sticker_set_thumbnail(
        self, name: str, user_id: int,
        thumbnail: str | None = None,
        format: str = "static",
    ) -> bool:
        return bool(await self._request("setStickerSetThumbnail", {
            "name": name, "user_id": user_id,
            "thumbnail": thumbnail, "format": format,
        }))

    async def set_custom_emoji_sticker_set_thumbnail(
        self, name: str, custom_emoji_id: str | None = None,
    ) -> bool:
        return bool(await self._request("setCustomEmojiStickerSetThumbnail", {
            "name": name, "custom_emoji_id": custom_emoji_id,
        }))

    async def delete_sticker_set(self, name: str) -> bool:
        return bool(await self._request("deleteStickerSet", {"name": name}))

    # ═══════════════════════════════════════════
    # Inline mode
    # ═══════════════════════════════════════════

    async def answer_inline_query(
        self, inline_query_id: str, results: list[dict],
        cache_time: int | None = None,
        is_personal: bool | None = None,
        next_offset: str | None = None,
        button: dict | None = None,
    ) -> bool:
        return bool(await self._request("answerInlineQuery", {
            "inline_query_id": inline_query_id, "results": results,
            "cache_time": cache_time, "is_personal": is_personal,
            "next_offset": next_offset, "button": button,
        }))

    # ═══════════════════════════════════════════
    # Payments
    # ═══════════════════════════════════════════

    async def send_invoice(
        self, chat_id: int | str, title: str, description: str,
        payload: str, provider_token: str, currency: str,
        prices: list[dict],
        max_tip_amount: int | None = None,
        suggested_tip_amounts: list[int] | None = None,
        start_parameter: str | None = None,
        provider_data: dict | None = None,
        photo_url: str | None = None,
        photo_size: int | None = None,
        photo_width: int | None = None,
        photo_height: int | None = None,
        need_name: bool | None = None,
        need_phone_number: bool | None = None,
        need_email: bool | None = None,
        need_shipping_address: bool | None = None,
        send_phone_number_to_provider: bool | None = None,
        send_email_to_provider: bool | None = None,
        is_flexible: bool | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "title": title, "description": description,
            "payload": payload, "provider_token": provider_token,
            "currency": currency, "prices": prices,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "start_parameter": start_parameter,
            "provider_data": provider_data,
            "photo_url": photo_url, "photo_size": photo_size,
            "photo_width": photo_width, "photo_height": photo_height,
            "need_name": need_name, "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
            "message_thread_id": message_thread_id,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)
        return _parse_field(Message, await self._request("sendInvoice", p))

    async def create_invoice_link(
        self, title: str, description: str,
        payload: str, provider_token: str, currency: str,
        prices: list[dict],
        max_tip_amount: int | None = None,
        suggested_tip_amounts: list[int] | None = None,
        provider_data: dict | None = None,
        photo_url: str | None = None,
        photo_size: int | None = None,
        photo_width: int | None = None,
        photo_height: int | None = None,
        need_name: bool | None = None,
        need_phone_number: bool | None = None,
        need_email: bool | None = None,
        need_shipping_address: bool | None = None,
        send_phone_number_to_provider: bool | None = None,
        send_email_to_provider: bool | None = None,
        is_flexible: bool | None = None,
    ) -> str:
        return str(await self._request("createInvoiceLink", {
            "title": title, "description": description,
            "payload": payload, "provider_token": provider_token,
            "currency": currency, "prices": prices,
            "max_tip_amount": max_tip_amount,
            "suggested_tip_amounts": suggested_tip_amounts,
            "provider_data": provider_data,
            "photo_url": photo_url, "photo_size": photo_size,
            "photo_width": photo_width, "photo_height": photo_height,
            "need_name": need_name, "need_phone_number": need_phone_number,
            "need_email": need_email,
            "need_shipping_address": need_shipping_address,
            "send_phone_number_to_provider": send_phone_number_to_provider,
            "send_email_to_provider": send_email_to_provider,
            "is_flexible": is_flexible,
        }))

    async def answer_shipping_query(
        self, shipping_query_id: str, ok: bool,
        shipping_options: list[dict] | None = None,
        error_message: str | None = None,
    ) -> bool:
        return bool(await self._request("answerShippingQuery", {
            "shipping_query_id": shipping_query_id, "ok": ok,
            "shipping_options": shipping_options,
            "error_message": error_message,
        }))

    async def answer_pre_checkout_query(
        self, pre_checkout_query_id: str, ok: bool,
        error_message: str | None = None,
    ) -> bool:
        return bool(await self._request("answerPreCheckoutQuery", {
            "pre_checkout_query_id": pre_checkout_query_id, "ok": ok,
            "error_message": error_message,
        }))

    # ═══════════════════════════════════════════
    # Games
    # ═══════════════════════════════════════════

    async def send_game(
        self, chat_id: int | str, game_short_name: str,
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        protect_content: bool | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Message:
        p: dict[str, Any] = {
            "chat_id": chat_id, "game_short_name": game_short_name,
            "message_thread_id": message_thread_id,
            "disable_notification": disable_notification,
            "protect_content": protect_content,
        }
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        return _parse_field(Message, await self._request("sendGame", p))

    async def set_game_score(
        self, user_id: int, score: int,
        force: bool | None = None,
        disable_edit_message: bool | None = None,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
    ) -> Message:
        return _parse_field(Message, await self._request("setGameScore", {
            "user_id": user_id, "score": score, "force": force,
            "disable_edit_message": disable_edit_message,
            "chat_id": chat_id, "message_id": message_id,
            "inline_message_id": inline_message_id,
        }))

    async def get_game_high_scores(
        self, user_id: int,
        chat_id: int | str | None = None,
        message_id: int | None = None,
        inline_message_id: str | None = None,
    ) -> list[GameHighScore]:
        data = await self._request("getGameHighScores", {
            "user_id": user_id, "chat_id": chat_id,
            "message_id": message_id, "inline_message_id": inline_message_id,
        })
        return [_parse_field(GameHighScore, item) for item in data]

    # ═══════════════════════════════════════════
    # Callback queries
    # ═══════════════════════════════════════════

    async def answer_callback_query(
        self, callback_query_id: str,
        text: str | None = None, show_alert: bool | None = None,
        url: str | None = None, cache_time: int | None = None,
    ) -> bool:
        return bool(await self._request("answerCallbackQuery", {
            "callback_query_id": callback_query_id, "text": text,
            "show_alert": show_alert, "url": url, "cache_time": cache_time,
        }))

    # ═══════════════════════════════════════════
    # Chat — get / set
    # ═══════════════════════════════════════════

    async def get_chat(self, chat_id: int | str) -> ChatFullInfo:
        return _parse_field(ChatFullInfo, await self._request("getChat", {"chat_id": chat_id}))

    async def get_chat_administrators(
        self, chat_id: int | str, return_bots: bool | None = None,
    ) -> list[ChatMember]:
        params: dict[str, Any] = {"chat_id": chat_id}
        if return_bots is not None:
            params["return_bots"] = return_bots
        data = await self._request("getChatAdministrators", params)
        return [_parse_field(_chat_member_type(item), item) for item in data]

    async def get_chat_member_count(self, chat_id: int | str) -> int:
        return int(await self._request("getChatMemberCount", {"chat_id": chat_id}))

    async def get_chat_member(self, chat_id: int | str, user_id: int) -> ChatMember:
        data = await self._request("getChatMember", {"chat_id": chat_id, "user_id": user_id})
        return _parse_field(_chat_member_type(data), data)

    async def set_chat_title(self, chat_id: int | str, title: str) -> bool:
        return bool(await self._request("setChatTitle", {"chat_id": chat_id, "title": title}))

    async def set_chat_description(self, chat_id: int | str, description: str | None = None) -> bool:
        return bool(await self._request("setChatDescription", {
            "chat_id": chat_id, "description": description,
        }))

    async def set_chat_photo(self, chat_id: int | str, photo: bytes | Path) -> bool:
        media_bytes, _ = _resolve_media(photo)
        files = {"photo": ("photo.jpg", media_bytes, "image/jpeg")}
        return bool(await self._request("setChatPhoto", {"chat_id": chat_id}, files=files))

    async def delete_chat_photo(self, chat_id: int | str) -> bool:
        return bool(await self._request("deleteChatPhoto", {"chat_id": chat_id}))

    async def set_chat_permissions(self, chat_id: int | str, permissions: ChatPermissions) -> bool:
        return bool(await self._request("setChatPermissions", {
            "chat_id": chat_id, "permissions": _serialize(permissions),
        }))

    async def set_chat_sticker_set(self, chat_id: int | str, sticker_set_name: str) -> bool:
        return bool(await self._request("setChatStickerSet", {
            "chat_id": chat_id, "sticker_set_name": sticker_set_name,
        }))

    async def delete_chat_sticker_set(self, chat_id: int | str) -> bool:
        return bool(await self._request("deleteChatStickerSet", {"chat_id": chat_id}))

    async def get_chat_available_gifts(self, chat_id: int | str) -> Gifts:
        return _parse_field(Gifts, await self._request("getChatAvailableGifts", {"chat_id": chat_id}))

    async def leave_chat(self, chat_id: int | str) -> bool:
        return bool(await self._request("leaveChat", {"chat_id": chat_id}))

    async def pin_chat_message(
        self, chat_id: int | str, message_id: int,
        disable_notification: bool | None = None,
    ) -> bool:
        return bool(await self._request("pinChatMessage", {
            "chat_id": chat_id, "message_id": message_id,
            "disable_notification": disable_notification,
        }))

    async def unpin_chat_message(
        self, chat_id: int | str, message_id: int | None = None,
    ) -> bool:
        return bool(await self._request("unpinChatMessage", {
            "chat_id": chat_id, "message_id": message_id,
        }))

    async def unpin_all_chat_messages(self, chat_id: int | str) -> bool:
        return bool(await self._request("unpinAllChatMessages", {"chat_id": chat_id}))

    # ═══════════════════════════════════════════
    # Invite Links
    # ═══════════════════════════════════════════

    async def export_chat_invite_link(self, chat_id: int | str) -> str:
        return str(await self._request("exportChatInviteLink", {"chat_id": chat_id}))

    async def create_chat_invite_link(
        self, chat_id: int | str,
        name: str | None = None,
        expire_date: int | None = None,
        member_limit: int | None = None,
        creates_join_request: bool | None = None,
    ) -> ChatInviteLink:
        return _parse_field(ChatInviteLink, await self._request("createChatInviteLink", {
            "chat_id": chat_id, "name": name,
            "expire_date": expire_date, "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }))

    async def edit_chat_invite_link(
        self, chat_id: int | str, invite_link: str,
        name: str | None = None,
        expire_date: int | None = None,
        member_limit: int | None = None,
        creates_join_request: bool | None = None,
    ) -> ChatInviteLink:
        return _parse_field(ChatInviteLink, await self._request("editChatInviteLink", {
            "chat_id": chat_id, "invite_link": invite_link,
            "name": name, "expire_date": expire_date,
            "member_limit": member_limit,
            "creates_join_request": creates_join_request,
        }))

    async def revoke_chat_invite_link(self, chat_id: int | str, invite_link: str) -> ChatInviteLink:
        return _parse_field(ChatInviteLink, await self._request("revokeChatInviteLink", {
            "chat_id": chat_id, "invite_link": invite_link,
        }))

    async def create_chat_subscription_invite_link(
        self, chat_id: int | str,
        subscription_period: int,
        subscription_price: int,
        name: str | None = None,
    ) -> ChatInviteLink:
        return _parse_field(ChatInviteLink, await self._request("createChatSubscriptionInviteLink", {
            "chat_id": chat_id, "subscription_period": subscription_period,
            "subscription_price": subscription_price, "name": name,
        }))

    async def edit_chat_subscription_invite_link(
        self, chat_id: int | str, invite_link: str,
        name: str | None = None,
    ) -> ChatInviteLink:
        return _parse_field(ChatInviteLink, await self._request("editChatSubscriptionInviteLink", {
            "chat_id": chat_id, "invite_link": invite_link, "name": name,
        }))

    # ═══════════════════════════════════════════
    # Chat join requests
    # ═══════════════════════════════════════════

    async def approve_chat_join_request(self, chat_id: int | str, user_id: int) -> bool:
        return bool(await self._request("approveChatJoinRequest", {
            "chat_id": chat_id, "user_id": user_id,
        }))

    async def decline_chat_join_request(self, chat_id: int | str, user_id: int) -> bool:
        return bool(await self._request("declineChatJoinRequest", {
            "chat_id": chat_id, "user_id": user_id,
        }))

    # ═══════════════════════════════════════════
    # Ban / restrict / promote
    # ═══════════════════════════════════════════

    async def ban_chat_member(
        self, chat_id: int | str, user_id: int,
        until_date: int | None = None,
        revoke_messages: bool | None = None,
    ) -> bool:
        return bool(await self._request("banChatMember", {
            "chat_id": chat_id, "user_id": user_id,
            "until_date": until_date, "revoke_messages": revoke_messages,
        }))

    async def unban_chat_member(
        self, chat_id: int | str, user_id: int,
        only_if_banned: bool | None = None,
    ) -> bool:
        return bool(await self._request("unbanChatMember", {
            "chat_id": chat_id, "user_id": user_id,
            "only_if_banned": only_if_banned,
        }))

    async def restrict_chat_member(
        self, chat_id: int | str, user_id: int,
        permissions: ChatPermissions,
        use_independent_chat_permissions: bool | None = None,
        until_date: int | None = None,
    ) -> bool:
        return bool(await self._request("restrictChatMember", {
            "chat_id": chat_id, "user_id": user_id,
            "permissions": _serialize(permissions),
            "use_independent_chat_permissions": use_independent_chat_permissions,
            "until_date": until_date,
        }))

    async def promote_chat_member(
        self, chat_id: int | str, user_id: int,
        is_anonymous: bool | None = None,
        can_manage_chat: bool | None = None,
        can_delete_messages: bool | None = None,
        can_manage_video_chats: bool | None = None,
        can_restrict_members: bool | None = None,
        can_promote_members: bool | None = None,
        can_change_info: bool | None = None,
        can_invite_users: bool | None = None,
        can_post_stories: bool | None = None,
        can_edit_stories: bool | None = None,
        can_delete_stories: bool | None = None,
        can_post_messages: bool | None = None,
        can_edit_messages: bool | None = None,
        can_pin_messages: bool | None = None,
        can_manage_topics: bool | None = None,
        can_manage_tags: bool | None = None,
    ) -> bool:
        return bool(await self._request("promoteChatMember", {
            "chat_id": chat_id, "user_id": user_id,
            "is_anonymous": is_anonymous,
            "can_manage_chat": can_manage_chat,
            "can_delete_messages": can_delete_messages,
            "can_manage_video_chats": can_manage_video_chats,
            "can_restrict_members": can_restrict_members,
            "can_promote_members": can_promote_members,
            "can_change_info": can_change_info,
            "can_invite_users": can_invite_users,
            "can_post_stories": can_post_stories,
            "can_edit_stories": can_edit_stories,
            "can_delete_stories": can_delete_stories,
            "can_post_messages": can_post_messages,
            "can_edit_messages": can_edit_messages,
            "can_pin_messages": can_pin_messages,
            "can_manage_topics": can_manage_topics,
            "can_manage_tags": can_manage_tags,
        }))

    async def set_chat_administrator_custom_title(
        self, chat_id: int | str, user_id: int, custom_title: str,
    ) -> bool:
        return bool(await self._request("setChatAdministratorCustomTitle", {
            "chat_id": chat_id, "user_id": user_id,
            "custom_title": custom_title,
        }))

    # ═══════════════════════════════════════════
    # Forum topics
    # ═══════════════════════════════════════════

    async def create_forum_topic(
        self, chat_id: int | str, name: str,
        icon_color: int | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> ForumTopic:
        return _parse_field(ForumTopic, await self._request("createForumTopic", {
            "chat_id": chat_id, "name": name,
            "icon_color": icon_color,
            "icon_custom_emoji_id": icon_custom_emoji_id,
        }))

    async def edit_forum_topic(
        self, chat_id: int | str, message_thread_id: int,
        name: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> bool:
        return bool(await self._request("editForumTopic", {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
            "name": name, "icon_custom_emoji_id": icon_custom_emoji_id,
        }))

    async def close_forum_topic(self, chat_id: int | str, message_thread_id: int) -> bool:
        return bool(await self._request("closeForumTopic", {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
        }))

    async def reopen_forum_topic(self, chat_id: int | str, message_thread_id: int) -> bool:
        return bool(await self._request("reopenForumTopic", {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
        }))

    async def delete_forum_topic(self, chat_id: int | str, message_thread_id: int) -> bool:
        return bool(await self._request("deleteForumTopic", {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
        }))

    async def unpin_all_forum_topic_messages(
        self, chat_id: int | str, message_thread_id: int,
    ) -> bool:
        return bool(await self._request("unpinAllForumTopicMessages", {
            "chat_id": chat_id, "message_thread_id": message_thread_id,
        }))

    async def edit_general_forum_topic(self, chat_id: int | str, name: str) -> bool:
        return bool(await self._request("editGeneralForumTopic", {
            "chat_id": chat_id, "name": name,
        }))

    async def close_general_forum_topic(self, chat_id: int | str) -> bool:
        return bool(await self._request("closeGeneralForumTopic", {"chat_id": chat_id}))

    async def reopen_general_forum_topic(self, chat_id: int | str) -> bool:
        return bool(await self._request("reopenGeneralForumTopic", {"chat_id": chat_id}))

    async def hide_general_forum_topic(self, chat_id: int | str) -> bool:
        return bool(await self._request("hideGeneralForumTopic", {"chat_id": chat_id}))

    async def unhide_general_forum_topic(self, chat_id: int | str) -> bool:
        return bool(await self._request("unhideGeneralForumTopic", {"chat_id": chat_id}))

    # ═══════════════════════════════════════════
    # File
    # ═══════════════════════════════════════════

    async def get_file(self, file_id: str) -> File:
        data = await self._request("getFile", {"file_id": file_id})
        file_obj = _parse_field(File, data)
        file_path = file_obj.file_path or ""
        real_url = self.FILE_URL.format(token=self.token)

        async def download_to_drive(path: str) -> None:
            url = f"{real_url}{file_path}"
            try:
                resp = await self._client.get(url)
                resp.raise_for_status()
                Path(path).write_bytes(resp.content)
            except httpx.TimeoutException as e:
                raise TimedOut(_redact_token(e, self.token)) from e
            except httpx.RequestError as e:
                raise NetworkError(_redact_token(e, self.token)) from e

        object.__setattr__(file_obj, "download_to_drive", download_to_drive)
        return file_obj

    # ═══════════════════════════════════════════
    # Bot commands
    # ═══════════════════════════════════════════

    async def set_my_commands(
        self, commands: list[BotCommand],
        scope: BotCommandScopeDefault | None = None,
        language_code: str | None = None,
    ) -> bool:
        p: dict[str, Any] = {"commands": _serialize(commands)}
        if scope is not None:
            p["scope"] = _serialize(scope)
        if language_code is not None:
            p["language_code"] = language_code
        return bool(await self._request("setMyCommands", p))

    async def delete_my_commands(
        self,
        scope: BotCommandScopeDefault | None = None,
        language_code: str | None = None,
    ) -> bool:
        p: dict[str, Any] = {}
        if scope is not None:
            p["scope"] = _serialize(scope)
        if language_code is not None:
            p["language_code"] = language_code
        return bool(await self._request("deleteMyCommands", p))

    async def get_my_commands(
        self,
        scope: BotCommandScopeDefault | None = None,
        language_code: str | None = None,
    ) -> list[BotCommand]:
        p: dict[str, Any] = {}
        if scope is not None:
            p["scope"] = _serialize(scope)
        if language_code is not None:
            p["language_code"] = language_code
        data = await self._request("getMyCommands", p)
        return [_parse_field(BotCommand, item) for item in data]

    # ═══════════════════════════════════════════
    # Bot name / description / about
    # ═══════════════════════════════════════════

    async def get_my_name(self, language_code: str | None = None) -> str:
        data = await self._request("getMyName", {"language_code": language_code})
        return data.get("name", "") if isinstance(data, dict) else str(data)

    async def set_my_name(self, name: str, language_code: str | None = None) -> bool:
        return bool(await self._request("setMyName", {
            "name": name, "language_code": language_code,
        }))

    async def get_my_description(self, language_code: str | None = None) -> str:
        data = await self._request("getMyDescription", {"language_code": language_code})
        return data.get("description", "") if isinstance(data, dict) else str(data)

    async def set_my_description(self, description: str, language_code: str | None = None) -> bool:
        return bool(await self._request("setMyDescription", {
            "description": description, "language_code": language_code,
        }))

    async def get_my_short_description(self, language_code: str | None = None) -> str:
        data = await self._request("getMyShortDescription", {"language_code": language_code})
        return data.get("short_description", "") if isinstance(data, dict) else str(data)

    async def set_my_short_description(self, short_description: str, language_code: str | None = None) -> bool:
        return bool(await self._request("setMyShortDescription", {
            "short_description": short_description, "language_code": language_code,
        }))

    # ═══════════════════════════════════════════
    # Menu button
    # ═══════════════════════════════════════════

    async def set_chat_menu_button(self, chat_id: int | None = None, menu_button: MenuButton | None = None) -> bool:
        p: dict[str, Any] = {"chat_id": chat_id}
        if menu_button is not None:
            p["menu_button"] = _serialize(menu_button)
        return bool(await self._request("setChatMenuButton", p))

    async def get_chat_menu_button(self, chat_id: int | None = None) -> MenuButton:
        data = await self._request("getChatMenuButton", {"chat_id": chat_id})
        return _parse_field(_menu_button_type(data), data)

    # ═══════════════════════════════════════════
    # Default administrator rights
    # ═══════════════════════════════════════════

    async def set_my_default_administrator_rights(
        self, rights: ChatAdministratorRights | None = None,
        for_channels: bool | None = None,
    ) -> bool:
        p: dict[str, Any] = {"for_channels": for_channels}
        if rights is not None:
            p["rights"] = _serialize(rights)
        return bool(await self._request("setMyDefaultAdministratorRights", p))

    async def get_my_default_administrator_rights(
        self, for_channels: bool | None = None,
    ) -> ChatAdministratorRights:
        return _parse_field(ChatAdministratorRights, await self._request(
            "getMyDefaultAdministratorRights", {"for_channels": for_channels},
        ))

    # ═══════════════════════════════════════════
    # Stars & gifts
    # ═══════════════════════════════════════════

    async def get_available_gifts(self) -> Gifts:
        return _parse_field(Gifts, await self._request("getAvailableGifts"))

    async def send_gift(
        self, user_id: int, gift_id: str,
        text: str | None = None,
        text_parse_mode: str | None = None,
        text_entities: list | None = None,
        tone: str | None = None,
        model_tone: str | None = None,
        pay_for_upgrade: bool | None = None,
    ) -> bool:
        return bool(await self._request("sendGift", {
            "user_id": user_id, "gift_id": gift_id,
            "text": text, "text_parse_mode": text_parse_mode,
            "text_entities": text_entities,
            "tone": tone, "model_tone": model_tone,
            "pay_for_upgrade": pay_for_upgrade,
        }))

    async def get_star_transactions(self, offset: int | None = None, limit: int | None = None) -> StarTransactions:
        return _parse_field(StarTransactions, await self._request(
            "getStarTransactions", {"offset": offset, "limit": limit},
        ))

    async def refund_star_payment(self, user_id: int, telegram_payment_charge_id: str) -> bool:
        return bool(await self._request("refundStarPayment", {
            "user_id": user_id,
            "telegram_payment_charge_id": telegram_payment_charge_id,
        }))

    # ═══════════════════════════════════════════
    # Telegram Business
    # ═══════════════════════════════════════════

    async def get_business_connection(self, business_connection_id: str) -> BusinessConnection:
        return _parse_field(BusinessConnection, await self._request(
            "getBusinessConnection", {"business_connection_id": business_connection_id},
        ))

    async def set_business_account_username(self, username: str) -> bool:
        return bool(await self._request("setBusinessAccountUsername", {"username": username}))

    async def set_business_account_bio(self, bio: str) -> bool:
        return bool(await self._request("setBusinessAccountBio", {"bio": bio}))

    async def set_business_account_profile_photo(self, photo: bytes | Path) -> bool:
        media_bytes, _ = _resolve_media(photo)
        files = {"photo": ("photo.jpg", media_bytes, "image/jpeg")}
        return bool(await self._request("setBusinessAccountProfilePhoto", {}, files=files))

    async def delete_business_account_profile_photo(self) -> bool:
        return bool(await self._request("deleteBusinessAccountProfilePhoto"))

    async def set_business_account_gift_settings(self, show_gift_button: bool) -> bool:
        return bool(await self._request("setBusinessAccountGiftSettings", {
            "show_gift_button": show_gift_button,
        }))

    async def get_business_account_gift_settings(self) -> dict:
        return await self._request("getBusinessAccountGiftSettings")

    # ═══════════════════════════════════════════
    # Verification
    # ═══════════════════════════════════════════

    async def verify_user(self, user_id: int, custom_description: str | None = None) -> bool:
        return bool(await self._request("verifyUser", {
            "user_id": user_id, "custom_description": custom_description,
        }))

    async def verify_chat(self, chat_id: int | str, custom_description: str | None = None) -> bool:
        return bool(await self._request("verifyChat", {
            "chat_id": chat_id, "custom_description": custom_description,
        }))

    async def remove_user_verification(self, user_id: int) -> bool:
        return bool(await self._request("removeUserVerification", {"user_id": user_id}))

    async def remove_chat_verification(self, chat_id: int | str) -> bool:
        return bool(await self._request("removeChatVerification", {"chat_id": chat_id}))

    # ═══════════════════════════════════════════
    # Managed bots (Bot API v10)
    # ═══════════════════════════════════════════

    async def get_managed_bot_token(self, user_id: int | None = None, bot_user_id: int | None = None) -> str:
        data = await self._request("getManagedBotToken", {"user_id": user_id if user_id is not None else bot_user_id})
        return data.get("token", str(data)) if isinstance(data, dict) else str(data)

    async def set_managed_bot_token(
        self, user_id: int | None = None, token: str | None = None, bot_user_id: int | None = None,
    ) -> bool:
        return bool(await self._request("setManagedBotToken", {
            "user_id": user_id if user_id is not None else bot_user_id, "token": token,
        }))

    async def reissue_managed_bot_token(
        self, user_id: int | None = None, bot_user_id: int | None = None,
    ) -> str:
        data = await self._request("reissueManagedBotToken", {"user_id": user_id if user_id is not None else bot_user_id})
        return data.get("token", str(data)) if isinstance(data, dict) else str(data)

    async def get_managed_bot_access_settings(self, user_id: int) -> dict:
        return await self._request("getManagedBotAccessSettings", {"user_id": user_id})

    async def set_managed_bot_access_settings(self, user_id: int, **settings) -> bool:
        return bool(await self._request("setManagedBotAccessSettings", {"user_id": user_id, **settings}))

    # ═══════════════════════════════════════════
    # Bot API v10 special methods
    # ═══════════════════════════════════════════

    async def send_message_draft(self, chat_id: int | str, text: str = "", **kwargs) -> Message:
        return _parse_field(Message, await self._request("sendMessageDraft", {
            "chat_id": chat_id, "text": text, **kwargs,
        }))

    async def answer_guest_query(
        self,
        guest_query_id: str,
        result: Any | None = None,
        text: str | None = None,
        parse_mode: str | None = None,
        **kwargs: Any,
    ) -> SentGuestMessage:
        params: dict[str, Any] = {"guest_query_id": guest_query_id, **kwargs}
        if result is not None:
            params["result"] = _serialize(result)
        elif text is not None:
            params["text"] = text
        if parse_mode is not None:
            params["parse_mode"] = parse_mode
        data = await self._request("answerGuestQuery", params)
        return _parse_field(SentGuestMessage, data)

    async def send_live_photo(self, chat_id: int | str, live_photo: str | bytes | Path, **kwargs) -> Message:
        return await self._send_media("sendLivePhoto", "live_photo", chat_id, live_photo, **kwargs)

    async def get_user_personal_chat_messages(self, user_id: int) -> list[Message]:
        data = await self._request("getUserPersonalChatMessages", {"user_id": user_id})
        return [_parse_field(Message, item) for item in data]

    async def call_api(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        """Call any Bot API method by its official method name."""
        return await self._request(method, params, files=files)

    # ═══════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════

    async def _send_media(
        self, api_method: str, field_name: str,
        chat_id: int | str, media: str | bytes | Path,
        caption: str | None = None, parse_mode: str | None = None,
        reply_parameters: ReplyParameters | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
        filename: str | None = None,
        extra_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Message:
        p: dict[str, Any] = dict(extra_params or {})
        p.setdefault("chat_id", chat_id)
        if caption is not None:
            p["caption"] = caption
        if parse_mode is not None:
            p["parse_mode"] = parse_mode
        if message_thread_id is not None:
            p["message_thread_id"] = message_thread_id
        if reply_parameters is not None:
            p["reply_parameters"] = _serialize(reply_parameters)
        if reply_markup is not None:
            p["reply_markup"] = _serialize(reply_markup)
        p.update(kwargs)

        if isinstance(media, str):
            if media.startswith("http://") or media.startswith("https://"):
                p[field_name] = media
                return _parse_field(Message, await self._request(api_method, p))
            if not Path(media).exists():
                p[field_name] = media
                return _parse_field(Message, await self._request(api_method, p))

        if isinstance(media, (bytes, Path)) or (isinstance(media, str) and Path(media).exists()):
            media_bytes, fname = _resolve_media(media)
            name = filename or fname or f"{field_name}.dat"
            ct = _guess_mime(field_name, name)
            files = {field_name: (name, media_bytes, ct)}
            return _parse_field(Message, await self._request(api_method, p, files=files))
        raise TypeError(f"media must be file_id/URL str, bytes, or Path, got {type(media)}")


_GENERIC_BOT_API_METHODS = {
    "send_checklist": "sendChecklist",
    "get_user_profile_photos": "getUserProfilePhotos",
    "get_user_profile_audios": "getUserProfileAudios",
    "set_user_emoji_status": "setUserEmojiStatus",
    "set_chat_member_tag": "setChatMemberTag",
    "ban_chat_sender_chat": "banChatSenderChat",
    "unban_chat_sender_chat": "unbanChatSenderChat",
    "get_forum_topic_icon_stickers": "getForumTopicIconStickers",
    "unpin_all_general_forum_topic_messages": "unpinAllGeneralForumTopicMessages",
    "get_user_chat_boosts": "getUserChatBoosts",
    "replace_managed_bot_token": "replaceManagedBotToken",
    "set_my_profile_photo": "setMyProfilePhoto",
    "remove_my_profile_photo": "removeMyProfilePhoto",
    "gift_premium_subscription": "giftPremiumSubscription",
    "read_business_message": "readBusinessMessage",
    "delete_business_messages": "deleteBusinessMessages",
    "set_business_account_name": "setBusinessAccountName",
    "remove_business_account_profile_photo": "removeBusinessAccountProfilePhoto",
    "get_business_account_star_balance": "getBusinessAccountStarBalance",
    "transfer_business_account_stars": "transferBusinessAccountStars",
    "get_business_account_gifts": "getBusinessAccountGifts",
    "get_user_gifts": "getUserGifts",
    "get_chat_gifts": "getChatGifts",
    "convert_gift_to_stars": "convertGiftToStars",
    "upgrade_gift": "upgradeGift",
    "transfer_gift": "transferGift",
    "post_story": "postStory",
    "repost_story": "repostStory",
    "edit_story": "editStory",
    "delete_story": "deleteStory",
    "answer_web_app_query": "answerWebAppQuery",
    "save_prepared_inline_message": "savePreparedInlineMessage",
    "save_prepared_keyboard_button": "savePreparedKeyboardButton",
    "edit_message_checklist": "editMessageChecklist",
    "approve_suggested_post": "approveSuggestedPost",
    "decline_suggested_post": "declineSuggestedPost",
    "replace_sticker_in_set": "replaceStickerInSet",
    "get_my_star_balance": "getMyStarBalance",
    "edit_user_star_subscription": "editUserStarSubscription",
    "set_passport_data_errors": "setPassportDataErrors",
}


def _make_generic_api_method(api_method: str):
    async def generic(self: Bot, **params: Any) -> Any:
        return await self._request(api_method, params)

    generic.__name__ = api_method[0].lower() + "".join(
        f"_{c.lower()}" if c.isupper() else c for c in api_method[1:]
    )
    generic.__qualname__ = f"Bot.{generic.__name__}"
    generic.__doc__ = f"Call Telegram Bot API method {api_method}."
    return generic


for _python_name, _api_method in _GENERIC_BOT_API_METHODS.items():
    if not hasattr(Bot, _python_name):
        setattr(Bot, _python_name, _make_generic_api_method(_api_method))


# ─── Helper: resolve media to bytes + filename ──────


def _resolve_media(media: str | bytes | Path) -> tuple[bytes, str]:
    """Resolve media input to (bytes, filename)."""
    if isinstance(media, bytes):
        return media, ""
    if isinstance(media, Path):
        return media.read_bytes(), media.name
    if isinstance(media, str):
        p = Path(media)
        if p.exists():
            return p.read_bytes(), p.name
        return media.encode("utf-8"), ""
    return bytes(media), ""


# ─── Helper: determine ChatMember variant from status ──


def _chat_member_type(data: dict) -> type:
    status = data.get("status", "member")
    if status == "creator":
        from telegram._types import ChatMemberOwner
        return ChatMemberOwner
    elif status == "administrator":
        from telegram._types import ChatMemberAdministrator
        return ChatMemberAdministrator
    elif status == "member":
        from telegram._types import ChatMemberMember
        return ChatMemberMember
    elif status == "restricted":
        from telegram._types import ChatMemberRestricted
        return ChatMemberRestricted
    elif status == "left":
        from telegram._types import ChatMemberLeft
        return ChatMemberLeft
    elif status == "kicked":
        from telegram._types import ChatMemberBanned
        return ChatMemberBanned
    from telegram._types import ChatMemberMember
    return ChatMemberMember


def _menu_button_type(data: dict) -> type:
    btn_type = data.get("type", "default")
    if btn_type == "commands":
        from telegram._types import MenuButtonCommands
        return MenuButtonCommands
    elif btn_type == "web_app":
        from telegram._types import MenuButtonWebApp
        return MenuButtonWebApp
    from telegram._types import MenuButtonDefault
    return MenuButtonDefault


# ─── Serialize ────────────────────────────────


def _serialize(value: Any) -> Any:
    """Serialize a value for JSON transmission."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {f: _serialize(getattr(value, f)) for f in value.__dataclass_fields__ if getattr(value, f, None) is not None}
    return str(value)


def _serialize_form_value(value: Any) -> Any:
    """Serialize a value for multipart/form-data fields."""
    import json

    serialized = _serialize(value)
    if isinstance(serialized, (dict, list, tuple)):
        return json.dumps(serialized, separators=(",", ":"))
    if isinstance(serialized, bool):
        return "true" if serialized else "false"
    return serialized


_MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
    "ogg": "audio/ogg", "mp3": "audio/mpeg", "m4a": "audio/mp4",
    "wav": "audio/wav", "aac": "audio/aac",
    "pdf": "application/pdf", "zip": "application/zip",
}


def _guess_mime(field: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_MAP.get(ext, "application/octet-stream")
