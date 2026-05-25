"""PTB-compatible callback context stub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CallbackContext:
    application: Any = None
    error: Exception | None = None
    bot_data: dict = field(default_factory=dict)
    user_data: dict = field(default_factory=dict)
    chat_data: dict = field(default_factory=dict)
    args: list[str] | None = None


class ContextTypes:
    DEFAULT_TYPE = CallbackContext
