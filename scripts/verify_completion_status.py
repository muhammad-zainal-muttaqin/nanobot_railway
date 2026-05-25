"""Summarize objective completion status for the Telegram Bot API v10 work."""

from __future__ import annotations

import importlib.metadata as metadata
import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram.constants import BOT_API_VERSION


def _ptb_installed() -> bool:
    try:
        metadata.version("python-telegram-bot")
    except metadata.PackageNotFoundError:
        return False
    return True


def _file_contains(path: str, needle: str) -> bool:
    return needle in (PROJECT_ROOT / path).read_text(encoding="utf-8")


def completion_items(env: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    env = env or os.environ
    has_token = bool(env.get("TELEGRAM_BOT_TOKEN", "").strip())
    has_strict_b2b_env = all(
        env.get(name, "").strip()
        for name in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_BOT_TO_BOT_TARGET",
            "TELEGRAM_EXPECT_BOT_UPDATE_FROM",
            "TELEGRAM_GROUP_CHAT_ID",
        )
    )
    docker_available = shutil.which("docker") is not None

    return [
        ("bot_api_version", "proven" if BOT_API_VERSION == "10.0" else "missing", BOT_API_VERSION),
        (
            "native_telegram_package",
            "proven" if (PROJECT_ROOT / "telegram" / "_bot.py").exists() else "missing",
            "telegram/_bot.py",
        ),
        (
            "python_telegram_bot_absent",
            "proven" if not _ptb_installed() else "missing",
            "python-telegram-bot not installed" if not _ptb_installed() else "python-telegram-bot installed",
        ),
        (
            "nanobot_latest_pin",
            "proven" if _file_contains("Dockerfile", '"nanobot-ai==0.2.0"') else "missing",
            "Dockerfile nanobot-ai==0.2.0",
        ),
        (
            "native_package_in_docker",
            "proven" if _file_contains("Dockerfile", "COPY telegram/ /app/telegram/") else "missing",
            "Dockerfile COPY telegram/",
        ),
        (
            "bot_to_bot_runtime_patch",
            "proven" if _file_contains("nanobot_railway_patches/sitecustomize.py", "bot_to_bot") else "missing",
            "nanobot_railway_patches/sitecustomize.py",
        ),
        (
            "strict_live_bot_to_bot_gate",
            "proven" if _file_contains("scripts/verify_telegram_live.py", "TELEGRAM_REQUIRE_BOT_TO_BOT") else "missing",
            "scripts/verify_telegram_live.py",
        ),
        (
            "live_token_available",
            "external" if not has_token else "ready",
            "TELEGRAM_BOT_TOKEN set" if has_token else "TELEGRAM_BOT_TOKEN not set",
        ),
        (
            "strict_live_bot_to_bot_env",
            "external" if not has_strict_b2b_env else "ready",
            "target, expected sender, and group set" if has_strict_b2b_env else "target/sender/group/token incomplete",
        ),
        (
            "docker_runtime_available",
            "external" if not docker_available else "ready",
            "docker found" if docker_available else "docker not found",
        ),
    ]


def main() -> int:
    items = completion_items()
    strict = os.environ.get("COMPLETION_STATUS_STRICT", "").strip().lower() in {"1", "true", "yes", "on"}
    incomplete = False
    for name, status, detail in items:
        print(f"{name}={status} detail={detail}")
        if status in {"missing", "external"}:
            incomplete = True
    return 1 if strict and incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
