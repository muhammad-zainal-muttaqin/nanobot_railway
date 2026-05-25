![Nanobot](https://github.com/HKUDS/nanobot/raw/main/nanobot_logo.png)

# Nanobot Railway Wrapper

This repository is a lightweight Railway deployment wrapper for [HKUDS/nanobot](https://github.com/HKUDS/nanobot). It does not vendor the upstream nanobot source code. The Docker image installs the published `nanobot-ai` package, then runs a small Starlette admin dashboard for Railway-friendly configuration, status, logs, and gateway process control.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/nanobot-4?referralCode=asepsp&utm_medium=integration&utm_source=template&utm_campaign=generic)

## Current Fork Status

This fork is patched for the upstream stable package:

* `nanobot-ai==0.2.0`
* A repo-local native `telegram/` package that talks directly to Telegram Bot API v10 over HTTPS.
* Starlette, Uvicorn, Jinja2, and python-multipart are bounded below the next major version for more reproducible Railway builds.

Because this repository is a wrapper, upstream core behavior is updated by changing the installed `nanobot-ai` package version in the `Dockerfile`, not by merging upstream Python source files into this repo.

## What This Fork Adds

Compared with a plain `nanobot-ai` install, this Railway wrapper provides:

* Basic Auth protected web dashboard.
* Lazy gateway startup on `/` and `/health`, useful for Railway deployments.
* Persistent config under `/data/.nanobot` by setting `HOME=/data`.
* Masked config API, so secrets shown by `GET /api/config` can be posted back without erasing the real stored values.
* Config merge behavior that keeps upstream 0.2.0 defaults while preserving older local config, masked secrets, and unknown/plugin channel or provider blocks.
* `/api/status` version reporting for installed `nanobot-ai`, native Telegram SDK state, gateway state, configured providers, enabled channels, and cron jobs.
* Dashboard controls for additional upstream 0.2.0 fields, including more providers, Telegram options, channel defaults, agent defaults, and tools settings.
* A runtime Telegram patch loaded through `PYTHONPATH=/app:/app/nanobot_railway_patches`, so the gateway subprocess uses the native Bot API v10 package and can accept bot senders when bot-to-bot mode is enabled without vendoring nanobot core source.
* A raw Bot API `sendMessage` endpoint and dashboard control to send a private bot message to `@OtherBot`, or a group test message to a numeric Telegram chat ID.
* The gateway subprocess is launched with the repository root first on `PYTHONPATH`, then `nanobot_railway_patches`, so upstream nanobot imports the native `telegram/` package even when run through the `nanobot gateway` console entry point.

## Telegram Bot API 10 Note

Telegram Bot API 10.0 introduced bot-to-bot communication. Telegram's public guide says:

* In groups, bots can receive messages from other bots through command mentions such as `/ping@OtherBot` or direct replies to a bot message; broader receipt requires Bot-to-Bot Communication Mode plus admin rights or disabled group privacy.
* In private chats, a bot can send to another bot by passing the recipient `@username` to `sendMessage`.
* Private bot-to-bot messaging requires Bot-to-Bot Communication Mode to be enabled for both sender and recipient in BotFather.
* Loop prevention is required.

This wrapper now implements the nanobot-side transport needed for those flows:

* `channels.telegram.botToBot` enables processing inbound Telegram messages whose sender is a bot.
* `channels.telegram.botToBotAllowBots` optionally restricts bot senders by `@username` or numeric bot ID.
* `channels.telegram.botToBotMaxPerMinute` rate-limits bot-origin messages to reduce accidental loops.
* The runtime patch applies bot allowlisting to both normal messages and Telegram command messages, so `/command@ThisBot` from another bot is no longer dropped by the older human-only allowlist path.
* The dashboard can send a private bot-to-bot test message or a group mention test through `POST /api/telegram/bot-to-bot/send`, including an optional bot-to-bot chain-depth marker for loop-prevention tests.

The native package reports `telegram.constants.BOT_API_VERSION == "10.0"` and includes regression tests that `Bot.send_message("@OtherBot", "text")` passes the bot username as `chat_id`, `sendMessageDraft` accepts empty text, guest/business messages dispatch through nanobot handlers, and the Railway patch resolves `telegram` to the repo-local package instead of the installed `python-telegram-bot` dependency.
The native method surface has also been audited against Telegram's current Bot API page: all 176 official method names have a coroutine entry point, and all 303 official type names are importable from `telegram`. Types that are not yet modeled as strict dataclasses use a flexible `TelegramObject` placeholder so raw API responses remain accessible while typed models are added incrementally.
The native package layout is documented in `docs/native_telegram_sdk.md`.

The dashboard and `/api/status` expose this clearly:

* Existing Telegram long-polling bot behavior remains supported through nanobot upstream using the local native SDK.
* The reported Telegram SDK is `native/v10` with target Bot API 10.0.
* Bot-to-bot receive/send controls are exposed. Guest Mode, managed-bot settings, live photos, and other v10 methods are represented in the native package surface and continue to be audited against Telegram's official API.

## Requirements

For Railway deployment:

* Railway account.
* Railway persistent volume mounted at `/data`.

For local container testing:

* Docker.

For local Python-only checks:

* Python 3.12 or newer is recommended.
* A virtual environment can install `nanobot-ai==0.2.0` and this wrapper's `requirements.txt`.

## Deploy on Railway

1. Deploy this template on Railway.
2. Attach a persistent volume mounted to `/data`.
3. Set admin credentials:

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-strong-password
```

If `ADMIN_PASSWORD` is not set, the server generates a random password at startup and prints it to logs. For production, set it explicitly.

Railway builds the image with `Dockerfile` and starts `/app/start.sh`.

## Configure Providers

1. Open your Railway public URL.
2. Log in with Basic Auth.
3. Go to **AI Providers**.
4. Add at least one API key.
5. Choose a provider/model or leave provider selection on `auto`.
6. Save changes.

![AI Providers tab](./img/ai_providers.png)

The dashboard includes upstream 0.2.0 provider slots such as Anthropic, OpenAI, OpenRouter, Gemini, Groq, DeepSeek, Zhipu, vLLM, Azure OpenAI, Bedrock, Hugging Face, DashScope, Ollama, LM Studio, Moonshot, MiniMax, Mistral, SiliconFlow, Volcengine, BytePlus, Qianfan, NVIDIA, and related compatible providers.

## Configure Telegram

1. Go to **Channels**.
2. Enable Telegram.
3. Paste your BotFather token.
4. Set allowed users:

```text
*
```

or a comma-separated list of Telegram user IDs.

![Channels tab](./img/channels.png)

Additional Telegram settings exposed by this fork include group policy, streaming, inline keyboards, reply behavior, reaction emoji, connection pool size, pool timeout, stream edit interval, and proxy.

### Bot-to-Bot Setup

1. In BotFather, enable Bot-to-Bot Communication Mode for this bot.
2. Enable Bot-to-Bot Communication Mode for the other bot as well if you want private bot-to-bot messages.
3. In this dashboard, enable **Bot-to-bot receive mode** under Telegram.
4. Set **Allowed Bots** to `*`, or list trusted bot usernames/IDs such as `@OtherBot`.
5. Save and restart the gateway.
6. Use the Telegram bot-to-bot send controls to send a direct test message to `@OtherBot`.

For group communication, add both bots to the same group and prefer command mentions such as `/ping@OtherBot hi` or direct replies to the receiving bot's message. Plain text mentions like `@OtherBot hi` are handled if Telegram delivers the update, but command mentions and replies are the Bot API 10 path to test first. The dashboard target field also accepts a numeric group chat ID such as `-1001234567890`; use the optional topic ID field for forum topics. For unattended multi-agent loops, keep `botToBotMaxPerMinute` conservative.

## Start and Monitor

Use the dashboard footer buttons to start, stop, or restart the gateway. The Overview page shows provider/channel counts and installed package versions.

![Overview tab](./img/overview.png)

Use the Logs tab if the bot does not respond.

![Logs](./img/logs.png)

Common checks:

* At least one provider API key is configured.
* Telegram token is valid.
* Telegram allowed users include your user ID or `*`.
* Gateway is running.
* Logs do not show provider authentication or validation errors.

## Endpoints

* `GET /` - Admin dashboard, Basic Auth protected.
* `GET /health` - Railway healthcheck.
* `GET /api/config` - Read merged config with secrets masked.
* `PUT /api/config` - Save config, preserving masked secrets.
* `GET /api/status` - Gateway state, package versions, providers, channels, cron jobs.
* `GET /api/telegram/effective-config` - Read effective Telegram config with secrets masked, including bot-to-bot status.
* `POST /api/telegram/bot-to-bot/send` - Send a raw Bot API `sendMessage` request from the configured Telegram bot token to a target `@BotUsername` or numeric group chat ID.
* `GET /api/logs` - Recent gateway logs.
* `POST /api/gateway/start` - Start gateway.
* `POST /api/gateway/stop` - Stop gateway.
* `POST /api/gateway/restart` - Restart gateway.

## Local Verification

Without Docker, you can still run the Python checks:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip pytest "nanobot-ai==0.2.0" -r requirements.txt
.\.venv\Scripts\python.exe -m pip uninstall -y python-telegram-bot
.\.venv\Scripts\python.exe -m compileall telegram server.py nanobot_railway_patches scripts tests
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe scripts\verify_nanobot_latest.py
.\.venv\Scripts\python.exe scripts\audit_telegram_api_surface.py
.\.venv\Scripts\python.exe scripts\verify_gateway_offline.py
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
$env:PYTHONPATH="$PWD;$PWD\nanobot_railway_patches"
.\.venv\Scripts\python.exe -c "from nanobot.channels.telegram import TelegramChannel; import telegram; print(telegram.__file__)"
```

Or run all local gates together:

```powershell
.\.venv\Scripts\python.exe scripts\verify_all.py
```

`scripts\verify_gateway_offline.py` starts `nanobot gateway` with a temporary config, no enabled chat channels, and a dummy provider key; it succeeds if the gateway reaches runtime without importing `python-telegram-bot`.

`scripts\verify_telegram_live.py` skips cleanly without credentials. For live Telegram proof, set `TELEGRAM_BOT_TOKEN`; set `TELEGRAM_BOT_TO_BOT_TARGET=@OtherBot` after enabling Bot-to-Bot Communication Mode for both bots in BotFather to test private bot-to-bot delivery. To prove receive-side bot-to-bot delivery, set `TELEGRAM_EXPECT_BOT_UPDATE_FROM=@OtherBot`, send a message from that bot to this bot, and run the verifier within `TELEGRAM_UPDATE_POLL_SECONDS`. For the final bot-to-bot proof, also set `TELEGRAM_GROUP_CHAT_ID` and `TELEGRAM_REQUIRE_BOT_TO_BOT=1`; the verifier will fail unless private send, receive, and group/topic evidence are present.
The full live verification runbook is in `docs/live_telegram_verification.md`.

For container verification on a machine with Docker:

```powershell
docker build -t nanobot-railway .
docker run --rm --entrypoint python nanobot-railway -c "import telegram, importlib.metadata as m; print(telegram.__file__); print(next((d.version for d in m.distributions() if d.metadata['Name']=='python-telegram-bot'), 'python-telegram-bot not installed'))"
docker run --rm -p 8080:8080 -e PORT=8080 -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=admin -v nanobot-data:/data nanobot-railway
```

Then open `http://localhost:8080`.
