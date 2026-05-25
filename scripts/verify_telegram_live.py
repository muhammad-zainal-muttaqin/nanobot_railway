"""Live verification for the native Telegram Bot API v10 client.

Environment:
  TELEGRAM_BOT_TOKEN              Required for live checks.
  TELEGRAM_BOT_TO_BOT_TARGET      Optional @OtherBot username for sendMessage.
  TELEGRAM_GROUP_CHAT_ID          Optional numeric group chat ID for sendMessage.
  TELEGRAM_MESSAGE_THREAD_ID      Optional forum topic/thread id for group send.
  TELEGRAM_EXPECT_BOT_UPDATE_FROM Optional @BotUsername or numeric bot id to poll for.
  TELEGRAM_UPDATE_POLL_SECONDS    Optional poll window for inbound proof; default 20.
  TELEGRAM_REQUIRE_BOT_TO_BOT     Optional 1/true to require both send and receive proof.
"""

from __future__ import annotations

import asyncio
import importlib.metadata as metadata
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Bot
from telegram.constants import BOT_API_VERSION


def _ptb_installed() -> bool:
    try:
        metadata.version("python-telegram-bot")
    except metadata.PackageNotFoundError:
        return False
    return True


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


async def verify_live(env: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    env = env or os.environ
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    require_bot_to_bot = _truthy(env.get("TELEGRAM_REQUIRE_BOT_TO_BOT"))
    if not token:
        status = "failed" if require_bot_to_bot else "skipped"
        return 1 if require_bot_to_bot else 0, {
            "status": status,
            "reason": "TELEGRAM_BOT_TOKEN is not set",
            "bot_api_version": BOT_API_VERSION,
            "python_telegram_bot_installed": _ptb_installed(),
        }

    bot = Bot(token)
    try:
        me = await bot.get_me()
        raw_me = await bot.call_api("getMe")

        checks: dict[str, Any] = {
            "status": "ok",
            "bot_api_version": BOT_API_VERSION,
            "python_telegram_bot_installed": _ptb_installed(),
            "get_me": {
                "id": me.id,
                "username": me.username,
                "is_bot": me.is_bot,
                "supports_guest_queries": me.supports_guest_queries,
                "can_manage_bots": me.can_manage_bots,
            },
            "raw_getMe_ok": bool(raw_me.get("id") == me.id) if isinstance(raw_me, dict) else False,
        }

        target = env.get("TELEGRAM_BOT_TO_BOT_TARGET", "").strip()
        if target:
            sent = await bot.send_message(target, "native Bot API v10 live bot-to-bot verification")
            checks["bot_to_bot_send"] = {
                "target": target,
                "message_id": sent.message_id,
                "chat_id": sent.chat.id,
            }

        group_chat_id = env.get("TELEGRAM_GROUP_CHAT_ID", "").strip()
        if group_chat_id:
            params: dict[str, Any] = {}
            thread_id = env.get("TELEGRAM_MESSAGE_THREAD_ID", "").strip()
            if thread_id:
                params["message_thread_id"] = int(thread_id)
            sent = await bot.send_message(
                int(group_chat_id),
                "native Bot API v10 live group verification",
                **params,
            )
            checks["group_send"] = {
                "chat_id": sent.chat.id,
                "message_id": sent.message_id,
                "message_thread_id": getattr(sent, "message_thread_id", None),
            }

        expected_bot = env.get("TELEGRAM_EXPECT_BOT_UPDATE_FROM", "").strip()
        if expected_bot:
            timeout = float(env.get("TELEGRAM_UPDATE_POLL_SECONDS", "20") or 20)
            checks["bot_to_bot_receive"] = await _poll_for_bot_update(bot, expected_bot, timeout)
            if not checks["bot_to_bot_receive"]["matched"]:
                return 1, checks

        if require_bot_to_bot:
            missing = []
            if "bot_to_bot_send" not in checks:
                missing.append("TELEGRAM_BOT_TO_BOT_TARGET")
            if "bot_to_bot_receive" not in checks:
                missing.append("TELEGRAM_EXPECT_BOT_UPDATE_FROM")
            if missing:
                checks["status"] = "failed"
                checks["reason"] = "required bot-to-bot proof is incomplete"
                checks["missing"] = missing
                return 1, checks

        return 0, checks
    finally:
        await bot._close_client()


def _matches_expected_bot(user: Any, expected: str) -> bool:
    expected = expected.strip()
    if not expected or user is None or not getattr(user, "is_bot", False):
        return False
    username = getattr(user, "username", None)
    user_id = str(getattr(user, "id", ""))
    normalized = expected.removeprefix("@").lower()
    return user_id == expected or bool(username and username.lower() == normalized)


async def _poll_for_bot_update(bot: Bot, expected: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    offset: int | None = None
    seen = 0
    while time.monotonic() < deadline:
        updates = await bot.get_updates(
            offset=offset,
            timeout=2,
            allowed_updates=["message", "business_message", "guest_message"],
        )
        for update in updates:
            seen += 1
            offset = update.update_id + 1
            user = update.effective_user
            if _matches_expected_bot(user, expected):
                message = update.effective_message
                return {
                    "matched": True,
                    "expected": expected,
                    "update_id": update.update_id,
                    "sender_id": getattr(user, "id", None),
                    "sender_username": getattr(user, "username", None),
                    "message_id": getattr(message, "message_id", None),
                    "chat_id": getattr(getattr(message, "chat", None), "id", None),
                }
        await asyncio.sleep(0.5)
    return {"matched": False, "expected": expected, "updates_seen": seen, "timeout_seconds": timeout}


def _print_report(report: dict[str, Any]) -> None:
    for key, value in report.items():
        print(f"{key}={value}")


def main() -> int:
    try:
        code, report = asyncio.run(verify_live())
    except Exception as exc:
        print(f"status=failed")
        print(f"error={type(exc).__name__}: {exc}")
        return 1
    _print_report(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
