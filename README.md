![Nanobot](https://github.com/HKUDS/nanobot/raw/main/nanobot_logo.png)

# Nanobot Railway Wrapper

This repository is a lightweight Railway deployment wrapper for [HKUDS/nanobot](https://github.com/HKUDS/nanobot). It does not vendor the upstream nanobot source code. The Docker image installs the published `nanobot-ai` package, then runs a small Starlette admin dashboard for Railway-friendly configuration, status, logs, and gateway process control.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/nanobot-4?referralCode=asepsp&utm_medium=integration&utm_source=template&utm_campaign=generic)

## Current Fork Status

This fork is patched for the upstream stable package:

* `nanobot-ai==0.2.0`
* `python-telegram-bot[socks]==22.7`
* Starlette, Uvicorn, Jinja2, and python-multipart are bounded below the next major version for more reproducible Railway builds.

Because this repository is a wrapper, upstream core behavior is updated by changing the installed `nanobot-ai` package version in the `Dockerfile`, not by merging upstream Python source files into this repo.

## What This Fork Adds

Compared with a plain `nanobot-ai` install, this Railway wrapper provides:

* Basic Auth protected web dashboard.
* Lazy gateway startup on `/` and `/health`, useful for Railway deployments.
* Persistent config under `/data/.nanobot` by setting `HOME=/data`.
* Masked config API, so secrets shown by `GET /api/config` can be posted back without erasing the real stored values.
* Config merge behavior that keeps upstream 0.2.0 defaults while preserving older local config, masked secrets, and unknown/plugin channel or provider blocks.
* `/api/status` version reporting for installed `nanobot-ai`, installed `python-telegram-bot`, gateway state, configured providers, enabled channels, and cron jobs.
* Dashboard controls for additional upstream 0.2.0 fields, including more providers, Telegram options, channel defaults, agent defaults, and tools settings.

## Telegram Bot API 10 Note

Telegram Bot API 10.0 was released after the currently pinned Telegram wrapper support level. This fork pins `python-telegram-bot==22.7`, which is the latest compatible wrapper found during the update work, but it should not be treated as full Bot API 10 support.

The dashboard and `/api/status` expose this clearly:

* Existing Telegram long-polling bot behavior remains supported through nanobot upstream.
* Bot API 10-only features are not exposed as supported.
* A raw HTTP Bot API 10 compatibility adapter is not included, because the existing chat bot flow does not require Bot API 10-only features.

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
* `GET /api/logs` - Recent gateway logs.
* `POST /api/gateway/start` - Start gateway.
* `POST /api/gateway/stop` - Stop gateway.
* `POST /api/gateway/restart` - Restart gateway.

## Local Verification

Without Docker, you can still run the Python checks:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "nanobot-ai==0.2.0" "python-telegram-bot[socks]==22.7" -r requirements.txt
.\.venv\Scripts\python.exe -m py_compile server.py
.\.venv\Scripts\python.exe -m mypy server.py --ignore-missing-imports --check-untyped-defs --show-error-codes
.\.venv\Scripts\python.exe -m pyright server.py
```

For container verification on a machine with Docker:

```powershell
docker build -t nanobot-railway .
docker run --rm -p 8080:8080 -e PORT=8080 -e ADMIN_USERNAME=admin -e ADMIN_PASSWORD=admin -v nanobot-data:/data nanobot-railway
```

Then open `http://localhost:8080`.
