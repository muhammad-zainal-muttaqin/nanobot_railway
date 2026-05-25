# Telegram Bot API v10 Completion Audit

Current status: locally implemented and verified; private live bot-to-bot proof passed on May 25, 2026. Group/topic live proof and Docker image build/run remain external.

## Requirements And Evidence

| Requirement | Evidence | Status |
| --- | --- | --- |
| Use latest published `nanobot-ai` | `scripts/verify_nanobot_latest.py` checks PyPI and the Dockerfile pin; current result is `pinned=0.2.0`, `latest=0.2.0`, `status=ok`. | Proven by live PyPI audit |
| Target the May 8, 2026 Bot API 10.0 release | `scripts/audit_telegram_api_surface.py` verifies Telegram's official Bot API page contains both `May 8, 2026` and `Bot API 10.0`. | Proven by live-doc audit |
| Do not use `python-telegram-bot` wrapper | Dockerfile uninstalls `python-telegram-bot`; local venv check reports `python-telegram-bot not installed`; tests assert the distribution is absent. | Proven locally |
| Provide native Telegram Bot API v10 package | Repo contains `telegram/` native HTTP client, types, `telegram.ext` compatibility layer, request adapter, errors, and constants. | Proven locally |
| Organize native SDK files/folders | `docs/native_telegram_sdk.md` documents ownership for `telegram/`, `telegram/ext/`, and `nanobot_railway_patches/sitecustomize.py`. | Proven locally |
| Match current Telegram Bot API method/type surface | `scripts/audit_telegram_api_surface.py` checks Telegram's official Bot API page and currently reports `method_missing=0`, `type_import_missing=0`. | Proven locally, network-dependent |
| Preserve recent Bot API 10 fields and method parameters | `scripts/audit_telegram_api_surface.py` now verifies curated May 8, 2026 and adjacent 2026 field/parameter requirements; current result is `recent_field_missing=0`, `recent_method_parameter_missing=0`. | Proven locally |
| Support Bot API 10 bot-to-bot send path | Native `Bot.send_message("@OtherBot", "...")` regression test proves `@BotUsername` is passed as `chat_id`; dashboard raw send endpoint remains available and can attach optional bot-to-bot chain-depth markers; live-doc audit verifies Telegram's Bot-to-Bot Communication docs are present. | Proven locally |
| Support bot-origin inbound handling in nanobot | Runtime patch allows bot senders when `botToBot` is enabled, bridges `effective_message` into upstream nanobot's legacy `update.message` path, and tests bot-origin `guest_message`, `business_message`, and slash-command forwarding into the inbound bus. | Proven locally |
| Prevent bot-to-bot loops locally | Tests prove allowlist enforcement, per-bot rate limiting via `botToBotMaxPerMinute`, self-bot suppression, optional `[nanobot:b2b-depth=N]` marker stripping/metadata, and drop behavior at `botToBotMaxChainDepth`. | Proven locally |
| Ensure nanobot gateway uses native `telegram/` package | Gateway subprocess prepends repo root and patch dir to `PYTHONPATH`; tests verify path order; runtime tests verify `telegram.__file__` resolves to repo-local package. | Proven locally |
| Prove nanobot gateway starts without PTB | `scripts/verify_gateway_offline.py` starts real `nanobot gateway` with temporary config, reaches tool registration, and reports PTB absent. | Proven locally |
| Prove live Telegram API connectivity | `scripts/verify_telegram_live.py` verified `getMe` with `@grokinclaw_bot` on May 25, 2026. The token was not stored in the repository and must be rotated after testing. | Proven live |
| Prove private bot-to-bot delivery through Telegram | On May 25, 2026, `@grokinclaw_bot` successfully sent private bot-to-bot messages to `@AkuHolo_bot` and `@S_o_R_a_bot`, then received bot-origin updates back from both bots. | Proven live |
| Prove group/topic bot-to-bot delivery through Telegram | Requires `TELEGRAM_GROUP_CHAT_ID` as a negative group/supergroup ID, optional `TELEGRAM_MESSAGE_THREAD_ID`, both bots in the group, and Bot-to-Bot Communication Mode enabled in BotFather. | Missing external group/topic ID |
| Prove Docker image behavior | Manifest tests verify Dockerfile copies native package, uninstalls PTB, and sets `PYTHONPATH`; Docker is not installed in this environment, so image build/run is not locally proven. | Partially proven |

## Verification Commands

```powershell
.\.venv\Scripts\python.exe scripts\verify_all.py
```

Equivalent individual commands:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m compileall telegram server.py nanobot_railway_patches scripts tests
.\.venv\Scripts\python.exe scripts\verify_nanobot_latest.py
.\.venv\Scripts\python.exe scripts\audit_telegram_api_surface.py
.\.venv\Scripts\python.exe scripts\verify_gateway_offline.py
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```

Expected local results without Telegram credentials:

```text
pytest: all tests pass
compileall: no compile failures
verify_nanobot_latest.py: status=ok
audit_telegram_api_surface.py: method_missing=0, type_import_missing=0
audit_telegram_api_surface.py: release_marker=ok, bot_to_bot_docs=ok
audit_telegram_api_surface.py: recent_field_missing=0, recent_method_parameter_missing=0
verify_gateway_offline.py: status='ok', python_telegram_bot_installed=False
verify_telegram_live.py: status=skipped, reason=TELEGRAM_BOT_TOKEN is not set
```

## Live Completion Gate

Detailed live verification steps are documented in `docs/live_telegram_verification.md`.

To prove the remaining live requirement, run:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_BOT_TO_BOT_TARGET="@OtherBot"
$env:TELEGRAM_EXPECT_BOT_UPDATE_FROM="@OtherBot"
$env:TELEGRAM_GROUP_CHAT_ID="-1001234567890"
$env:TELEGRAM_UPDATE_POLL_SECONDS="20"
$env:TELEGRAM_REQUIRE_BOT_TO_BOT="1"
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```

For forum topic verification, also set:

```powershell
$env:TELEGRAM_GROUP_CHAT_ID="-1001234567890"
$env:TELEGRAM_MESSAGE_THREAD_ID="123"
```

Full production completion can be claimed only after the live verifier returns `status=ok` with real Telegram credentials, private bot-to-bot proof, and group/topic proof.
