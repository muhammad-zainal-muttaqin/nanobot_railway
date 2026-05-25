import asyncio

import scripts.verify_telegram_live as live
from scripts.verify_telegram_live import _matches_expected_bot, _poll_for_bot_update, verify_live
from telegram import Chat, Message, Update, User


class UserLike:
    def __init__(self, id, username, is_bot):
        self.id = id
        self.username = username
        self.is_bot = is_bot


def test_live_verify_skips_without_token():
    code, report = asyncio.run(verify_live({}))

    assert code == 0
    assert report["status"] == "skipped"
    assert report["reason"] == "TELEGRAM_BOT_TOKEN is not set"
    assert report["bot_api_version"] == "10.0"


def test_live_verify_required_bot_to_bot_fails_without_token():
    code, report = asyncio.run(verify_live({"TELEGRAM_REQUIRE_BOT_TO_BOT": "1"}))

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "TELEGRAM_BOT_TOKEN is not set"


def test_live_verify_required_bot_to_bot_fails_when_evidence_is_missing(monkeypatch):
    class FakeBot:
        def __init__(self, token):
            self.token = token

        async def get_me(self):
            return User(id=1, is_bot=True, first_name="Native", username="NativeBot")

        async def call_api(self, method):
            assert method == "getMe"
            return {"id": 1}

        async def _close_client(self):
            pass

    monkeypatch.setattr(live, "Bot", FakeBot)

    code, report = asyncio.run(verify_live({
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_REQUIRE_BOT_TO_BOT": "true",
    }))

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "required bot-to-bot proof is incomplete"
    assert report["missing"] == [
        "TELEGRAM_BOT_TO_BOT_TARGET",
        "TELEGRAM_EXPECT_BOT_UPDATE_FROM",
        "TELEGRAM_GROUP_CHAT_ID",
    ]


def test_live_verify_required_bot_to_bot_passes_with_send_and_receive(monkeypatch):
    class FakeBot:
        def __init__(self, token):
            self.token = token

        async def get_me(self):
            return User(id=1, is_bot=True, first_name="Native", username="NativeBot")

        async def call_api(self, method):
            assert method == "getMe"
            return {"id": 1}

        async def send_message(self, chat_id, text, **kwargs):
            return Message(message_id=9, date=1, chat=Chat(id=2, type="private"), text=text)

        async def _close_client(self):
            pass

    async def fake_poll(bot, expected, timeout):
        return {"matched": True, "expected": expected, "timeout_seconds": timeout}

    monkeypatch.setattr(live, "Bot", FakeBot)
    monkeypatch.setattr(live, "_poll_for_bot_update", fake_poll)

    code, report = asyncio.run(verify_live({
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_REQUIRE_BOT_TO_BOT": "1",
        "TELEGRAM_BOT_TO_BOT_TARGET": "@OtherBot",
        "TELEGRAM_EXPECT_BOT_UPDATE_FROM": "@OtherBot",
        "TELEGRAM_GROUP_CHAT_ID": "-10012345",
    }))

    assert code == 0
    assert report["status"] == "ok"
    assert report["bot_to_bot_send"]["target"] == "@OtherBot"
    assert report["bot_to_bot_receive"]["matched"] is True
    assert report["group_send"]["chat_id"] == 2


def test_live_verify_rejects_invalid_bot_to_bot_target(monkeypatch):
    class FakeBot:
        def __init__(self, token):
            self.token = token

        async def get_me(self):
            return User(id=1, is_bot=True, first_name="Native", username="NativeBot")

        async def call_api(self, method):
            return {"id": 1}

        async def _close_client(self):
            pass

    monkeypatch.setattr(live, "Bot", FakeBot)

    code, report = asyncio.run(verify_live({
        "TELEGRAM_BOT_TOKEN": "123:token",
        "TELEGRAM_BOT_TO_BOT_TARGET": "not valid",
    }))

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "TELEGRAM_BOT_TO_BOT_TARGET must be @BotUsername or numeric chat ID"


def test_expected_bot_update_matching_accepts_username_or_id():
    user = UserLike(id=123, username="OtherBot", is_bot=True)

    assert _matches_expected_bot(user, "@OtherBot")
    assert _matches_expected_bot(user, "otherbot")
    assert _matches_expected_bot(user, "123")
    assert not _matches_expected_bot(user, "@BlockedBot")
    assert not _matches_expected_bot(UserLike(id=123, username="OtherBot", is_bot=False), "@OtherBot")


def test_poll_for_bot_update_matches_guest_message_sender():
    class FakeBot:
        def __init__(self):
            self.calls = 0

        async def get_updates(self, **kwargs):
            self.calls += 1
            return [
                Update(
                    update_id=99,
                    guest_message=Message(
                        message_id=77,
                        date=1,
                        chat=Chat(id=555, type="private"),
                        from_user=User(id=321, is_bot=True, first_name="Other", username="OtherBot"),
                        text="hello",
                    ),
                )
            ]

    report = asyncio.run(_poll_for_bot_update(FakeBot(), "@OtherBot", timeout=1))

    assert report["matched"] is True
    assert report["update_id"] == 99
    assert report["sender_id"] == 321
    assert report["sender_username"] == "OtherBot"
    assert report["message_id"] == 77
    assert report["chat_id"] == 555


def test_poll_for_bot_update_matches_business_message_sender_by_id():
    class FakeBot:
        async def get_updates(self, **kwargs):
            return [
                Update(
                    update_id=100,
                    business_message=Message(
                        message_id=78,
                        date=1,
                        chat=Chat(id=556, type="private"),
                        from_user=User(id=654, is_bot=True, first_name="Business", username="BusinessBot"),
                        text="business hello",
                    ),
                )
            ]

    report = asyncio.run(_poll_for_bot_update(FakeBot(), "654", timeout=1))

    assert report["matched"] is True
    assert report["update_id"] == 100
    assert report["sender_id"] == 654
    assert report["sender_username"] == "BusinessBot"
    assert report["message_id"] == 78
    assert report["chat_id"] == 556
