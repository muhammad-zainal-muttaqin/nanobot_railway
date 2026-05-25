import asyncio

import server


class FakeProcess:
    returncode = None
    stdout = None

    def terminate(self):
        self.returncode = 0

    async def wait(self):
        self.returncode = 0


def test_gateway_start_sets_native_pythonpath_first(monkeypatch, tmp_path):
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return FakeProcess()

    manager = server.GatewayManager()
    monkeypatch.setattr(server, "RUNTIME_CONFIG_PATH", tmp_path / "runtime_config.json")
    monkeypatch.setattr(server, "_stored_config_data", lambda: {"channels": {}, "providers": {}})
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    asyncio.run(manager.start())

    assert captured["args"][:4] == ("nanobot", "gateway", "--config", str(tmp_path / "runtime_config.json"))
    pythonpath = captured["env"]["PYTHONPATH"].split(server.os.pathsep)
    assert pythonpath[0] == str(server.Path(server.__file__).parent)
    assert pythonpath[1] == str(server.Path(server.__file__).parent / "nanobot_railway_patches")
    assert manager.state == "running"


def test_gateway_start_writes_env_runtime_config(monkeypatch, tmp_path):
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return FakeProcess()

    runtime_path = tmp_path / "runtime_config.json"
    manager = server.GatewayManager()
    monkeypatch.setattr(server, "RUNTIME_CONFIG_PATH", runtime_path)
    monkeypatch.setattr(server, "_stored_config_data", lambda: {"channels": {}, "providers": {}})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:env-token")
    monkeypatch.setenv("TELEGRAM_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TO_BOT_ALLOW_BOTS", "@AkuHolo_bot,@S_o_R_a_bot")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "sk-env")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_BASE", "https://llm.example.test/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "acme-chat")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    asyncio.run(manager.start())

    assert captured["args"][-1] == str(runtime_path)
    data = server.json.loads(runtime_path.read_text(encoding="utf-8"))
    assert data["channels"]["telegram"]["enabled"] is True
    assert data["channels"]["telegram"]["token"] == "123:env-token"
    assert data["channels"]["telegram"]["botToBotAllowBots"] == ["@AkuHolo_bot", "@S_o_R_a_bot"]
    assert data["providers"]["custom"]["apiKey"] == "sk-env"
    assert data["providers"]["custom"]["apiBase"] == "https://llm.example.test/v1"
    assert data["agents"]["defaults"]["provider"] == "custom"
    assert data["agents"]["defaults"]["model"] == "acme-chat"
