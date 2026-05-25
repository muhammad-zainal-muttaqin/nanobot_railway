# Railway Template Publishing Guide

Use this when publishing the repository as a public Railway template. The goal is a one-click deploy that starts safely, stores state on a volume, and lets deployers configure their own bot and LLM credentials.

## Service Settings

Configure the service in Railway's template composer:

* Source: this GitHub repository, main branch.
* Builder: Dockerfile.
* Start command: `/app/start.sh`.
* Public networking: HTTP enabled.
* Healthcheck path: `/health`.
* Volume: attach a persistent volume mounted at `/data`.

`railway.toml` already records the Dockerfile builder, start command, and healthcheck path. The persistent volume still needs to be attached in the Railway template composer.

## Recommended Template Variables

Set these as service variables in the template composer. Mark secrets as hidden/sealed where Railway offers that option.

| Variable | Required | Suggested value | Description |
| --- | --- | --- | --- |
| `ADMIN_USERNAME` | Yes | `admin` | Basic Auth username for the dashboard. |
| `ADMIN_PASSWORD` | Yes | `${{ secret(32) }}` | Generated dashboard password. Do not hardcode a shared password. |
| `NANOBOT_AGENTS__DEFAULTS__WORKSPACE` | Yes | `/data/.nanobot/workspace` | Stores nanobot workspace files on the mounted `/data` volume. |
| `OPENAI_COMPATIBLE_API_KEY` | Optional | empty | API key for an OpenAI-compatible endpoint. |
| `OPENAI_COMPATIBLE_API_BASE` | Optional | empty | Base URL ending in `/v1`, for example `https://api.example.com/v1`. |
| `OPENAI_COMPATIBLE_MODEL` | Optional | empty | Model name expected by the compatible endpoint. |
| `TELEGRAM_ENABLED` | Optional | `0` | Set to `1` after adding a bot token. |
| `TELEGRAM_BOT_TOKEN` | Optional | empty | BotFather token for the deployer's own bot. |
| `TELEGRAM_ALLOWED_USERS` | Optional | `*` | Use `*` for public access or a comma-separated allowlist of Telegram user IDs. |
| `TELEGRAM_BOT_TO_BOT` | Optional | `0` | Set to `1` only after enabling Bot-to-Bot Communication Mode in BotFather. |
| `TELEGRAM_BOT_TO_BOT_ALLOW_BOTS` | Optional | empty | Trusted bot usernames/IDs, for example `@AkuHolo_bot,@S_o_R_a_bot`. |
| `TELEGRAM_BOT_TO_BOT_MAX_PER_MINUTE` | Optional | `12` | Per-bot loop protection rate limit. |
| `TELEGRAM_BOT_TO_BOT_MAX_CHAIN_DEPTH` | Optional | `6` | Bot-to-bot loop protection chain depth. |

Leave optional variables out if they are not needed. Empty optional variables are ignored by the runtime override layer, but they make the template form longer.

## OpenAI-Compatible Defaults

For most public template users, prefer the three `OPENAI_COMPATIBLE_*` variables:

```text
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_API_BASE=
OPENAI_COMPATIBLE_MODEL=
```

When any of these are set, the app writes them into nanobot's `custom` provider at runtime. If `NANOBOT_PROVIDER` is not explicitly set, the app selects `custom` automatically.

Advanced users can still use nanobot path variables:

```text
NANOBOT_PROVIDER=custom
NANOBOT_MODEL=my-model
NANOBOT_PROVIDERS__CUSTOM__API_KEY=sk-...
NANOBOT_PROVIDERS__CUSTOM__API_BASE=https://api.example.com/v1
```

## Optional Direct Provider Shortcuts

Only add these to the template if your audience needs them. Otherwise, users can configure providers from the dashboard after deployment.

```text
OPENAI_API_KEY=
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
DEEPSEEK_API_KEY=
MISTRAL_API_KEY=
MOONSHOT_API_KEY=
DASHSCOPE_API_KEY=
NVIDIA_API_KEY=
```

## Do Not Include Live Verifier Variables

These are for maintainers only and should not be part of the public template form:

```text
TELEGRAM_BOT_TO_BOT_TARGET
TELEGRAM_GROUP_CHAT_ID
TELEGRAM_MESSAGE_THREAD_ID
TELEGRAM_EXPECT_BOT_UPDATE_FROM
TELEGRAM_UPDATE_POLL_SECONDS
TELEGRAM_REQUIRE_BOT_TO_BOT
```

Keep them in local shell sessions only when running `scripts/verify_telegram_live.py`.

## Publish Checklist

Before publishing:

* Run `python scripts/verify_all.py`.
* Confirm the Railway template has a volume mounted at `/data`.
* Confirm the template has public HTTP networking enabled.
* Confirm `ADMIN_PASSWORD` uses `${{ secret(32) }}` in the template composer.
* Confirm the template description tells users to redeploy/restart after changing variables.
* Do not include your personal Telegram token, provider keys, test bot chat IDs, or live verifier variables.
