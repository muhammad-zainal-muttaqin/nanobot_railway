"""Message filters — PTB-compatible filter combinators.

Usage::
    filters.TEXT
    filters.PHOTO | filters.VIDEO
    (filters.TEXT | filters.PHOTO) & ~filters.COMMAND
    filters.Regex(r"^/start")
"""

from __future__ import annotations

import re
from typing import Any


class _Filter:
    def __call__(self, message: Any) -> bool:
        return self.check(message)

    def check(self, message: Any) -> bool:
        raise NotImplementedError

    def __invert__(self) -> _InvertedFilter:
        return _InvertedFilter(self)

    def __and__(self, other: _Filter) -> _AndFilter:
        return _AndFilter(self, other)

    def __or__(self, other: _Filter) -> _OrFilter:
        return _OrFilter(self, other)


class _InvertedFilter(_Filter):
    def __init__(self, inner: _Filter):
        self._inner = inner

    def check(self, message: Any) -> bool:
        return not self._inner.check(message)


class _AndFilter(_Filter):
    def __init__(self, *filters: _Filter):
        self._filters = filters

    def check(self, message: Any) -> bool:
        return all(f.check(message) for f in self._filters)


class _OrFilter(_Filter):
    def __init__(self, *filters: _Filter):
        self._filters = filters

    def check(self, message: Any) -> bool:
        return any(f.check(message) for f in self._filters)


class _TextFilter(_Filter):
    def check(self, message: Any) -> bool:
        text = getattr(message, "text", None)
        return bool(text)


class _PhotoFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "photo", None))


class _VideoFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "video", None))


class _VoiceFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "voice", None))


class _AudioFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "audio", None))


class _AnimationFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "animation", None))


class _VideoNoteFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "video_note", None))


class _DocumentFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "document", None))


class _LocationFilter(_Filter):
    def check(self, message: Any) -> bool:
        return bool(getattr(message, "location", None))


class _CommandFilter(_Filter):
    def check(self, message: Any) -> bool:
        text = getattr(message, "text", None) or getattr(message, "caption", None)
        return bool(text and text.startswith("/"))


class _RegexFilter(_Filter):
    def __init__(self, pattern: str | re.Pattern):
        self._pattern = re.compile(pattern) if isinstance(pattern, str) else pattern

    def check(self, message: Any) -> bool:
        text = getattr(message, "text", None) or getattr(message, "caption", None)
        return bool(text and self._pattern.search(text))


# ─── Filter instances ────────────────────────

TEXT = _TextFilter()
PHOTO = _PhotoFilter()
VIDEO = _VideoFilter()
VOICE = _VoiceFilter()
AUDIO = _AudioFilter()
ANIMATION = _AnimationFilter()
VIDEO_NOTE = _VideoNoteFilter()
DOCUMENT = _DocumentFilter()
LOCATION = _LocationFilter()
COMMAND = _CommandFilter()


def Regex(pattern: str | re.Pattern) -> _RegexFilter:
    return _RegexFilter(pattern)


class _Document:
    """Filters.Document namespace — matches ANY document by default."""
    ALL = DOCUMENT
    # Sub-filters could be added (PDF, IMAGE, etc.) — not needed for nanobot.


class _Filters:
    """Namespace: filters.TEXT, filters.PHOTO, filters.Document.ALL, etc."""
    TEXT = TEXT
    PHOTO = PHOTO
    VIDEO = VIDEO
    VOICE = VOICE
    AUDIO = AUDIO
    ANIMATION = ANIMATION
    VIDEO_NOTE = VIDEO_NOTE
    Document = _Document()
    LOCATION = LOCATION
    COMMAND = COMMAND
    Regex = staticmethod(Regex)


filters = _Filters()
