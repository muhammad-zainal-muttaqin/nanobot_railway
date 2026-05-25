import importlib.metadata as metadata
import os
import subprocess
import sys
from pathlib import Path


def _nanobot_executable() -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return Path(sys.executable).parent / f"nanobot{suffix}"


def _native_pythonpath() -> str:
    root = Path(__file__).resolve().parent.parent
    return os.pathsep.join([str(root), str(root / "nanobot_railway_patches")])


def test_python_telegram_bot_distribution_is_absent():
    try:
        metadata.version("python-telegram-bot")
    except metadata.PackageNotFoundError:
        return
    raise AssertionError("python-telegram-bot must not be installed for native v10 verification")


def test_nanobot_gateway_cli_imports_without_ptb():
    env = os.environ.copy()
    env["PYTHONPATH"] = _native_pythonpath()

    result = subprocess.run(
        [str(_nanobot_executable()), "gateway", "--help"],
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    stdout = result.stdout.decode("utf-8", errors="replace")
    assert "Start the nanobot gateway" in stdout
