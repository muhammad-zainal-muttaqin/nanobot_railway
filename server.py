import asyncio
import base64
import json
import os
import re
import secrets
import signal
import time
from collections import deque
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from nanobot.config.loader import (
    load_config,
    save_config,
)
from nanobot.config.schema import Config

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
SECRET_FIELDS = {
    "api_key",
    "apiKey",
    "token",
    "botToken",
    "app_token",
    "appToken",
    "access_token",
    "accessToken",
    "refresh_token",
    "refreshToken",
    "client_secret",
    "clientSecret",
    "app_secret",
    "appSecret",
    "smtp_password",
    "smtpPassword",
    "imap_password",
    "imapPassword",
    "app_password",
    "appPassword",
    "secret",
    "claw_token",
    "clawToken",
    "encrypt_key",
    "encryptKey",
    "verification_token",
    "verificationToken",
}
CONFIG_PATH = Path.home() / ".nanobot" / "config.json"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

if not ADMIN_PASSWORD:
    ADMIN_PASSWORD = secrets.token_urlsafe(16)
    print(f"Generated admin password: {ADMIN_PASSWORD}")


class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "Authorization" not in conn.headers:
            return None

        auth = conn.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != "basic":
                return None
            decoded = base64.b64decode(credentials).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            raise AuthenticationError("Invalid credentials")

        username, _, password = decoded.partition(":")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return AuthCredentials(["authenticated"]), SimpleUser(username)

        raise AuthenticationError("Invalid credentials")


def require_auth(request: Request):
    if not request.user.is_authenticated:
        return PlainTextResponse(
            "Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="nanobot"'},
        )
    return None


class GatewayManager:
    def __init__(self):
        self.process: asyncio.subprocess.Process | None = None
        self.state = "stopped"
        self.logs: deque[str] = deque(maxlen=500)
        self.start_time: float | None = None
        self.restart_count = 0
        self._read_tasks: list[asyncio.Task] = []

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        self.state = "starting"
        self._cleanup_read_tasks()
        try:
            env = os.environ.copy()
            app_path = str(Path(__file__).parent)
            patch_path = str(Path(__file__).parent / "nanobot_railway_patches")
            native_paths = os.pathsep.join([app_path, patch_path])
            env["PYTHONPATH"] = (
                native_paths if not env.get("PYTHONPATH") else f"{native_paths}{os.pathsep}{env['PYTHONPATH']}"
            )
            self.process = await asyncio.create_subprocess_exec(
                "nanobot", "gateway",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            self.state = "running"
            self.start_time = time.time()
            task = asyncio.create_task(self._read_output())
            self._read_tasks.append(task)
        except Exception as e:
            self.state = "error"
            self.logs.append(f"Failed to start gateway: {e}")

    async def stop(self):
        if not self.process or self.process.returncode is not None:
            self.state = "stopped"
            self._cleanup_read_tasks()
            return
        self.state = "stopping"
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=10)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
        self.state = "stopped"
        self.start_time = None
        self._cleanup_read_tasks()

    async def restart(self):
        await self.stop()
        self.restart_count += 1
        await self.start()

    async def _read_output(self):
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                cleaned = ANSI_ESCAPE.sub("", decoded)
                self.logs.append(cleaned)
        except asyncio.CancelledError:
            return
        if self.process and self.process.returncode is not None and self.state == "running":
            self.state = "error"
            self.logs.append(f"Gateway exited with code {self.process.returncode}")
        self._cleanup_read_tasks()

    def _cleanup_read_tasks(self):
        self._read_tasks = [task for task in self._read_tasks if not task.done()]

    def get_status(self) -> dict:
        pid = None
        if self.process and self.process.returncode is None:
            pid = self.process.pid
        uptime = None
        if self.start_time and self.state == "running":
            uptime = int(time.time() - self.start_time)
        return {
            "state": self.state,
            "pid": pid,
            "uptime": uptime,
            "restart_count": self.restart_count,
        }


gateway = GatewayManager()
config_lock = asyncio.Lock()
gateway_start_lock = asyncio.Lock()


def mask_secrets(data, _path=""):
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if _is_secret_field(k) and isinstance(v, str) and v:
                result[k] = v[:8] + "***" if len(v) > 8 else "***"
            else:
                result[k] = mask_secrets(v, f"{_path}.{k}")
        return result
    if isinstance(data, list):
        return [mask_secrets(item, _path) for item in data]
    return data


def _is_secret_field(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", name.lower())
    if name in SECRET_FIELDS:
        return True
    return any(part in normalized for part in ("apikey", "token", "secret", "password"))


def _load_raw_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_raw_config(data: dict[str, Any]):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = dict(base)
        for key, value in overlay.items():
            result[key] = _deep_merge(result.get(key), value)
        return result
    return overlay


def _merged_config_data() -> dict:
    defaults = Config().model_dump(by_alias=True)
    loaded = load_config().model_dump(by_alias=True)
    raw = _load_raw_config()
    return _deep_merge(_deep_merge(defaults, loaded), raw)


def _collect_secret_values(data, field_name):
    values = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == field_name and isinstance(v, str):
                values.append(v)
            else:
                values.extend(_collect_secret_values(v, field_name))
    elif isinstance(data, list):
        for item in data:
            values.extend(_collect_secret_values(item, field_name))
    return values


def merge_secrets(new_data, existing_data):
    if isinstance(new_data, dict) and isinstance(existing_data, dict):
        result = {}
        for k, v in new_data.items():
            if _is_secret_field(k) and isinstance(v, str) and (v.endswith("***") or v == ""):
                result[k] = existing_data.get(k, "")
            else:
                result[k] = merge_secrets(v, existing_data.get(k, {}))
        return result
    return new_data


def _normalize_optional_empty_strings(data):
    nullable_paths = {
        ("agents", "defaults", "reasoningEffort"),
        ("channels", "transcriptionLanguage"),
        ("channels", "telegram", "proxy"),
        ("tools", "web", "proxy"),
        ("tools", "web", "userAgent"),
    }

    def walk(value, path=()):
        if isinstance(value, dict):
            return {k: walk(v, path + (k,)) for k, v in value.items()}
        if path in nullable_paths and value == "":
            return None
        return value

    return walk(data)


def _package_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None

def runtime_versions() -> dict:
    return {
        "nanobot_ai": _package_version("nanobot-ai"),
        "telegram_sdk": {
            "sdk": "native/v10",
            "api_version": "10.0",
            "release": "May 8, 2026",
            "support": (
                "Native Bot API v10 HTTP client \u2014 replaces python-telegram-bot entirely. "
                "Full Bot API 10.0 support: Guest Mode, Live Photos, Bot-to-Bot, "
                "deleteMessageReaction, deleteAllMessageReactions, sendMessageDraft, "
                "answerGuestQuery, sendLivePhoto, and more."
            ),
        },
        "railway_patch": {
            "telegram_bot_to_bot": True,
        },
    }


def _telegram_bot_to_bot_status(data: dict[str, Any]) -> dict[str, Any]:
    telegram_config = data.get("channels", {}).get("telegram", {})
    if not isinstance(telegram_config, dict):
        telegram_config = {}
    allow_bots = telegram_config.get("botToBotAllowBots") or telegram_config.get("bot_to_bot_allow_bots") or []
    return {
        "enabled": bool(telegram_config.get("botToBot") or telegram_config.get("bot_to_bot")),
        "allowlistCount": len(allow_bots) if isinstance(allow_bots, list) else 0,
        "maxPerMinute": telegram_config.get("botToBotMaxPerMinute")
        or telegram_config.get("bot_to_bot_max_per_minute")
        or 12,
        "maxChainDepth": telegram_config.get("botToBotMaxChainDepth")
        or telegram_config.get("bot_to_bot_max_chain_depth")
        or 6,
    }


async def homepage(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    await ensure_gateway_started()
    return templates.TemplateResponse(request, "index.html")


async def health(request: Request):
    await ensure_gateway_started()
    return JSONResponse({"status": "ok", "gateway": gateway.state})


async def api_config_get(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    data = _merged_config_data()
    return JSONResponse(mask_secrets(data))


async def api_config_put(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    try:
        restart = body.pop("_restartGateway", False)

        async with config_lock:
            existing_data = _merged_config_data()

            merged = merge_secrets(body, existing_data)
            merged = _normalize_optional_empty_strings(_deep_merge(existing_data, merged))

            try:
                new_config = Config.model_validate(merged)
            except Exception as e:
                err_msg = str(e)
                for field in SECRET_FIELDS:
                    for val in _collect_secret_values(merged, field):
                        if val and len(val) > 3:
                            err_msg = err_msg.replace(val, "***")
                return JSONResponse({"error": f"Validation error: {err_msg}"}, status_code=400)

            save_config(new_config)
            raw_config = cast(dict[str, Any], _deep_merge(new_config.model_dump(by_alias=True), merged))
            _write_raw_config(raw_config)

        if restart:
            asyncio.create_task(gateway.restart())

        return JSONResponse({"ok": True, "restarting": restart})
    except Exception as e:
        print(f"Config save error: {type(e).__name__}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_status(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err

    data = _merged_config_data()

    providers = {}
    for name, prov in data["providers"].items():
        if not isinstance(prov, dict):
            continue
        providers[name] = {"configured": bool(prov.get("apiKey") or prov.get("api_key"))}

    # ChannelsConfig mixes global fields (send_progress, …) with per-channel dicts (telegram, …).
    # Only dict-shaped entries represent actual channels with an "enabled" flag.
    channels = {}
    for name, chan in data["channels"].items():
        if not isinstance(chan, dict):
            continue
        if "enabled" not in chan:
            continue
        channels[name] = {"enabled": bool(chan.get("enabled", False))}

    cron_dir = Path.home() / ".nanobot" / "cron"
    cron_jobs = []
    if cron_dir.exists():
        for f in cron_dir.glob("*.json"):
            try:
                cron_jobs.append(json.loads(f.read_text()))
            except Exception:
                pass

    return JSONResponse({
        "gateway": gateway.get_status(),
        "versions": runtime_versions(),
        "telegramBotToBot": _telegram_bot_to_bot_status(data),
        "providers": providers,
        "channels": channels,
        "cron": {"count": len(cron_jobs), "jobs": cron_jobs},
    })


async def api_telegram_effective_config(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err

    data = _merged_config_data()
    telegram_config = data.get("channels", {}).get("telegram", {})
    if not isinstance(telegram_config, dict):
        telegram_config = {}
    visible = mask_secrets(telegram_config)
    return JSONResponse({
        "telegram": visible,
        "botToBot": _telegram_bot_to_bot_status(data),
    })


async def api_telegram_bot_to_bot_send(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    target = str(body.get("target", "")).strip()
    text = str(body.get("text", "")).strip()
    message_thread_id = body.get("messageThreadId")
    chain_depth = body.get("botToBotChainDepth")
    direct_bot_target = bool(re.fullmatch(r"@[A-Za-z0-9_]{5,32}", target))
    group_chat_target = bool(re.fullmatch(r"-?\d{5,32}", target))
    if not direct_bot_target and not group_chat_target:
        return JSONResponse({
            "error": "target must be a Telegram bot username like @OtherBot or a numeric group chat ID"
        }, status_code=400)
    if message_thread_id in ("", None):
        message_thread_id = None
    elif not re.fullmatch(r"\d{1,32}", str(message_thread_id).strip()):
        return JSONResponse({"error": "messageThreadId must be numeric when provided"}, status_code=400)
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    if len(text) > 4096:
        return JSONResponse({"error": "text must be 4096 characters or less"}, status_code=400)
    if chain_depth in ("", None):
        chain_depth = None
    elif not re.fullmatch(r"\d{1,4}", str(chain_depth).strip()):
        return JSONResponse({"error": "botToBotChainDepth must be numeric when provided"}, status_code=400)
    if chain_depth is not None:
        text = f"[nanobot:b2b-depth={int(str(chain_depth).strip())}] {text}"
        if len(text) > 4096:
            return JSONResponse({"error": "text with bot-to-bot chain marker must be 4096 characters or less"}, status_code=400)

    data = _merged_config_data()
    telegram_config = data.get("channels", {}).get("telegram", {})
    token = telegram_config.get("token")
    if not token or (isinstance(token, str) and token.endswith("***")):
        return JSONResponse({"error": "Telegram token is not configured"}, status_code=400)

    try:
        import httpx

        payload_json: dict[str, Any] = {"chat_id": target, "text": text}
        if message_thread_id is not None:
            payload_json["message_thread_id"] = int(str(message_thread_id).strip())
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload_json,
            )
        payload = response.json()
    except Exception as e:
        return JSONResponse({"error": f"Telegram request failed: {e}"}, status_code=502)

    if not payload.get("ok"):
        description = payload.get("description") or "Telegram rejected the request"
        return JSONResponse({"error": description, "telegram": payload}, status_code=400)

    return JSONResponse({
        "ok": True,
        "target": target,
        "messageId": payload.get("result", {}).get("message_id"),
        "messageThreadId": payload.get("result", {}).get("message_thread_id"),
        "botToBotChainDepth": int(str(chain_depth).strip()) if chain_depth is not None else None,
    })


async def api_logs(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    return JSONResponse({"lines": list(gateway.logs)})


async def api_gateway_start(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    asyncio.create_task(gateway.start())
    return JSONResponse({"ok": True})


async def api_gateway_stop(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    asyncio.create_task(gateway.stop())
    return JSONResponse({"ok": True})


async def api_gateway_restart(request: Request):
    auth_err = require_auth(request)
    if auth_err:
        return auth_err
    asyncio.create_task(gateway.restart())
    return JSONResponse({"ok": True})


async def auto_start_gateway():
    config = load_config()
    if config.get_api_key():
        await gateway.start()


async def ensure_gateway_started():
    # Railway template sometimes runs with Starlette versions that don't support
    # `on_startup` in Starlette(app=...). So we auto-start gateway lazily on
    # the first incoming request to authenticated pages / healthcheck.
    if gateway.state == "running":
        return
    async with gateway_start_lock:
        if gateway.state == "running":
            return
        await auto_start_gateway()


routes = [
    Route("/", homepage),
    Route("/health", health),
    Route("/api/config", api_config_get, methods=["GET"]),
    Route("/api/config", api_config_put, methods=["PUT"]),
    Route("/api/status", api_status),
    Route("/api/telegram/effective-config", api_telegram_effective_config),
    Route("/api/telegram/bot-to-bot/send", api_telegram_bot_to_bot_send, methods=["POST"]),
    Route("/api/logs", api_logs),
    Route("/api/gateway/start", api_gateway_start, methods=["POST"]),
    Route("/api/gateway/stop", api_gateway_stop, methods=["POST"]),
    Route("/api/gateway/restart", api_gateway_restart, methods=["POST"]),
]

app = Starlette(
    routes=routes,
    middleware=[Middleware(AuthenticationMiddleware, backend=BasicAuthBackend())],
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)

    def handle_signal():
        loop.create_task(gateway.stop())
        server.should_exit = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)

    loop.run_until_complete(server.serve())
