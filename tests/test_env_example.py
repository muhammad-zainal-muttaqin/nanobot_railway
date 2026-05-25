from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_env_example_documents_live_telegram_verifier_vars():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "TELEGRAM_ENABLED=0" in text
    assert "TELEGRAM_BOT_TOKEN=" in text
    assert "TELEGRAM_ALLOWED_USERS=*" in text
    assert "TELEGRAM_BOT_TO_BOT=0" in text
    assert "OPENAI_API_KEY=" in text
    assert "NANOBOT_PROVIDER=auto" in text
    assert "TELEGRAM_BOT_TO_BOT_TARGET=@OtherBot" in text
    assert "TELEGRAM_GROUP_CHAT_ID=" in text
    assert "TELEGRAM_MESSAGE_THREAD_ID=" in text
    assert "TELEGRAM_EXPECT_BOT_UPDATE_FROM=@OtherBot" in text
    assert "TELEGRAM_UPDATE_POLL_SECONDS=20" in text
    assert "TELEGRAM_REQUIRE_BOT_TO_BOT=0" in text
