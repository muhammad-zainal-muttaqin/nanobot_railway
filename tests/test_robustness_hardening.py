"""Regression tests for runtime-robustness hardening.

Each test pins a previously-confirmed failure mode where a malformed input or a
transient error would crash the whole service / stall the bot, and asserts the
hardened code now degrades gracefully instead.
"""

import asyncio
import socket
from urllib.error import URLError

from starlette.testclient import TestClient

import server
from telegram import Bot, Update


def _auth_header() -> dict[str, str]:
    import base64

    token = base64.b64encode(
        f"{server.ADMIN_USERNAME}:{server.ADMIN_PASSWORD}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


# ── Fix 1: malformed NANOBOT_*__ JSON value must not raise ──────────────────


def test_parse_config_env_value_falls_back_to_raw_on_bad_json():
    # Valid JSON still parses.
    assert server._parse_config_env_value('{"a": 1}') == {"a": 1}
    assert server._parse_config_env_value("[1, 2]") == [1, 2]
    # Malformed JSON-prefixed value degrades to the raw string instead of raising.
    assert server._parse_config_env_value("{foo: bar}") == "{foo: bar}"
    assert server._parse_config_env_value("[1,2,") == "[1,2,"


def test_merged_config_survives_malformed_generic_env(monkeypatch):
    monkeypatch.setattr(
        server, "_stored_config_data", lambda: {"channels": {}, "providers": {}, "agents": {}}
    )
    monkeypatch.setenv("NANOBOT_CONFIG__AGENTS__DEFAULTS__EXTRA", "{not valid json}")

    data = server._merged_config_data()

    assert data["agents"]["defaults"]["extra"] == "{not valid json}"


# ── Fix 2: malformed list-env JSON array falls back to comma-split ──────────


def test_parse_list_env_falls_back_to_comma_split_on_bad_json():
    # Valid JSON array still parses.
    assert server._parse_list_env('["@a", "@b"]') == ["@a", "@b"]
    # Comma form is unaffected.
    assert server._parse_list_env("*,12345") == ["*", "12345"]
    # Malformed array no longer raises; it comma-splits the raw string.
    assert server._parse_list_env("[1,2,") == ["[1", "2"]


def test_merged_config_survives_malformed_list_env(monkeypatch):
    monkeypatch.setattr(
        server, "_stored_config_data", lambda: {"channels": {}, "providers": {}, "agents": {}}
    )
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", '["@bot"')

    data = server._merged_config_data()

    # Does not crash; degrades to a best-effort comma-split.
    assert data["channels"]["telegram"]["allowFrom"] == ['["@bot"']


# ── Fix 3: a single poison update must not stall the polling loop ───────────


class _FakeUpdatesResponse:
    status_code = 200
    text = ""

    def __init__(self, result):
        self._result = result

    def json(self):
        return {"ok": True, "result": self._result}


class _FakeUpdatesClient:
    def __init__(self, result):
        self._result = result

    async def post(self, url, json=None, data=None, files=None):
        return _FakeUpdatesResponse(self._result)


def test_get_updates_skips_poison_update_but_advances_offset():
    poison = {"update_id": 555, "callback_query": {"from": {"id": 1}, "chat_instance": "z"}}
    valid = {"update_id": 556, "message": {"message_id": 1, "date": 1, "chat": {"id": 9, "type": "private"}, "text": "hi"}}
    bot = Bot("123:token", request=_FakeUpdatesClient([poison, valid]))

    updates = asyncio.run(bot.get_updates())

    # Both updates are represented so offset can advance past the poison one.
    assert [u.update_id for u in updates] == [555, 556]
    # The valid one parsed fully; the poison one degraded to a minimal Update.
    assert isinstance(updates[0], Update)
    assert updates[1].message.text == "hi"
    assert max(u.update_id for u in updates) == 556


def test_get_updates_drops_item_without_int_update_id():
    bad = {"callback_query": {"chat_instance": "z"}}  # no update_id at all
    valid = {"update_id": 700, "message": {"message_id": 1, "date": 1, "chat": {"id": 9, "type": "private"}, "text": "ok"}}
    bot = Bot("123:token", request=_FakeUpdatesClient([bad, valid]))

    updates = asyncio.run(bot.get_updates())

    assert [u.update_id for u in updates] == [700]


# ── Fix 4: /health stays 200 even when gateway auto-start fails ─────────────


def test_health_stays_ok_when_autostart_fails(monkeypatch):
    async def boom():
        raise RuntimeError("corrupt config.json")

    monkeypatch.setattr(server, "ensure_gateway_started", boom)
    client = TestClient(server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── Fix 5: bot-to-bot send guards a non-dict JSON payload ───────────────────


def test_bot_to_bot_send_rejects_non_dict_payload(monkeypatch):
    class FakeResponse:
        def json(self):
            return []  # valid JSON, but not an object

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            return FakeResponse()

    monkeypatch.setattr(
        server, "_merged_config_data", lambda: {"channels": {"telegram": {"token": "123:abc"}}}
    )

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "text": "hello"},
    )

    assert response.status_code == 502
    assert response.json()["error"] == "Unexpected Telegram response"


# ── Fix 7: pin-check verifier skips cleanly on a network error ──────────────


def test_verify_nanobot_latest_skips_on_network_error(monkeypatch, capsys):
    import scripts.verify_nanobot_latest as verifier

    monkeypatch.setattr(verifier, "pinned_version", lambda: "0.2.0")

    def raise_network():
        raise URLError("pypi unreachable")

    monkeypatch.setattr(verifier, "latest_version", raise_network)

    assert verifier.main() == 0
    assert "status=skipped" in capsys.readouterr().out


def test_verify_nanobot_latest_still_flags_real_mismatch(monkeypatch):
    import scripts.verify_nanobot_latest as verifier

    monkeypatch.setattr(verifier, "pinned_version", lambda: "0.2.0")
    monkeypatch.setattr(verifier, "latest_version", lambda: "0.3.0")

    assert verifier.main() == 1
