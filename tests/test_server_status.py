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


def test_bot_to_bot_send_rejects_invalid_chain_depth():
    client = TestClient(server.app)

    response = client.post(
        "/api/telegram/bot-to-bot/send",
        headers=_auth_header(),
        json={"target": "@OtherBot", "text": "hello", "botToBotChainDepth": "bad"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "botToBotChainDepth must be numeric when provided"
