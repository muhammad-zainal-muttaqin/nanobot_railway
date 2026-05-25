from scripts.verify_gateway_offline import run_smoke


def test_gateway_offline_smoke_reaches_runtime_without_ptb():
    code, report = run_smoke(seconds=5.0)

    assert code == 0
    assert report["status"] == "ok"
    assert report["alive_after_startup"] is True
    assert report["python_telegram_bot_installed"] is False
    assert report["registered_tools"] is True
