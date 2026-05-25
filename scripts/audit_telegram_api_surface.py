"""Audit the native Telegram package against Telegram's live Bot API docs."""

from __future__ import annotations

import inspect
import re
import sys
from dataclasses import fields, is_dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import telegram
from telegram._bot import Bot


DOC_URL = "https://core.telegram.org/bots/api"
FEATURES_URL = "https://core.telegram.org/bots/features#bot-to-bot-communication"

RECENT_FIELD_REQUIREMENTS = {
    "User": {
        "supports_guest_queries",
        "can_manage_bots",
        "allows_users_to_create_topics",
    },
    "Message": {
        "guest_bot_caller_user",
        "guest_bot_caller_chat",
        "guest_query_id",
        "live_photo",
        "sender_tag",
        "reply_to_poll_option_id",
        "poll_option_added",
        "poll_option_deleted",
    },
    "Update": {
        "guest_message",
        "managed_bot",
    },
    "Chat": {
        "is_direct_messages",
    },
    "ChatPermissions": {
        "can_react_to_messages",
        "can_edit_tag",
    },
    "ChatMemberRestricted": {
        "can_react_to_messages",
        "can_edit_tag",
        "tag",
    },
    "ChatMemberMember": {
        "tag",
    },
    "ChatMemberAdministrator": {
        "can_manage_tags",
    },
    "ChatAdministratorRights": {
        "can_manage_tags",
    },
    "Poll": {
        "media",
        "explanation_media",
        "members_only",
        "country_codes",
        "correct_option_ids",
        "allows_revoting",
        "description",
        "description_entities",
    },
    "PollOption": {
        "media",
        "persistent_id",
        "added_by_user",
        "added_by_chat",
        "addition_date",
    },
    "PollAnswer": {
        "option_persistent_ids",
    },
    "ReplyParameters": {
        "poll_option_id",
    },
}

RECENT_METHOD_PARAMETER_REQUIREMENTS = {
    "answer_guest_query": {"guest_query_id", "result"},
    "get_chat_administrators": {"chat_id", "return_bots"},
    "send_poll": {
        "media",
        "explanation_media",
        "members_only",
        "country_codes",
        "correct_option_ids",
        "allows_revoting",
        "shuffle_options",
        "allow_adding_options",
        "hide_results_until_closes",
        "description",
        "description_parse_mode",
        "description_entities",
    },
    "promote_chat_member": {"can_manage_tags"},
    "get_managed_bot_access_settings": {"user_id"},
    "set_managed_bot_access_settings": {"user_id"},
    "get_user_personal_chat_messages": {"user_id"},
}


class _HeaderParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_h4 = False
        self._buffer: list[str] = []
        self.headers: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "h4":
            self._in_h4 = True
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h4" and self._in_h4:
            self.headers.append("".join(self._buffer).strip())
            self._in_h4 = False

    def handle_data(self, data: str) -> None:
        if self._in_h4:
            self._buffer.append(data)


def _snake_case(name: str) -> str:
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _local_field_names(type_name: str) -> set[str]:
    cls = getattr(telegram, type_name, None)
    if cls is None:
        return set()
    if is_dataclass(cls):
        return {field.name for field in fields(cls)}
    annotations = getattr(cls, "__annotations__", {})
    return set(annotations)


def _missing_recent_fields() -> list[str]:
    missing: list[str] = []
    for type_name, required_fields in RECENT_FIELD_REQUIREMENTS.items():
        local_fields = _local_field_names(type_name)
        for field_name in sorted(required_fields - local_fields):
            missing.append(f"{type_name}.{field_name}")
    return missing


def _missing_recent_method_parameters() -> list[str]:
    missing: list[str] = []
    for method_name, required_parameters in RECENT_METHOD_PARAMETER_REQUIREMENTS.items():
        method = getattr(Bot, method_name, None)
        if method is None:
            missing.append(f"Bot.{method_name}")
            continue
        parameters = set(inspect.signature(method).parameters)
        for parameter in sorted(required_parameters - parameters):
            missing.append(f"Bot.{method_name}({parameter})")
    return missing


def main() -> int:
    html = urlopen(DOC_URL, timeout=30).read().decode("utf-8", "replace")
    features_html = urlopen(FEATURES_URL, timeout=30).read().decode("utf-8", "replace")
    parser = _HeaderParser()
    parser.feed(html)

    official_methods = [h for h in parser.headers if re.match(r"^[a-z][A-Za-z0-9]+$", h)]
    official_types = [h for h in parser.headers if re.match(r"^[A-Z][A-Za-z0-9]+$", h)]

    local_methods = {
        name
        for name, obj in inspect.getmembers(Bot, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }
    missing_methods = [m for m in official_methods if _snake_case(m) not in local_methods]
    missing_types = [name for name in official_types if not hasattr(telegram, name)]
    missing_recent_fields = _missing_recent_fields()
    missing_recent_params = _missing_recent_method_parameters()
    has_release_marker = "May 8, 2026" in html and "Bot API 10.0" in html
    has_bot_to_bot_docs = "bot-to-bot-communication" in features_html and "Bot-to-Bot Communication" in features_html

    print(f"source={DOC_URL}")
    print(f"features_source={FEATURES_URL}")
    print(f"release_marker={'ok' if has_release_marker else 'missing'}")
    print(f"bot_to_bot_docs={'ok' if has_bot_to_bot_docs else 'missing'}")
    print(f"official_methods={len(official_methods)} method_missing={len(missing_methods)}")
    print(f"official_types={len(official_types)} type_import_missing={len(missing_types)}")
    print(
        "recent_field_requirements="
        f"{sum(len(v) for v in RECENT_FIELD_REQUIREMENTS.values())} "
        f"recent_field_missing={len(missing_recent_fields)}"
    )
    print(
        "recent_method_parameters="
        f"{sum(len(v) for v in RECENT_METHOD_PARAMETER_REQUIREMENTS.values())} "
        f"recent_method_parameter_missing={len(missing_recent_params)}"
    )

    if missing_methods:
        print("missing_methods:")
        print("\n".join(missing_methods))
    if missing_types:
        print("missing_types:")
        print("\n".join(missing_types))
    if missing_recent_fields:
        print("missing_recent_fields:")
        print("\n".join(missing_recent_fields))
    if missing_recent_params:
        print("missing_recent_method_parameters:")
        print("\n".join(missing_recent_params))

    failed = (
        missing_methods
        or missing_types
        or missing_recent_fields
        or missing_recent_params
        or not has_release_marker
        or not has_bot_to_bot_docs
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
