import asyncio

import server


class FakeProcess:
    returncode = None
    stdout = None

    def terminate(self):
        self.returncode = 0

    async def wait(self):
        self.returncode = 0


def test_gateway_start_sets_native_pythonpath_first(monkeypatch):
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return FakeProcess()

    manager = server.GatewayManager()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

    asyncio.run(manager.start())

    assert captured["args"][:2] == ("nanobot", "gateway")
    pythonpath = captured["env"]["PYTHONPATH"].split(server.os.pathsep)
    assert pythonpath[0] == str(server.Path(server.__file__).parent)
    assert pythonpath[1] == str(server.Path(server.__file__).parent / "nanobot_railway_patches")
    assert manager.state == "running"
