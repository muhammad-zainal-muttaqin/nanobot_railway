import sys
from pathlib import Path

PATCH_DIR = Path(__file__).resolve().parent.parent / "nanobot_railway_patches"
if str(PATCH_DIR) not in sys.path:
    sys.path.insert(0, str(PATCH_DIR))

import sitecustomize  # noqa: F401
from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram import TelegramChannel
from telegram import Chat, Message, Update, User


def test_railway_patch_adds_bot_to_bot_runtime_config():
    channel = TelegramChannel(
        {
            "enabled": True,
            "token": "",
            "botToBot": True,
            "botToBotAllowBots": ["@OtherBot"],
            "botToBotMaxPerMinute": 5,
            "botToBotMaxChainDepth": 3,
        },
        MessageBus(),
    )

    assert channel.config.bot_to_bot is True
    assert channel.config.bot_to_bot_allow_bots == ["@OtherBot"]
    assert channel.config.bot_to_bot_max_per_minute == 5
    assert channel.config.bot_to_bot_max_chain_depth == 3
    assert channel.is_allowed("bot:123|OtherBot")
    assert not channel.is_allowed("bot:123|BlockedBot")


def test_bot_allowlist_normalizes_internal_sender_forms():
    channel = TelegramChannel(
        {
            "enabled": True,
            "token": "",
            "botToBot": True,
            "botToBotAllowBots": ["bot:123|OtherBot"],
        },
        MessageBus(),
    )

    assert channel.is_allowed("bot:123|OtherBot")
    assert channel.is_allowed("bot:123|@OtherBot")


def test_nanobot_telegram_channel_uses_repo_native_package():
    import telegram
    from telegram.constants import BOT_API_VERSION

    assert "nanobot_railway\\telegram\\__init__.py" in telegram.__file__.replace("/", "\\")
    assert BOT_API_VERSION == "10.0"


def test_bot_origin_guest_message_flows_to_nanobot_bus():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=42,
            guest_message=Message(
                message_id=10,
                date=1,
                chat=Chat(id=100, type="private"),
                from_user=User(id=200, is_bot=True, first_name="Other", username="OtherBot"),
                text="hello from bot",
            ),
        )

        await channel._on_message(update, object())
        inbound = await bus.consume_inbound()
        return inbound

    import asyncio

    inbound = asyncio.run(scenario())
    assert inbound.sender_id == "bot:200|OtherBot"
    assert inbound.chat_id == "100"
    assert inbound.content == "hello from bot"
    assert inbound.metadata["is_bot"] is True
    assert inbound.metadata["sender_username"] == "OtherBot"


def test_bot_origin_business_message_flows_to_nanobot_bus():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@BusinessBot"],
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=43,
            business_message=Message(
                message_id=11,
                date=1,
                chat=Chat(id=101, type="private"),
                from_user=User(id=201, is_bot=True, first_name="Business", username="BusinessBot"),
                text="/status from business bot",
                business_connection_id="bc_1",
            ),
        )

        await channel._on_message(update, object())
        inbound = await bus.consume_inbound()
        return inbound

    import asyncio

    inbound = asyncio.run(scenario())
    assert inbound.sender_id == "bot:201|BusinessBot"
    assert inbound.chat_id == "101"
    assert inbound.content == "/status from business bot"
    assert inbound.metadata["is_bot"] is True
    assert inbound.metadata["sender_username"] == "BusinessBot"
    assert inbound.metadata["message_id"] == 11


def test_bot_origin_guest_command_flows_to_nanobot_bus():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
            },
            bus,
        )

        update = Update(
            update_id=44,
            guest_message=Message(
                message_id=12,
                date=1,
                chat=Chat(id=102, type="private"),
                from_user=User(id=202, is_bot=True, first_name="Other", username="OtherBot"),
                text="/status@ThisBot now",
            ),
        )

        await channel._forward_command(update, object())
        inbound = await bus.consume_inbound()
        return inbound

    import asyncio

    inbound = asyncio.run(scenario())
    assert inbound.sender_id == "bot:202|OtherBot"
    assert inbound.chat_id == "102"
    assert inbound.content == "/status now"
    assert inbound.metadata["is_bot"] is True


def test_bot_to_bot_chain_depth_marker_is_stripped_and_recorded():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
                "botToBotMaxChainDepth": 3,
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=45,
            guest_message=Message(
                message_id=13,
                date=1,
                chat=Chat(id=103, type="private"),
                from_user=User(id=203, is_bot=True, first_name="Other", username="OtherBot"),
                text="[nanobot:b2b-depth=2] continue",
            ),
        )

        await channel._on_message(update, object())
        return await bus.consume_inbound()

    import asyncio

    inbound = asyncio.run(scenario())
    assert inbound.content == "continue"
    assert inbound.metadata["bot_to_bot_chain_depth"] == 2


def test_bot_to_bot_chain_depth_limit_drops_message():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
                "botToBotMaxChainDepth": 2,
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=46,
            guest_message=Message(
                message_id=14,
                date=1,
                chat=Chat(id=104, type="private"),
                from_user=User(id=204, is_bot=True, first_name="Other", username="OtherBot"),
                text="[nanobot:b2b-depth=2] stop",
            ),
        )

        await channel._on_message(update, object())
        return bus.inbound_size

    import asyncio

    assert asyncio.run(scenario()) == 0


def test_bot_to_bot_rate_limit_drops_after_configured_count():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
                "botToBotMaxPerMinute": 1,
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        for message_id, text in [(15, "first"), (16, "second")]:
            update = Update(
                update_id=50 + message_id,
                guest_message=Message(
                    message_id=message_id,
                    date=1,
                    chat=Chat(id=105, type="private"),
                    from_user=User(id=205, is_bot=True, first_name="Other", username="OtherBot"),
                    text=text,
                ),
            )
            await channel._on_message(update, object())

        first = await bus.consume_inbound()
        return first, bus.inbound_size

    import asyncio

    first, remaining = asyncio.run(scenario())
    assert first.content == "first"
    assert remaining == 0


def test_bot_to_bot_duplicate_message_is_dropped():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=80,
            guest_message=Message(
                message_id=20,
                date=1,
                chat=Chat(id=108, type="private"),
                from_user=User(id=208, is_bot=True, first_name="Other", username="OtherBot"),
                text="same",
            ),
        )

        await channel._on_message(update, object())
        await channel._on_message(update, object())
        first = await bus.consume_inbound()
        return first, bus.inbound_size

    import asyncio

    first, remaining = asyncio.run(scenario())
    assert first.content == "same"
    assert remaining == 0


def test_bot_to_bot_reply_increments_chain_depth_marker():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["@OtherBot"],
                "botToBotMaxChainDepth": 5,
            },
            bus,
        )

        async def no_media(*args, **kwargs):
            return [], []

        async def no_reaction(*args, **kwargs):
            return None

        channel._download_message_media = no_media
        channel._add_reaction = no_reaction
        channel._start_typing = lambda *args, **kwargs: None

        update = Update(
            update_id=81,
            guest_message=Message(
                message_id=21,
                date=1,
                chat=Chat(id=109, type="private"),
                from_user=User(id=209, is_bot=True, first_name="Other", username="OtherBot"),
                text="[nanobot:b2b-depth=2] prompt",
            ),
        )

        await channel._on_message(update, object())
        inbound = await bus.consume_inbound()
        sent = {}

        class FakeBot:
            async def send_message(self, **kwargs):
                sent.update(kwargs)
                return Message(
                    message_id=22,
                    date=1,
                    chat=Chat(id=kwargs["chat_id"], type="private"),
                    text=kwargs["text"],
                )

        class FakeApp:
            bot = FakeBot()

        channel._app = FakeApp()
        await channel.send(
            OutboundMessage(
                channel="telegram",
                chat_id="109",
                content="reply",
                metadata={"origin_message_id": inbound.metadata["origin_message_id"]},
            )
        )
        return sent["text"]

    import asyncio

    text = asyncio.run(scenario())
    assert text.startswith("[nanobot:b2b-depth=3] reply")


def test_bot_to_bot_ignores_own_bot_messages():
    async def scenario():
        bus = MessageBus()
        channel = TelegramChannel(
            {
                "enabled": True,
                "token": "",
                "allowFrom": ["*"],
                "botToBot": True,
                "botToBotAllowBots": ["*"],
            },
            bus,
        )
        channel._bot_user_id = 999
        channel._bot_username = "ThisBot"

        update = Update(
            update_id=90,
            guest_message=Message(
                message_id=17,
                date=1,
                chat=Chat(id=106, type="private"),
                from_user=User(id=999, is_bot=True, first_name="This", username="ThisBot"),
                text="self echo",
            ),
        )

        await channel._on_message(update, object())
        return bus.inbound_size

    import asyncio

    assert asyncio.run(scenario()) == 0
