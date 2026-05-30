"""Verify the wrapper pins the latest published nanobot-ai package."""

from __future__ import annotations

import json
import re
import socket
from json import JSONDecodeError
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPI_URL = "https://pypi.org/pypi/nanobot-ai/json"


def pinned_version() -> str:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    match = re.search(r'"nanobot-ai==([^"]+)"', dockerfile)
    if not match:
        raise RuntimeError("Dockerfile does not pin nanobot-ai")
    return match.group(1)


def latest_version() -> str:
    data = json.loads(urlopen(PYPI_URL, timeout=30).read().decode("utf-8"))
    return data["info"]["version"]


def main() -> int:
    pinned = pinned_version()
    try:
        latest = latest_version()
    except (URLError, TimeoutError, socket.timeout, JSONDecodeError, KeyError) as exc:
        # A transient PyPI outage or unexpected payload must not hard-fail the
        # local gate; a genuine version mismatch still returns 1 below.
        print(f"source={PYPI_URL}")
        print(f"pinned={pinned}")
        print(f"status=skipped (network: {exc})")
        return 0
    print(f"source={PYPI_URL}")
    print(f"pinned={pinned}")
    print(f"latest={latest}")
    print(f"status={'ok' if pinned == latest else 'outdated'}")
    return 0 if pinned == latest else 1


if __name__ == "__main__":
    raise SystemExit(main())
