from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_packages_native_telegram_without_ptb():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'uv pip install --system --no-cache "nanobot-ai==0.2.0"' in dockerfile
    assert "uv pip uninstall --system python-telegram-bot" in dockerfile
    assert "COPY telegram/ /app/telegram/" in dockerfile
    assert "ENV PYTHONPATH=/app:/app/nanobot_railway_patches" in dockerfile


def test_dockerignore_keeps_native_telegram_package_in_context():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert "telegram/" not in ignored
    assert "nanobot_railway_patches/" not in ignored
    assert ".tmp_home_smoke/" in ignored


def test_railway_uses_dockerfile_and_start_script():
    railway = (ROOT / "railway.toml").read_text(encoding="utf-8")

    assert 'builder = "DOCKERFILE"' in railway
    assert 'dockerfilePath = "Dockerfile"' in railway
    assert 'startCommand = "/app/start.sh"' in railway


def test_dashboard_bot_to_bot_send_exposes_chain_depth():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "botToBotChainDepth" in html
    assert "botToBot.chainDepth" in html
