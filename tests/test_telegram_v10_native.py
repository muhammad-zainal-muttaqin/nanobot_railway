import asyncio

import httpx
import pytest

from telegram import Bot, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, User
from telegram.constants import BOT_API_VERSION, BOT_API_VERSION_INFO
from telegram._application import Application
from telegram._bot import _parse_update
from telegram.error import BadRequest, NetworkError, RetryAfter
from telegram.ext import MessageHandler, filters
from telegram.request import HTTPXRequest


class FakeResponse:
    def __init__(self, result):
        self._result = result
        self.status_code = 200
        self.text = ""

    def json(self):
        return {"ok": True, "result": self._result}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def post(self, url, json=None, data=None, files=None):
        method = url.rsplit("/", 1)[-1]
        payload = json if json is not None else data
        self.calls.append((method, payload, files))
        if method == "answerGuestQuery":
            return FakeResponse({"message_id": 55, "date": 2})
        if method == "getChatAdministrators":
            return FakeResponse([])
        if method in {"sendMessage", "sendMessageDraft", "sendPhoto", "sendLivePhoto", "sendPoll"}:
            return FakeResponse(
                {
                    "message_id": 7,
                    "date": 1,
                    "chat": {"id": payload.get("chat_id", 123), "type": "private"},
                    "text": payload.get("text", ""),
                }
            )
        return FakeResponse(True)

    async def aclose(self):
        self.closed = True


def run(coro):
    return asyncio.run(coro)


def test_send_message_accepts_bot_username_chat_id():
    client = FakeClient()
    bot = Bot("123:token", request=client)

    message = run(bot.send_message("@OtherBot", "hello"))

    assert message.text == "hello"
    assert client.calls[0][0] == "sendMessage"
    assert client.calls[0][1]["chat_id"] == "@OtherBot"


def test_native_constants_report_bot_api_10():
    assert BOT_API_VERSION == "10.0"
    assert BOT_API_VERSION_INFO == (10, 0)


def test_nanobot_telegram_import_surface_is_native():
    from telegram import (
        BotCommand,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        ReactionTypeEmoji,
        ReplyParameters,
    )
    from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
    from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters
    from telegram.request import HTTPXRequest

    assert BotCommand
    assert InlineKeyboardButton
    assert InlineKeyboardMarkup
    assert ReactionTypeEmoji
    assert ReplyParameters
    assert BadRequest
    assert NetworkError
    assert RetryAfter
    assert TimedOut
    assert Application
    assert CallbackQueryHandler
    assert ContextTypes
    assert MessageHandler
    assert filters
    assert HTTPXRequest


def test_missing_official_types_import_as_flexible_objects():
    from telegram import BotAccessSettings, InputMediaLivePhoto, PaidMediaPurchased, TelegramObject
    from telegram._bot import _parse_field

    settings = BotAccessSettings(can_read_messages=True)
    assert isinstance(settings, TelegramObject)
    assert settings.can_read_messages is True
    assert settings.to_dict() == {"can_read_messages": True}

    parsed = _parse_field(PaidMediaPurchased, {"from": {"id": 1}, "paid_media_payload": "p"})
    assert parsed.from_user == {"id": 1}
    assert parsed.paid_media_payload == "p"
    assert InputMediaLivePhoto(type="live_photo").type == "live_photo"


def test_send_message_draft_allows_empty_text_for_api_10():
    client = FakeClient()
    bot = Bot("123:token", request=client)

    message = run(bot.send_message_draft(123))

    assert message.text == ""
    assert client.calls[0][0] == "sendMessageDraft"
    assert client.calls[0][1]["text"] == ""


def test_generic_v10_method_wrappers_reach_official_api_names():
    client = FakeClient()
    bot = Bot("123:token", request=client)

    result = run(bot.approve_suggested_post(chat_id=123, message_id=456))

    assert result is True
    assert client.calls[0][0] == "approveSuggestedPost"
    assert client.calls[0][1] == {"chat_id": 123, "message_id": 456}


def test_v10_guest_and_managed_bot_methods_use_official_payloads():
    client = FakeClient()
    bot = Bot("123:token", request=client)
    result = {"type": "article", "id": "1", "title": "Reply"}

    sent = run(bot.answer_guest_query("guest-query", result=result))
    token = run(bot.get_managed_bot_token(user_id=456))
    updated = run(bot.set_managed_bot_access_settings(user_id=456, can_read_messages=True))

    assert sent.message_id == 55
    assert token == "True"
    assert updated is True
    assert client.calls[0][0] == "answerGuestQuery"
    assert client.calls[0][1] == {"guest_query_id": "guest-query", "result": result}
    assert client.calls[1][0] == "getManagedBotToken"
    assert client.calls[1][1] == {"user_id": 456}
    assert client.calls[2][0] == "setManagedBotAccessSettings"
    assert client.calls[2][1] == {"user_id": 456, "can_read_messages": True}


def test_v10_chat_admin_return_bots_and_reaction_permission():
    from telegram import ChatAdministratorRights, ChatMemberAdministrator, ChatMemberMember, ChatMemberRestricted, ChatPermissions
    from telegram._bot import _parse_field

    client = FakeClient()
    bot = Bot("123:token", request=client)

    admins = run(bot.get_chat_administrators(-100, return_bots=True))
    permissions = ChatPermissions(can_react_to_messages=True, can_edit_tag=True)

    assert admins == []
    assert permissions.can_react_to_messages is True
    assert permissions.can_edit_tag is True
    admin = _parse_field(ChatMemberAdministrator, {
        "user": {"id": 2, "is_bot": False, "first_name": "Ada"},
        "can_be_edited": True,
        "is_anonymous": False,
        "can_manage_chat": True,
        "can_delete_messages": True,
        "can_manage_video_chats": True,
        "can_restrict_members": True,
        "can_promote_members": True,
        "can_change_info": True,
        "can_invite_users": True,
        "can_manage_tags": True,
    })
    rights = ChatAdministratorRights(
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=True,
        can_change_info=True,
        can_invite_users=True,
        can_manage_tags=True,
    )
    member = _parse_field(ChatMemberMember, {
        "user": {"id": 4, "is_bot": False, "first_name": "Grace"},
        "tag": "ops",
    })
    parsed = _parse_field(ChatMemberRestricted, {
        "user": {"id": 3, "is_bot": False, "first_name": "Ada"},
        "is_member": True,
        "can_send_messages": True,
        "can_send_audios": True,
        "can_send_documents": True,
        "can_send_photos": True,
        "can_send_videos": True,
        "can_send_video_notes": True,
        "can_send_voice_notes": True,
        "can_send_polls": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
        "can_change_info": True,
        "can_invite_users": True,
        "can_pin_messages": True,
        "can_manage_topics": True,
        "can_react_to_messages": False,
        "can_edit_tag": True,
        "tag": "limited",
    })
    promoted = run(bot.promote_chat_member(-100, 2, can_manage_tags=True))
    assert promoted is True
    assert admin.can_manage_tags is True
    assert rights.can_manage_tags is True
    assert member.tag == "ops"
    assert parsed.can_react_to_messages is False
    assert parsed.can_edit_tag is True
    assert parsed.tag == "limited"
    assert client.calls[0][0] == "getChatAdministrators"
    assert client.calls[0][1] == {"chat_id": -100, "return_bots": True}
    assert client.calls[1][0] == "promoteChatMember"
    assert client.calls[1][1]["can_manage_tags"] is True


def test_v10_poll_media_fields_are_typed_and_sendable():
    from telegram import Message, Poll, PollAnswer, ReplyParameters
    from telegram._bot import _parse_field

    client = FakeClient()
    bot = Bot("123:token", request=client)

    message = run(bot.send_poll(
        123,
        "Pick one",
        [{"text": "A", "media": {"type": "photo", "media": "file-id"}}],
        media={"type": "photo", "media": "poll-cover"},
        explanation_media={"type": "photo", "media": "explain-cover"},
        members_only=True,
        country_codes=["ID", "US"],
        correct_option_ids=[0],
        allows_revoting=True,
        shuffle_options=True,
        allow_adding_options=True,
        hide_results_until_closes=True,
        description="short poll",
    ))
    poll = _parse_field(Poll, {
        "id": "poll-1",
        "question": "Pick one",
        "options": [{"text": "A", "voter_count": 1, "media": {"type": "photo", "media": "file-id"}}],
        "total_voter_count": 1,
        "is_closed": False,
        "is_anonymous": False,
        "type": "quiz",
        "allows_multiple_answers": False,
        "media": {"type": "photo", "media": "poll-cover"},
        "explanation_media": {"type": "photo", "media": "explain-cover"},
        "members_only": True,
        "country_codes": ["ID"],
        "correct_option_ids": [0],
        "allows_revoting": True,
        "description": "short poll",
        "options": [{
            "text": "A",
            "voter_count": 1,
            "media": {"type": "photo", "media": "file-id"},
            "persistent_id": "option-a",
            "added_by_user": {"id": 5, "is_bot": False, "first_name": "Lin"},
            "addition_date": 123,
        }],
    })
    answer = _parse_field(PollAnswer, {
        "poll_id": "poll-1",
        "option_ids": [0],
        "option_persistent_ids": ["option-a"],
    })
    reply = ReplyParameters(message_id=9, poll_option_id=0)
    message_with_poll_option = _parse_field(Message, {
        "message_id": 8,
        "date": 1,
        "chat": {"id": 123, "type": "private"},
        "reply_to_poll_option_id": 0,
    })

    assert message.chat.id == 123
    assert poll.media.media == "poll-cover"
    assert poll.explanation_media.media == "explain-cover"
    assert poll.options[0].media.media == "file-id"
    assert poll.members_only is True
    assert poll.country_codes == ["ID"]
    assert poll.correct_option_ids == [0]
    assert poll.allows_revoting is True
    assert poll.description == "short poll"
    assert poll.options[0].persistent_id == "option-a"
    assert poll.options[0].added_by_user.first_name == "Lin"
    assert poll.options[0].addition_date == 123
    assert answer.option_persistent_ids == ["option-a"]
    assert reply.poll_option_id == 0
    assert message_with_poll_option.reply_to_poll_option_id == 0
    assert client.calls[0][0] == "sendPoll"
    assert client.calls[0][1]["media"] == {"type": "photo", "media": "poll-cover"}
    assert client.calls[0][1]["explanation_media"] == {"type": "photo", "media": "explain-cover"}
    assert client.calls[0][1]["members_only"] is True
    assert client.calls[0][1]["country_codes"] == ["ID", "US"]
    assert client.calls[0][1]["correct_option_ids"] == [0]
    assert client.calls[0][1]["allows_revoting"] is True
    assert client.calls[0][1]["shuffle_options"] is True
    assert client.calls[0][1]["allow_adding_options"] is True
    assert client.calls[0][1]["hide_results_until_closes"] is True
    assert client.calls[0][1]["description"] == "short poll"


def test_call_api_reaches_any_official_method_name():
    client = FakeClient()
    bot = Bot("123:token", request=client)

    result = run(bot.call_api("getMyStarBalance"))

    assert result is True
    assert client.calls[0][0] == "getMyStarBalance"


def test_http_errors_redact_token_and_map_request_errors():
    class RaisingClient:
        async def post(self, url, json=None, data=None, files=None):
            request = httpx.Request("POST", url)
            raise httpx.ConnectError(f"failed {url}", request=request)

    bot = Bot("123:secret-token", request=RaisingClient())

    with pytest.raises(NetworkError) as exc:
        run(bot.get_me())

    assert "123:secret-token" not in str(exc.value)
    assert "<redacted-token>" in str(exc.value)


def test_invalid_json_diagnostics_redact_token():
    class InvalidJsonResponse:
        status_code = 502
        text = "upstream mentioned 123:secret-token and /bot123:secret-token/getMe"

        def json(self):
            raise ValueError("not json")

    class InvalidJsonClient:
        async def post(self, url, json=None, data=None, files=None):
            return InvalidJsonResponse()

    bot = Bot("123:secret-token", request=InvalidJsonClient())

    with pytest.raises(NetworkError) as exc:
        run(bot.get_me())

    assert "123:secret-token" not in str(exc.value)
    assert "Invalid JSON from Telegram API getMe" in str(exc.value)


def test_bot_api_error_mapping_handles_retry_and_ok_false_status_200():
    class ApiErrorResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "ok": False,
                "description": "Too Many Requests: retry later",
                "parameters": {"retry_after": 4},
            }

    class ApiErrorClient:
        async def post(self, url, json=None, data=None, files=None):
            return ApiErrorResponse()

    bot = Bot("123:token", request=ApiErrorClient())

    with pytest.raises(RetryAfter) as exc:
        run(bot.get_me())

    assert exc.value.retry_after == 4


def test_bot_api_ok_false_status_200_without_retry_is_bad_request():
    class ApiErrorResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"ok": False, "description": "Bad request"}

    class ApiErrorClient:
        async def post(self, url, json=None, data=None, files=None):
            return ApiErrorResponse()

    bot = Bot("123:token", request=ApiErrorClient())

    with pytest.raises(BadRequest):
        run(bot.get_me())


def test_media_file_id_string_is_sent_without_upload():
    client = FakeClient()
    bot = Bot("123:token", request=client)

    message = run(bot.send_live_photo(123, "telegram-file-id"))

    assert message.chat.id == 123
    assert client.calls[0][0] == "sendLivePhoto"
    assert client.calls[0][1]["live_photo"] == "telegram-file-id"
    assert client.calls[0][2] is None


def test_multipart_complex_values_are_json_encoded():
    client = FakeClient()
    bot = Bot("123:token", request=client)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="Open", url="https://example.com")]])

    message = run(bot.send_photo(123, b"image", reply_markup=markup, has_spoiler=True))

    assert message.chat.id == 123
    assert client.calls[0][0] == "sendPhoto"
    assert client.calls[0][1]["reply_markup"] == (
        '{"inline_keyboard":[[{"text":"Open","url":"https://example.com"}]]}'
    )
    assert client.calls[0][1]["has_spoiler"] == "true"
    assert client.calls[0][2]["photo"][0] == "photo.dat"


def test_parse_guest_message_as_effective_message():
    update = _parse_update(
        {
            "update_id": 10,
            "guest_message": {
                "message_id": 3,
                "date": 1,
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 44, "is_bot": False, "first_name": "Ada"},
                "text": "guest prompt",
                "guest_query_id": "gq_1",
            },
        }
    )

    assert update.effective_message is update.guest_message
    assert update.effective_message.text == "guest prompt"
    assert update.effective_user.first_name == "Ada"
    assert update.effective_chat.id == -1001


def test_message_handler_dispatches_business_and_guest_messages():
    seen = []

    async def callback(update, context):
        seen.append(update.effective_message.text)

    handler = MessageHandler(filters.TEXT, callback)

    business_update = Update(
        update_id=1,
        business_message=Message(
            message_id=1,
            date=1,
            chat=Chat(id=1, type="private"),
            from_user=User(id=2, is_bot=True, first_name="Bot"),
            text="business bot reply",
        ),
    )
    guest_update = Update(
        update_id=2,
        guest_message=Message(
            message_id=2,
            date=1,
            chat=Chat(id=1, type="private"),
            text="guest mode prompt",
        ),
    )

    assert handler.check_update(business_update)
    assert handler.check_update(guest_update)
    run(handler.handle(business_update, object()))
    run(handler.handle(guest_update, object()))

    assert seen == ["business bot reply", "guest mode prompt"]


def test_ptb_request_adapter_accepts_nanobot_kwargs():
    request = HTTPXRequest(
        connection_pool_size=4,
        pool_timeout=2.0,
        connect_timeout=3.0,
        read_timeout=4.0,
        proxy=None,
    )

    assert request.timeout.connect == 3.0
    assert request.timeout.read == 4.0
    run(request.aclose())


def test_updater_facade_expands_message_updates_for_api_10():
    async def scenario():
        bot = Bot("123:token", request=FakeClient())
        app = Application(bot)
        await app.updater.start_polling(allowed_updates=["message", "callback_query"])

        assert app._polling_task is not None
        coro = app._polling_task.get_coro()
        assert coro.cr_frame.f_locals["allowed_updates"] == [
            "message",
            "callback_query",
            "business_message",
            "edited_business_message",
            "guest_message",
        ]
        await app.shutdown()

    run(scenario())


def test_updater_stop_matches_nanobot_lifecycle():
    async def scenario():
        bot = Bot("123:token", request=FakeClient())
        app = Application(bot)
        await app.initialize()

        assert app._running is True
        await app.updater.stop()
        assert app._running is False

    run(scenario())


def test_application_shutdown_cancels_polling_and_closes_builder_clients():
    async def scenario():
        api_request = FakeClient()
        poll_request = FakeClient()
        app = (
            Application.builder()
            .token("123:token")
            .request(api_request)
            .get_updates_request(poll_request)
            .build()
        )
        await app.updater.start_polling(allowed_updates=["message"])

        assert app._polling_task is not None
        await app.shutdown()
        assert app._polling_task is None
        assert api_request.closed is True
        assert poll_request.closed is True

    run(scenario())
