"""Offline nanobot gateway smoke test using the native Telegram package.

The smoke starts `nanobot gateway` with a temporary config, no enabled chat
channels, and a dummy provider key. It does not call Telegram or an LLM; success
means the installed nanobot gateway reaches runtime without python-telegram-bot.
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nanobot.config.schema import Config


def _ptb_installed() -> bool:
    try:
        metadata.version("python-telegram-bot")
    except metadata.PackageNotFoundError:
        return False
    return True


def _nanobot_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return Path(sys.executable).parent / f"nanobot{suffix}"


def _build_config(home: Path) -> Path:
    config = json.loads(Config().model_dump_json(by_alias=True))
    config["agents"]["defaults"]["provider"] = "openai"
    config["agents"]["defaults"]["model"] = "openai/gpt-4o-mini"
    config["providers"]["openai"]["apiKey"] = "offline-smoke-dummy-key"
    config_path = home / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def run_smoke(seconds: float = 5.0) -> tuple[int, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="nanobot-gateway-smoke-") as tmp:
        home = Path(tmp)
        config_path = _build_config(home)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PROJECT_ROOT), str(PROJECT_ROOT / "nanobot_railway_patches")]
        )

        proc = subprocess.Popen(
            [str(_nanobot_executable()), "gateway", "--config", str(config_path)],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        time.sleep(seconds)
        alive_after_startup = proc.poll() is None
        if alive_after_startup:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

        output = (proc.stdout.read() if proc.stdout else b"").decode("utf-8", errors="replace")
        failed_import = "ModuleNotFoundError" in output or "python-telegram-bot" in output
        registered_tools = "Registered" in output and "tools" in output
        report = {
            "status": (
                "ok"
                if alive_after_startup and registered_tools and not failed_import and not _ptb_installed()
                else "failed"
            ),
            "alive_after_startup": alive_after_startup,
            "python_telegram_bot_installed": _ptb_installed(),
            "registered_tools": registered_tools,
            "returncode_after_stop": proc.returncode,
            "tail": output[-1000:],
        }
        return (0 if report["status"] == "ok" else 1), report


def main() -> int:
    code, report = run_smoke()
    for key, value in report.items():
        print(f"{key}={ascii(value)}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
