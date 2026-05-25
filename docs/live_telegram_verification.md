# Live Telegram Verification Runbook

Use this runbook to prove the remaining external requirement: real Telegram Bot API v10 connectivity and bot-to-bot delivery using the native SDK.

## Prerequisites

1. Create or choose the receiving bot in BotFather.
2. Enable Bot-to-Bot Communication Mode for the receiving bot.
3. Create or choose the sender bot in BotFather.
4. Enable Bot-to-Bot Communication Mode for the sender bot too.
5. Install local dependencies and remove `python-telegram-bot`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip pytest "nanobot-ai==0.2.0" -r requirements.txt
.\.venv\Scripts\python.exe -m pip uninstall -y python-telegram-bot
```

## Outbound Private Bot-To-Bot Send

Set the receiving bot token and sender target:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_BOT_TO_BOT_TARGET="@OtherBot"
$env:TELEGRAM_REQUIRE_BOT_TO_BOT="0"
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```

Expected successful evidence includes:

```text
status=ok
bot_api_version=10.0
python_telegram_bot_installed=False
bot_to_bot_send={...}
```

## Inbound Bot-Origin Receive

Set the expected sender and a poll window:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_EXPECT_BOT_UPDATE_FROM="@OtherBot"
$env:TELEGRAM_UPDATE_POLL_SECONDS="30"
$env:TELEGRAM_REQUIRE_BOT_TO_BOT="0"
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```

During the poll window, send a message from `@OtherBot` to the receiving bot.

Expected successful evidence includes:

```text
status=ok
bot_to_bot_receive={'matched': True, ...}
```

## Group Or Forum Topic Send

Add both bots to a group. `TELEGRAM_GROUP_CHAT_ID` must be a negative group/supergroup ID. For forum topics, set the positive topic ID:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_GROUP_CHAT_ID="-1001234567890"
$env:TELEGRAM_MESSAGE_THREAD_ID="123"
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```

Expected successful evidence includes:

```text
group_send={...}
```

## Completion Criteria

The live requirement is complete when:

- `scripts\verify_telegram_live.py` returns exit code `0`.
- Output includes `status=ok`.
- Output includes `python_telegram_bot_installed=False`.
- For private bot-to-bot send proof, output includes `bot_to_bot_send`.
- For receive proof, output includes `bot_to_bot_receive={'matched': True, ...}`.

For the final proof run, set strict bot-to-bot mode so the verifier fails unless private send, receive, and group/topic evidence are present:

```powershell
$env:TELEGRAM_BOT_TOKEN="123456:ABC..."
$env:TELEGRAM_BOT_TO_BOT_TARGET="@OtherBot"
$env:TELEGRAM_EXPECT_BOT_UPDATE_FROM="@OtherBot"
$env:TELEGRAM_GROUP_CHAT_ID="-1001234567890"
# Optional for forum topics:
# $env:TELEGRAM_MESSAGE_THREAD_ID="123"
$env:TELEGRAM_UPDATE_POLL_SECONDS="30"
$env:TELEGRAM_REQUIRE_BOT_TO_BOT="1"
.\.venv\Scripts\python.exe scripts\verify_telegram_live.py
```
