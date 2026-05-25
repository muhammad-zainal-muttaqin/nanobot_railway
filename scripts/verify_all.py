"""Run all local verification gates for the native Telegram Bot API v10 work."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(label: str, args: list[str], env: dict[str, str] | None = None) -> int:
    print(f"\n== {label} ==", flush=True)
    result = subprocess.run(args, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode:
        print(f"{label} failed with exit code {result.returncode}")
    return result.returncode


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(PROJECT_ROOT), str(PROJECT_ROOT / "nanobot_railway_patches")]
    )

    checks = [
        (
            "compileall",
            [
                sys.executable,
                "-m",
                "compileall",
                "telegram",
                "server.py",
                "nanobot_railway_patches",
                "scripts",
                "tests",
            ],
            env,
        ),
        ("pytest", [sys.executable, "-m", "pytest", "tests"], env),
        ("nanobot latest", [sys.executable, "scripts/verify_nanobot_latest.py"], env),
        ("telegram api surface", [sys.executable, "scripts/audit_telegram_api_surface.py"], env),
        ("gateway offline", [sys.executable, "scripts/verify_gateway_offline.py"], env),
        ("telegram live", [sys.executable, "scripts/verify_telegram_live.py"], env),
    ]

    failed = 0
    for label, args, check_env in checks:
        failed |= _run(label, args, check_env)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
