import base64

from starlette.testclient import TestClient

import server


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{server.ADMIN_USERNAME}:{server.ADMIN_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_api_status_reports_native_telegram_sdk():
    client = TestClient(server.app)

    response = client.get("/api/status", headers=_auth_header())

    assert response.status_code == 200
    versions = response.json()["versions"]
    assert versions["nanobot_ai"] == "0.2.0"
    assert versions["telegram_sdk"]["sdk"] == "native/v10"
    assert versions["telegram_sdk"]["api_version"] == "10.0"


def test_env_overrides_effective_config(monkeypatch):
    monkeypatch.setattr(server, "_stored_config_data", lambda: {"channels": {}, "providers": {}, "agents": {}})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:env-token")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USERS", "*,12345")
    monkeypatch.setenv("TELEGRAM_BOT_TO_BOT", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TO_BOT_MAX_PER_MINUTE", "5")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter")
    monkeypatch.setenv("NANOBOT_AGENTS__DEFAULTS__PROVIDER", "openrouter")

    data = server._merged_config_data()

    telegram = data["channels"]["telegram"]
    assert telegram["token"] == "123:env-token"
    assert telegram["enabled"] is True
    assert telegram["allowFrom"] == ["*", "12345"]
    assert telegram["botToBot"] is True
    assert telegram["botToBotMaxPerMinute"] == 5
    assert data["providers"]["openrouter"]["apiKey"] == "sk-openrouter"
    assert data["agents"]["defaults"]["provider"] == "openrouter"


def test_bot_to_bot_send_includes_optional_chain_depth(monkeypatch):
    captured = {}

    class FakeResponse:
        def json(self):
            return {"ok": True, "result": {"message_id": 123}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(server, "_merged_config_data", lambda: {"channels": {"telegram": {"token": "123:abc"}}})

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "text": "hello", "botToBotChainDepth": 2},
    )

    assert response.status_code == 200
    assert captured["json"]["text"] == "[nanobot:b2b-depth=2] hello"
    assert response.json()["botToBotChainDepth"] == 2


def test_bot_to_bot_send_accepts_group_chat_id_alias(monkeypatch):
    captured = {}

    class FakeResponse:
        def json(self):
            return {"ok": True, "result": {"message_id": 124, "message_thread_id": 77}}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(server, "_merged_config_data", lambda: {"channels": {"telegram": {"token": "123:abc"}}})

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={
            "target": "@OtherBot",
            "groupChatId": "-10012345",
            "messageThreadId": "77",
            "text": "/ping@OtherBot hi",
        },
    )

    assert response.status_code == 200
    assert captured["json"]["chat_id"] == "-10012345"
    assert captured["json"]["message_thread_id"] == 77
    assert response.json()["groupChatId"] == -10012345


def test_bot_to_bot_send_rejects_invalid_chain_depth():
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "text": "hello", "botToBotChainDepth": "bad"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "botToBotChainDepth must be numeric when provided"


def test_bot_to_bot_send_rejects_private_chat_id_as_group():
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "groupChatId": "8777874679", "text": "hello"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "groupChatId must be a negative numeric group chat ID when provided"


def test_bot_to_bot_send_rejects_private_numeric_target_for_group_topic():
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "8777874679", "messageThreadId": "77", "text": "hello"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "target must be a Telegram bot username like @OtherBot or a negative numeric group chat ID"


def test_bot_to_bot_send_redacts_token_from_errors(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            raise RuntimeError(f"failed {url}")

    monkeypatch.setattr(server, "_merged_config_data", lambda: {"channels": {"telegram": {"token": "123:abc"}}})

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "text": "hello"},
    )

    assert response.status_code == 502
    assert "123:abc" not in response.json()["error"]
    assert "<redacted-token>" in response.json()["error"]
