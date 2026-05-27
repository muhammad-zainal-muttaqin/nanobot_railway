import asyncio
import base64
import copy
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
RUNTIME_CONFIG_PATH = CONFIG_PATH.with_name("runtime_config.json")

PROVIDER_API_KEY_ENV = {
    "AIHUBMIX_API_KEY": "aihubmix",
    "ANTHROPIC_API_KEY": "anthropic",
    "AZURE_OPENAI_API_KEY": "azureOpenai",
    "BEDROCK_API_KEY": "bedrock",
    "BYTEPLUS_API_KEY": "byteplus",
    "DASHSCOPE_API_KEY": "dashscope",
    "DEEPSEEK_API_KEY": "deepseek",
    "GEMINI_API_KEY": "gemini",
    "GOOGLE_API_KEY": "gemini",
    "GROQ_API_KEY": "groq",
    "HUGGINGFACE_API_KEY": "huggingface",
    "MINIMAX_API_KEY": "minimax",
    "MISTRAL_API_KEY": "mistral",
    "MOONSHOT_API_KEY": "moonshot",
    "NVIDIA_API_KEY": "nvidia",
    "OPENAI_API_KEY": "openai",
    "OPENROUTER_API_KEY": "openrouter",
    "QIANFAN_API_KEY": "qianfan",
    "SILICONFLOW_API_KEY": "siliconflow",
    "VOLCENGINE_API_KEY": "volcengine",
    "ZHIPU_API_KEY": "zhipu",
}

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
        self._lifecycle_lock = asyncio.Lock()

    async def start(self):
        async with self._lifecycle_lock:
            await self._start_locked()

    async def _start_locked(self):
        if self.process and self.process.returncode is None:
            return
        self.state = "starting"
        self._cleanup_read_tasks()
        try:
            env = os.environ.copy()
            runtime_config = _merged_config_data()
            _write_runtime_config(runtime_config)
            app_path = str(Path(__file__).parent)
            patch_path = str(Path(__file__).parent / "nanobot_railway_patches")
            native_paths = os.pathsep.join([app_path, patch_path])
            env["PYTHONPATH"] = (
                native_paths if not env.get("PYTHONPATH") else f"{native_paths}{os.pathsep}{env['PYTHONPATH']}"
            )
            self.process = await asyncio.create_subprocess_exec(
                "nanobot", "gateway", "--config", str(RUNTIME_CONFIG_PATH),
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
        async with self._lifecycle_lock:
            await self._stop_locked()

    async def _stop_locked(self):
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
        async with self._lifecycle_lock:
            await self._stop_locked()
            self.restart_count += 1
            await self._start_locked()

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


def _redact_telegram_token(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {key: _redact_telegram_token(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_telegram_token(item, token) for item in value]
    if isinstance(value, str):
        text = value.replace(token, "<redacted-token>") if token else value
        return re.sub(r"/bot[^/\s]+/", "/bot<redacted-token>/", text)
    return value


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


def _write_runtime_config(data: dict[str, Any]):
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = dict(base)
        for key, value in overlay.items():
            result[key] = _deep_merge(result.get(key), value)
        return result
    return overlay


def _set_config_path_value(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[path[-1]] = value


def _parse_bool_env(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _parse_int_env(name: str, value: str) -> int:
    if not re.fullmatch(r"-?\d{1,32}", value.strip()):
        raise ValueError(f"{name} must be numeric")
    return int(value)


def _parse_list_env(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("list env value must be a JSON array")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in stripped.split(",") if item.strip()]


def _parse_config_env_value(value: str) -> Any:
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered == "null":
        return None
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if stripped.startswith(("{", "[")):
        return json.loads(stripped)
    return value


def _env_path_segment(value: str) -> str:
    if value.isupper():
        parts = value.lower().split("_")
        return parts[0] + "".join(part.title() for part in parts[1:])
    return value


def _apply_generic_nanobot_env(data: dict[str, Any], env: dict[str, str]) -> None:
    for name, value in env.items():
        if value == "":
            continue
        if name.startswith("NANOBOT_CONFIG__"):
            suffix = name.removeprefix("NANOBOT_CONFIG__")
        elif name.startswith("NANOBOT_") and "__" in name:
            suffix = name.removeprefix("NANOBOT_")
        else:
            continue
        path = tuple(_env_path_segment(part) for part in suffix.split("__") if part)
        if path:
            _set_config_path_value(data, path, _parse_config_env_value(value))


def _apply_env_overrides(data: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    if env is None:
        env = os.environ
    result = copy.deepcopy(data)

    _apply_generic_nanobot_env(result, env)

    for env_name, provider_name in PROVIDER_API_KEY_ENV.items():
        value = env.get(env_name, "").strip()
        if value:
            _set_config_path_value(result, ("providers", provider_name, "apiKey"), value)

    telegram_token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if telegram_token:
        _set_config_path_value(result, ("channels", "telegram", "token"), telegram_token)

    telegram_bool_paths = {
        "TELEGRAM_ENABLED": ("channels", "telegram", "enabled"),
        "TELEGRAM_BOT_TO_BOT": ("channels", "telegram", "botToBot"),
        "TELEGRAM_BOT_TO_BOT_ENABLED": ("channels", "telegram", "botToBot"),
    }
    for env_name, path in telegram_bool_paths.items():
        value = env.get(env_name)
        if value not in (None, ""):
            _set_config_path_value(result, path, _parse_bool_env(env_name, value))

    telegram_int_paths = {
        "TELEGRAM_BOT_TO_BOT_MAX_PER_MINUTE": ("channels", "telegram", "botToBotMaxPerMinute"),
        "TELEGRAM_BOT_TO_BOT_MAX_CHAIN_DEPTH": ("channels", "telegram", "botToBotMaxChainDepth"),
    }
    for env_name, path in telegram_int_paths.items():
        value = env.get(env_name)
        if value not in (None, ""):
            _set_config_path_value(result, path, _parse_int_env(env_name, value))

    telegram_list_paths = {
        "TELEGRAM_ALLOWED_USERS": ("channels", "telegram", "allowFrom"),
        "TELEGRAM_ALLOW_FROM": ("channels", "telegram", "allowFrom"),
        "TELEGRAM_BOT_TO_BOT_ALLOW_BOTS": ("channels", "telegram", "botToBotAllowBots"),
    }
    for env_name, path in telegram_list_paths.items():
        value = env.get(env_name)
        if value not in (None, ""):
            _set_config_path_value(result, path, _parse_list_env(value))

    telegram_proxy = env.get("TELEGRAM_PROXY", "").strip()
    if telegram_proxy:
        _set_config_path_value(result, ("channels", "telegram", "proxy"), telegram_proxy)

    compatible_api_key = env.get("OPENAI_COMPATIBLE_API_KEY", "").strip()
    compatible_api_base = env.get("OPENAI_COMPATIBLE_API_BASE", "").strip()
    compatible_model = env.get("OPENAI_COMPATIBLE_MODEL", "").strip()

    explicit_custom_api_key = any(
        env.get(name, "").strip()
        for name in (
            "NANOBOT_PROVIDERS__CUSTOM__API_KEY",
            "NANOBOT_CONFIG__PROVIDERS__CUSTOM__API_KEY",
        )
    )
    explicit_custom_api_base = any(
        env.get(name, "").strip()
        for name in (
            "NANOBOT_PROVIDERS__CUSTOM__API_BASE",
            "NANOBOT_CONFIG__PROVIDERS__CUSTOM__API_BASE",
        )
    )
    explicit_model = any(
        env.get(name, "").strip()
        for name in (
            "NANOBOT_MODEL",
            "NANOBOT_AGENTS__DEFAULTS__MODEL",
            "NANOBOT_CONFIG__AGENTS__DEFAULTS__MODEL",
        )
    )
    explicit_provider = any(
        env.get(name, "").strip()
        for name in (
            "NANOBOT_PROVIDER",
            "NANOBOT_AGENTS__DEFAULTS__PROVIDER",
            "NANOBOT_CONFIG__AGENTS__DEFAULTS__PROVIDER",
        )
    )

    if compatible_api_key and not explicit_custom_api_key:
        _set_config_path_value(result, ("providers", "custom", "apiKey"), compatible_api_key)
    if compatible_api_base and not explicit_custom_api_base:
        _set_config_path_value(result, ("providers", "custom", "apiBase"), compatible_api_base)
    if compatible_model and not explicit_model:
        _set_config_path_value(result, ("agents", "defaults", "model"), compatible_model)
    if (
        (compatible_api_key or compatible_api_base or compatible_model)
        and not explicit_provider
    ):
        _set_config_path_value(result, ("agents", "defaults", "provider"), "custom")

    agent_string_paths = {
        "NANOBOT_PROVIDER": ("agents", "defaults", "provider"),
        "NANOBOT_MODEL": ("agents", "defaults", "model"),
        "NANOBOT_TIMEZONE": ("agents", "defaults", "timezone"),
    }
    for env_name, path in agent_string_paths.items():
        value = env.get(env_name, "").strip()
        if value:
            _set_config_path_value(result, path, value)

    return result


def _stored_config_data() -> dict:
    defaults = Config().model_dump(by_alias=True)
    loaded = load_config().model_dump(by_alias=True)
    raw = _load_raw_config()
    return _deep_merge(_deep_merge(defaults, loaded), raw)


def _merged_config_data() -> dict:
    return _apply_env_overrides(_stored_config_data())


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
            existing_data = _stored_config_data()

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
    group_chat_id = body.get("groupChatId")
    text = str(body.get("text", "")).strip()
    message_thread_id = body.get("messageThreadId")
    chain_depth = body.get("botToBotChainDepth")
    direct_bot_target = bool(re.fullmatch(r"@[A-Za-z0-9_]{5,32}", target))
    group_chat_target = bool(re.fullmatch(r"-\d{5,32}", target))
    if not direct_bot_target and not group_chat_target:
        return JSONResponse({
            "error": "target must be a Telegram bot username like @OtherBot or a negative numeric group chat ID"
        }, status_code=400)
    if group_chat_id in ("", None):
        group_chat_id = None
    elif not re.fullmatch(r"-\d{5,32}", str(group_chat_id).strip()):
        return JSONResponse({"error": "groupChatId must be a negative numeric group chat ID when provided"}, status_code=400)
    if group_chat_id is not None and not direct_bot_target:
        return JSONResponse({"error": "groupChatId requires target to be a bot username"}, status_code=400)
    if message_thread_id in ("", None):
        message_thread_id = None
    elif not re.fullmatch(r"\d{1,32}", str(message_thread_id).strip()):
        return JSONResponse({"error": "messageThreadId must be numeric when provided"}, status_code=400)
    if message_thread_id is not None and group_chat_id is None and not group_chat_target:
        return JSONResponse({"error": "messageThreadId requires a numeric group chat target or groupChatId"}, status_code=400)
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

        send_chat_id = str(group_chat_id).strip() if group_chat_id is not None else target
        payload_json: dict[str, Any] = {"chat_id": send_chat_id, "text": text}
        if message_thread_id is not None:
            payload_json["message_thread_id"] = int(str(message_thread_id).strip())
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload_json,
            )
        payload = response.json()
    except Exception as e:
        return JSONResponse({"error": f"Telegram request failed: {_redact_telegram_token(str(e), token)}"}, status_code=502)

    if not payload.get("ok"):
        sanitized = _redact_telegram_token(payload, token)
        description = sanitized.get("description") if isinstance(sanitized, dict) else None
        return JSONResponse({
            "error": description or "Telegram rejected the request",
            "telegram": sanitized,
        }, status_code=400)

    return JSONResponse({
        "ok": True,
        "target": target,
        "groupChatId": int(str(group_chat_id).strip()) if group_chat_id is not None else None,
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


def _has_provider_api_key(data: dict[str, Any]) -> bool:
    providers = data.get("providers") if isinstance(data, dict) else None
    if not isinstance(providers, dict):
        return False
    for prov in providers.values():
        if isinstance(prov, dict) and (prov.get("apiKey") or prov.get("api_key")):
            return True
    return False


async def auto_start_gateway():
    if _has_provider_api_key(_merged_config_data()):
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
