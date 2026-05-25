# Native Telegram Bot API v10 SDK

This repository intentionally ships a repo-local `telegram/` package so nanobot can run without `python-telegram-bot`.

## Package Layout

| Path | Responsibility |
| --- | --- |
| `telegram/__init__.py` | Public exports for Bot API objects and the native `Bot` client. Provides lazy access to flexible placeholder types. |
| `telegram/constants.py` | Bot API version constants, currently `BOT_API_VERSION = "10.0"`. |
| `telegram/_bot.py` | Native async HTTPS client for `api.telegram.org`, typed helpers, generic method bridge, serialization, parsing, media upload handling. |
| `telegram/_types.py` | Bot API dataclasses plus `TelegramObject` fallback types for official names not yet modeled as strict dataclasses. |
| `telegram/_application.py` | Minimal `telegram.ext.Application`/`Updater` compatibility layer used by upstream nanobot. |
| `telegram/_handlers.py` | Message/callback handler compatibility using `Update.effective_message`, including v10 `guest_message` and `business_message`. |
| `telegram/_filters.py` | Filter combinators used by nanobot Telegram handlers. |
| `telegram/_context_types.py` | Callback context compatibility surface. |
| `telegram/request.py` | `HTTPXRequest` adapter accepting upstream PTB-style request kwargs while using `httpx.AsyncClient`. |
| `telegram/error.py` | Bot API error classes and HTTP status mapping. |
| `telegram/ext/__init__.py` | `telegram.ext` re-export surface for nanobot imports. |

## Runtime Patch

`nanobot_railway_patches/sitecustomize.py` is loaded via `PYTHONPATH` before nanobot starts. It:

- Forces the repo root onto `sys.path` so the local `telegram/` package wins.
- Adds bot-to-bot receive configuration fields to upstream `TelegramConfig`.
- Allows bot-origin senders when `botToBot` is enabled.
- Applies bot allowlist, rate limit, self-bot suppression, and chain-depth loop prevention.
- Bridges v10 `effective_message` updates into upstream nanobot's legacy `update.message` path.

## Verification

Use the aggregate verifier:

```powershell
.\.venv\Scripts\python.exe scripts\verify_all.py
```

The verifier proves local package/import behavior, official Bot API surface coverage, latest nanobot pin, offline gateway startup without `python-telegram-bot`, and live Telegram verifier readiness. Live Telegram delivery still requires `TELEGRAM_BOT_TOKEN` and BotFather bot-to-bot configuration.
