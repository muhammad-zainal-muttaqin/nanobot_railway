from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_public_template_vars():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "ADMIN_USERNAME=admin" in text
    assert "ADMIN_PASSWORD=" in text
    assert "NANOBOT_AGENTS__DEFAULTS__WORKSPACE=/data/.nanobot/workspace" in text
    assert "OPENAI_COMPATIBLE_API_KEY=" in text
    assert "OPENAI_COMPATIBLE_API_BASE=" in text
    assert "OPENAI_COMPATIBLE_MODEL=" in text
    assert "TELEGRAM_ENABLED=0" in text
    assert "TELEGRAM_BOT_TOKEN=" in text
    assert "TELEGRAM_ALLOWED_USERS=*" in text
    assert "TELEGRAM_BOT_TO_BOT=0" in text
    assert "OPENAI_API_KEY=" in text


def test_env_example_does_not_suggest_live_verifier_vars_to_template_users():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "TELEGRAM_BOT_TO_BOT_TARGET" not in text
    assert "TELEGRAM_GROUP_CHAT_ID" not in text
    assert "TELEGRAM_MESSAGE_THREAD_ID" not in text
    assert "TELEGRAM_EXPECT_BOT_UPDATE_FROM" not in text
    assert "TELEGRAM_UPDATE_POLL_SECONDS" not in text
    assert "TELEGRAM_REQUIRE_BOT_TO_BOT" not in text
