"""Telegram Bot API type definitions — Bot API v10 (May 8, 2026)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class TelegramObject:
    """Flexible base for Bot API objects without a typed dataclass yet."""

    def __init__(self, **data: Any):
        self._raw_data = dict(data)
        for key, value in data.items():
            setattr(self, "from_user" if key == "from" else key, value)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._raw_data)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._raw_data!r})"


_GENERIC_TYPE_NAMES = (
    "MessageId", "InaccessibleMessage", "MaybeInaccessibleMessage", "TextQuote",
    "ExternalReplyInfo", "MessageOrigin", "MessageOriginUser", "MessageOriginHiddenUser",
    "MessageOriginChat", "MessageOriginChannel", "Story", "VideoQuality",
    "PaidMediaLivePhoto", "PaidMediaPreview", "PollMedia", "InputPollMedia",
    "InputPollOptionMedia", "InputPollOption", "ChecklistTask", "Checklist",
    "InputChecklistTask", "InputChecklist", "ChecklistTasksDone", "ChecklistTasksAdded",
    "WebAppData", "ManagedBotCreated", "ManagedBotUpdated", "PollOptionAdded",
    "PollOptionDeleted", "BackgroundFill", "BackgroundFillSolid", "BackgroundFillGradient",
    "BackgroundFillFreeformGradient", "BackgroundType", "BackgroundTypeFill",
    "BackgroundTypeWallpaper", "BackgroundTypePattern", "BackgroundTypeChatTheme",
    "ChatBackground", "ForumTopicEdited", "SharedUser", "UsersShared", "ChatShared",
    "VideoChatScheduled", "VideoChatStarted", "VideoChatEnded",
    "VideoChatParticipantsInvited", "PaidMessagePriceChanged",
    "DirectMessagePriceChanged", "SuggestedPostApproved", "SuggestedPostApprovalFailed",
    "SuggestedPostDeclined", "SuggestedPostPaid", "SuggestedPostRefunded",
    "GiveawayCompleted", "SuggestedPostPrice", "SuggestedPostInfo",
    "SuggestedPostParameters", "DirectMessagesTopic", "UserProfilePhotos",
    "UserProfileAudios", "KeyboardButtonRequestUsers", "KeyboardButtonRequestManagedBot",
    "LoginUrl", "SwitchInlineQueryChosenChat", "CopyTextButton", "ChatPhoto",
    "Birthdate", "UserRating", "StoryAreaPosition", "LocationAddress", "StoryAreaType",
    "StoryAreaTypeLocation", "StoryAreaTypeSuggestedReaction", "StoryAreaTypeLink",
    "StoryAreaTypeWeather", "StoryAreaTypeUniqueGift", "StoryArea",
    "ReactionTypeCustomEmoji", "GiftBackground", "UniqueGiftModel", "UniqueGiftSymbol",
    "UniqueGiftBackdropColors", "UniqueGiftBackdrop", "UniqueGiftColors", "UniqueGift",
    "GiftInfo", "UniqueGiftInfo", "OwnedGift", "OwnedGiftRegular", "OwnedGiftUnique",
    "OwnedGifts", "BotAccessSettings", "AcceptedGiftTypes", "StarAmount", "BotCommandScope",
    "BotName", "BotDescription", "BotShortDescription", "ChatBoostSource", "ChatBoostSourcePremium",
    "ChatBoostSourceGiftCode", "ChatBoostSourceGiveaway", "ChatOwnerLeft",
    "ChatOwnerChanged", "UserChatBoosts", "BusinessBotRights", "SentWebAppMessage",
    "PreparedInlineMessage", "PreparedKeyboardButton", "ResponseParameters",
    "InputMediaLivePhoto", "InputMediaLocation", "InputMediaSticker", "InputMediaVenue",
    "InputFile", "InputPaidMedia", "InputPaidMediaLivePhoto", "InputPaidMediaPhoto",
    "InputPaidMediaVideo", "InputProfilePhoto", "InputProfilePhotoStatic",
    "InputProfilePhotoAnimated", "InputStoryContent", "InputStoryContentPhoto",
    "InputStoryContentVideo", "InputSticker", "InlineQueryResultsButton",
    "InlineQueryResult", "InlineQueryResultArticle", "InlineQueryResultPhoto",
    "InlineQueryResultGif", "InlineQueryResultMpeg4Gif", "InlineQueryResultVideo",
    "InlineQueryResultAudio", "InlineQueryResultVoice", "InlineQueryResultDocument",
    "InlineQueryResultLocation", "InlineQueryResultVenue", "InlineQueryResultContact",
    "InlineQueryResultGame", "InlineQueryResultCachedPhoto", "InlineQueryResultCachedGif",
    "InlineQueryResultCachedMpeg4Gif", "InlineQueryResultCachedSticker",
    "InlineQueryResultCachedDocument", "InlineQueryResultCachedVideo",
    "InlineQueryResultCachedVoice", "InlineQueryResultCachedAudio", "InputMessageContent",
    "InputTextMessageContent", "InputLocationMessageContent", "InputVenueMessageContent",
    "InputContactMessageContent", "InputInvoiceMessageContent", "RefundedPayment",
    "PaidMediaPurchased", "RevenueWithdrawalState", "RevenueWithdrawalStatePending",
    "RevenueWithdrawalStateSucceeded", "RevenueWithdrawalStateFailed", "AffiliateInfo",
    "TransactionPartner", "TransactionPartnerUser", "TransactionPartnerChat",
    "TransactionPartnerAffiliateProgram", "TransactionPartnerFragment",
    "TransactionPartnerTelegramAds", "TransactionPartnerTelegramApi",
    "TransactionPartnerOther", "EncryptedCredentials", "PassportElementError",
    "PassportElementErrorDataField", "PassportElementErrorFrontSide",
    "PassportElementErrorReverseSide", "PassportElementErrorSelfie",
    "PassportElementErrorFile", "PassportElementErrorFiles",
    "PassportElementErrorTranslationFile", "PassportElementErrorTranslationFiles",
    "PassportElementErrorUnspecified", "CallbackGame",
)


for _type_name in _GENERIC_TYPE_NAMES:
    globals().setdefault(_type_name, type(_type_name, (TelegramObject,), {"__module__": __name__}))


@dataclass(frozen=True)
class User:
    id: int
    is_bot: bool
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    added_to_attachment_menu: bool | None = None
    can_join_groups: bool | None = None
    can_read_all_group_messages: bool | None = None
    supports_inline_queries: bool | None = None
    can_connect_to_business: bool | None = None
    has_main_web_app: bool | None = None
    supports_guest_queries: bool | None = None
    has_topics_enabled: bool | None = None
    allows_users_to_create_topics: bool | None = None
    can_manage_bots: bool | None = None


@dataclass(frozen=True)
class Chat:
    id: int
    type: str
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_forum: bool | None = None
    is_direct_messages: bool | None = None


@dataclass(frozen=True)
class ChatFullInfo:
    id: int
    type: str
    title: str | None = None
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    accent_color_id: int | None = None
    background_custom_emoji_id: str | None = None
    profile_accent_color_id: int | None = None
    profile_background_custom_emoji_id: str | None = None
    emoji_status_custom_emoji_id: str | None = None
    emoji_status_expiration_date: int | None = None
    bio: str | None = None
    has_private_forwards: bool | None = None
    has_restricted_voice_and_video_messages: bool | None = None
    join_to_send_messages: bool | None = None
    join_by_request: bool | None = None
    description: str | None = None
    invite_link: str | None = None
    pinned_message: Message | None = None
    permissions: ChatPermissions | None = None
    can_send_paid_media: bool | None = None
    slow_mode_delay: int | None = None
    unrestrict_boost_count: int | None = None
    message_auto_delete_time: int | None = None
    has_aggressive_anti_spam_enabled: bool | None = None
    has_hidden_members: bool | None = None
    has_protected_content: bool | None = None
    has_visible_history: bool | None = None
    sticker_set_name: str | None = None
    can_set_sticker_set: bool | None = None
    custom_emoji_sticker_set_name: str | None = None
    linked_chat_id: int | None = None
    location: ChatLocation | None = None
    is_forum: bool | None = None
    is_direct_messages: bool | None = None
    available_reactions: list[ReactionType] | None = None
    paid_media_allowed: bool | None = None
    paid_media_message_number: int | None = None
    business_connection_restricted: bool | None = None
    guest_avatars: list[GuestAvatar] | None = None
    primary_bot: User | None = None
    managed_bots: list[ManagedBotInChat] | None = None


@dataclass(frozen=True)
class GuestAvatar:
    url: str
    file_unique_id: str
    type: str


@dataclass(frozen=True)
class ManagedBotInChat:
    user: User
    access_settings: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChatLocation:
    location: Location
    address: str


@dataclass(frozen=True)
class MessageEntity:
    type: str
    offset: int
    length: int
    url: str | None = None
    user: User | None = None
    language: str | None = None
    custom_emoji_id: str | None = None


@dataclass(frozen=True)
class PhotoSize:
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: int | None = None


@dataclass(frozen=True)
class Voice:
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class Audio:
    file_id: str
    file_unique_id: str
    duration: int
    performer: str | None = None
    title: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class Document:
    file_id: str
    file_unique_id: str
    thumbnail: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class Video:
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    cover: list[PhotoSize] | None = None
    start_timestamp: int | None = None


@dataclass(frozen=True)
class VideoNote:
    file_id: str
    file_unique_id: str
    length: int
    duration: int
    thumbnail: PhotoSize | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class Animation:
    file_id: str
    file_unique_id: str
    width: int
    height: int
    duration: int
    thumbnail: PhotoSize | None = None
    file_name: str | None = None
    mime_type: str | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class Location:
    longitude: float
    latitude: float
    horizontal_accuracy: float | None = None
    live_period: int | None = None
    heading: int | None = None
    proximity_alert_radius: int | None = None


@dataclass(frozen=True)
class LivePhoto:
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: int | None = None
    video: Video | None = None


@dataclass(frozen=True)
class SentGuestMessage:
    message_id: int | None = None
    date: int | None = None


# ─── Reply Markup Types ─────────────────────


@dataclass(frozen=True)
class WebAppInfo:
    url: str


@dataclass(frozen=True)
class KeyboardButtonPollType:
    type: str | None = None


@dataclass(frozen=True)
class KeyboardButtonRequestUser:
    request_id: int
    user_is_bot: bool | None = None
    user_is_premium: bool | None = None


@dataclass(frozen=True)
class KeyboardButtonRequestChat:
    request_id: int
    chat_is_channel: bool
    chat_is_forum: bool | None = None
    chat_has_username: bool | None = None
    chat_is_created: bool | None = None
    user_administrator_rights: ChatAdministratorRights | None = None
    bot_administrator_rights: ChatAdministratorRights | None = None
    bot_is_member: bool | None = None
    request_title: bool | None = None
    request_username: bool | None = None
    request_photo: bool | None = None


@dataclass(frozen=True)
class KeyboardButton:
    text: str
    request_user: KeyboardButtonRequestUser | None = None
    request_chat: KeyboardButtonRequestChat | None = None
    request_contact: bool | None = None
    request_location: bool | None = None
    request_poll: KeyboardButtonPollType | None = None
    web_app: WebAppInfo | None = None


@dataclass(frozen=True)
class ReplyKeyboardMarkup:
    keyboard: list[list[KeyboardButton]]
    is_persistent: bool | None = None
    resize_keyboard: bool | None = None
    one_time_keyboard: bool | None = None
    input_field_placeholder: str | None = None
    selective: bool | None = None


@dataclass(frozen=True)
class ReplyKeyboardRemove:
    remove_keyboard: bool = True
    selective: bool | None = None


@dataclass(frozen=True)
class ForceReply:
    force_reply: bool = True
    input_field_placeholder: str | None = None
    selective: bool | None = None


@dataclass(frozen=True)
class InlineKeyboardButton:
    text: str
    url: str | None = None
    callback_data: str | None = None
    web_app: WebAppInfo | None = None
    login_url: dict | None = None
    switch_inline_query: str | None = None
    switch_inline_query_current_chat: str | None = None
    callback_game: dict | None = None
    pay: bool | None = None
    copy_text: dict | None = None
    icon_custom_emoji_id: str | None = None
    style: str | None = None


@dataclass(frozen=True)
class InlineKeyboardMarkup:
    inline_keyboard: list[list[InlineKeyboardButton]]


# ─── Bot Commands ──────────────────────────


@dataclass(frozen=True)
class BotCommand:
    command: str
    description: str


@dataclass(frozen=True)
class BotCommandScopeDefault:
    type: str = "default"


@dataclass(frozen=True)
class BotCommandScopeAllPrivateChats:
    type: str = "all_private_chats"


@dataclass(frozen=True)
class BotCommandScopeAllGroupChats:
    type: str = "all_group_chats"


@dataclass(frozen=True)
class BotCommandScopeAllChatAdministrators:
    type: str = "all_chat_administrators"


@dataclass(frozen=True)
class BotCommandScopeChat:
    chat_id: int | str
    type: str = "chat"


@dataclass(frozen=True)
class BotCommandScopeChatAdministrators:
    chat_id: int | str
    type: str = "chat_administrators"


@dataclass(frozen=True)
class BotCommandScopeChatMember:
    chat_id: int | str
    user_id: int
    type: str = "chat_member"


# ─── Chat Permissions & Invite Links ────────


@dataclass(frozen=True)
class ChatPermissions:
    can_send_messages: bool | None = None
    can_send_audios: bool | None = None
    can_send_documents: bool | None = None
    can_send_photos: bool | None = None
    can_send_videos: bool | None = None
    can_send_video_notes: bool | None = None
    can_send_voice_notes: bool | None = None
    can_send_polls: bool | None = None
    can_send_other_messages: bool | None = None
    can_add_web_page_previews: bool | None = None
    can_change_info: bool | None = None
    can_invite_users: bool | None = None
    can_pin_messages: bool | None = None
    can_manage_topics: bool | None = None
    can_edit_tag: bool | None = None
    can_send_paid_media: bool | None = None
    can_react_to_messages: bool | None = None


@dataclass(frozen=True)
class ChatInviteLink:
    invite_link: str
    creator: User
    creates_join_request: bool
    is_primary: bool
    is_revoked: bool
    name: str | None = None
    expire_date: int | None = None
    member_limit: int | None = None
    pending_join_request_count: int | None = None


@dataclass(frozen=True)
class ChatAdministratorRights:
    is_anonymous: bool
    can_manage_chat: bool
    can_delete_messages: bool
    can_manage_video_chats: bool
    can_restrict_members: bool
    can_promote_members: bool
    can_change_info: bool
    can_invite_users: bool
    can_post_stories: bool | None = None
    can_edit_stories: bool | None = None
    can_delete_stories: bool | None = None
    can_post_messages: bool | None = None
    can_edit_messages: bool | None = None
    can_pin_messages: bool | None = None
    can_manage_topics: bool | None = None
    can_manage_tags: bool | None = None


# ─── Chat Member Types ──────────────────────


@dataclass(frozen=True)
class ChatMemberOwner:
    user: User
    is_anonymous: bool
    status: str = "creator"
    custom_title: str | None = None


@dataclass(frozen=True)
class ChatMemberAdministrator:
    user: User
    can_be_edited: bool
    is_anonymous: bool
    can_manage_chat: bool
    can_delete_messages: bool
    can_manage_video_chats: bool
    can_restrict_members: bool
    can_promote_members: bool
    can_change_info: bool
    can_invite_users: bool
    status: str = "administrator"
    can_post_stories: bool | None = None
    can_edit_stories: bool | None = None
    can_delete_stories: bool | None = None
    can_post_messages: bool | None = None
    can_edit_messages: bool | None = None
    can_pin_messages: bool | None = None
    can_manage_topics: bool | None = None
    can_manage_tags: bool | None = None
    custom_title: str | None = None


@dataclass(frozen=True)
class ChatMemberMember:
    user: User
    status: str = "member"
    tag: str | None = None
    until_date: int | None = None


@dataclass(frozen=True)
class ChatMemberRestricted:
    user: User
    is_member: bool
    can_send_messages: bool
    can_send_audios: bool
    can_send_documents: bool
    can_send_photos: bool
    can_send_videos: bool
    can_send_video_notes: bool
    can_send_voice_notes: bool
    can_send_polls: bool
    can_send_other_messages: bool
    can_add_web_page_previews: bool
    can_change_info: bool
    can_invite_users: bool
    can_pin_messages: bool
    can_manage_topics: bool
    can_react_to_messages: bool | None = None
    can_edit_tag: bool | None = None
    tag: str | None = None
    status: str = "restricted"
    until_date: int | None = None


@dataclass(frozen=True)
class ChatMemberLeft:
    user: User
    status: str = "left"


@dataclass(frozen=True)
class ChatMemberBanned:
    user: User
    until_date: int
    status: str = "kicked"


ChatMember = (
    ChatMemberOwner
    | ChatMemberAdministrator
    | ChatMemberMember
    | ChatMemberRestricted
    | ChatMemberLeft
    | ChatMemberBanned
)


@dataclass(frozen=True)
class ChatMemberUpdated:
    chat: Chat
    from_user: User
    date: int
    old_chat_member: ChatMember
    new_chat_member: ChatMember
    invite_link: ChatInviteLink | None = None
    via_join_request: bool | None = None
    via_chat_folder_invite_link: bool | None = None


@dataclass(frozen=True)
class ChatJoinRequest:
    chat: Chat
    from_user: User
    user_chat_id: int
    date: int
    bio: str | None = None
    invite_link: ChatInviteLink | None = None


# ─── Menu Button ────────────────────────────


@dataclass(frozen=True)
class MenuButtonCommands:
    type: str = "commands"


@dataclass(frozen=True)
class MenuButtonWebApp:
    text: str
    web_app: WebAppInfo
    type: str = "web_app"


@dataclass(frozen=True)
class MenuButtonDefault:
    type: str = "default"


MenuButton = MenuButtonCommands | MenuButtonWebApp | MenuButtonDefault


# ─── Polls ─────────────────────────────────


@dataclass(frozen=True)
class PollOption:
    text: str
    voter_count: int
    text_entities: list[MessageEntity] | None = None
    media: PollMedia | None = None
    persistent_id: str | None = None
    added_by_user: User | None = None
    added_by_chat: Chat | None = None
    addition_date: int | None = None


@dataclass(frozen=True)
class Poll:
    id: str
    question: str
    options: list[PollOption]
    total_voter_count: int
    is_closed: bool
    is_anonymous: bool
    type: str
    allows_multiple_answers: bool
    question_entities: list[MessageEntity] | None = None
    correct_option_id: int | None = None
    correct_option_ids: list[int] | None = None
    explanation: str | None = None
    explanation_entities: list[MessageEntity] | None = None
    media: PollMedia | None = None
    explanation_media: PollMedia | None = None
    members_only: bool | None = None
    country_codes: list[str] | None = None
    allows_revoting: bool | None = None
    description: str | None = None
    description_entities: list[MessageEntity] | None = None
    open_period: int | None = None
    close_date: int | None = None


@dataclass(frozen=True)
class PollAnswer:
    poll_id: str
    option_ids: list[int]
    option_persistent_ids: list[str] | None = None
    voter_chat: Chat | None = None
    user: User | None = None


# ─── Stickers ──────────────────────────────


@dataclass(frozen=True)
class MaskPosition:
    point: str
    x_shift: float
    y_shift: float
    scale: float


@dataclass(frozen=True)
class Sticker:
    file_id: str
    file_unique_id: str
    type: str
    width: int
    height: int
    is_animated: bool
    is_video: bool
    thumbnail: PhotoSize | None = None
    emoji: str | None = None
    set_name: str | None = None
    premium_animation: File | None = None
    mask_position: MaskPosition | None = None
    custom_emoji_id: str | None = None
    needs_repainting: bool | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class StickerSet:
    name: str
    title: str
    sticker_type: str
    stickers: list[Sticker]
    thumbnail: PhotoSize | None = None


# ─── Dice / Contact / Venue ────────────────


@dataclass(frozen=True)
class Dice:
    emoji: str
    value: int


@dataclass(frozen=True)
class Contact:
    phone_number: str
    first_name: str
    last_name: str | None = None
    user_id: int | None = None
    vcard: str | None = None


@dataclass(frozen=True)
class Venue:
    location: Location
    title: str
    address: str
    foursquare_id: str | None = None
    foursquare_type: str | None = None
    google_place_id: str | None = None
    google_place_type: str | None = None


# ─── Inline Mode ──────────────────────────


@dataclass(frozen=True)
class InlineQuery:
    id: str
    from_user: User
    query: str
    offset: str
    chat_type: str | None = None
    location: Location | None = None


@dataclass(frozen=True)
class ChosenInlineResult:
    result_id: str
    from_user: User
    query: str
    location: Location | None = None
    inline_message_id: str | None = None


# ─── Payments ─────────────────────────────


@dataclass(frozen=True)
class ShippingAddress:
    country_code: str
    state: str
    city: str
    street_line1: str
    street_line2: str
    post_code: str


@dataclass(frozen=True)
class OrderInfo:
    name: str | None = None
    phone_number: str | None = None
    email: str | None = None
    shipping_address: ShippingAddress | None = None


@dataclass(frozen=True)
class Invoice:
    title: str
    description: str
    start_parameter: str
    currency: str
    total_amount: int


@dataclass(frozen=True)
class SuccessfulPayment:
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
    shipping_option_id: str | None = None
    order_info: OrderInfo | None = None


@dataclass(frozen=True)
class ShippingQuery:
    id: str
    from_user: User
    invoice_payload: str
    shipping_address: ShippingAddress


@dataclass(frozen=True)
class PreCheckoutQuery:
    id: str
    from_user: User
    currency: str
    total_amount: int
    invoice_payload: str
    shipping_option_id: str | None = None
    order_info: OrderInfo | None = None


@dataclass(frozen=True)
class PaidMedia:
    pass  # Base for paid media variants


@dataclass(frozen=True)
class PaidMediaPhoto:
    photo: list[PhotoSize]
    type: str = "photo"


@dataclass(frozen=True)
class PaidMediaVideo:
    video: Video
    type: str = "video"


@dataclass(frozen=True)
class PaidMediaPreviewed:
    photo: list[PhotoSize] | None = None
    video: Video | None = None
    type: str = "previewed"


@dataclass(frozen=True)
class PaidMediaInfo:
    star_count: int
    paid_media: list[PaidMedia]


# ─── Games ────────────────────────────────


@dataclass(frozen=True)
class Game:
    title: str
    description: str
    photo: list[PhotoSize]
    text: str | None = None
    text_entities: list[MessageEntity] | None = None
    animation: Animation | None = None


@dataclass(frozen=True)
class GameHighScore:
    position: int
    user: User
    score: int


# ─── Passport ─────────────────────────────


@dataclass(frozen=True)
class PassportFile:
    file_id: str
    file_unique_id: str
    file_size: int
    file_date: int


@dataclass(frozen=True)
class EncryptedPassportElement:
    type: str
    hash: str
    data: str | None = None
    phone_number: str | None = None
    email: str | None = None
    files: list[PassportFile] | None = None
    front_side: PassportFile | None = None
    reverse_side: PassportFile | None = None
    selfie: PassportFile | None = None
    translation: list[PassportFile] | None = None


@dataclass(frozen=True)
class PassportData:
    data: list[EncryptedPassportElement]
    credentials: dict


# ─── Forum Topics ─────────────────────────


@dataclass(frozen=True)
class ForumTopic:
    message_thread_id: int
    name: str
    icon_color: int
    icon_custom_emoji_id: str | None = None


@dataclass(frozen=True)
class ForumTopicCreated:
    name: str
    icon_color: int
    icon_custom_emoji_id: str | None = None


@dataclass(frozen=True)
class ForumTopicClosed:
    pass


@dataclass(frozen=True)
class ForumTopicReopened:
    pass


@dataclass(frozen=True)
class GeneralForumTopicHidden:
    pass


@dataclass(frozen=True)
class GeneralForumTopicUnhidden:
    pass


@dataclass(frozen=True)
class WriteAccessAllowed:
    from_request: bool | None = None
    web_app_name: str | None = None
    from_attachment_menu: bool | None = None


@dataclass(frozen=True)
class Giveaway:
    chats: list[Chat]
    winners_selection_date: int
    winner_count: int
    only_new_members: bool | None = None
    has_public_winners: bool | None = None
    prize_description: str | None = None
    country_codes: list[str] | None = None
    premium_subscription_month_count: int | None = None
    prize_star_count: int | None = None


@dataclass(frozen=True)
class GiveawayCreated:
    pass


@dataclass(frozen=True)
class GiveawayWinners:
    chat: Chat
    giveaway_message_id: int
    winners_selection_date: int
    winner_count: int
    winners: list[User]
    additional_chat_count: int | None = None
    premium_subscription_month_count: int | None = None
    unclaimed_prize_count: int | None = None
    only_new_members: bool | None = None
    prize_description: str | None = None
    prize_star_count: int | None = None


@dataclass(frozen=True)
class GiveawayMessage:
    pass  # Can be expanded if needed


# ─── Link Preview ─────────────────────────


@dataclass(frozen=True)
class LinkPreviewOptions:
    is_disabled: bool | None = None
    url: str | None = None
    prefer_small_media: bool | None = None
    prefer_large_media: bool | None = None
    show_above_text: bool | None = None


# ─── Input Media (for sendMediaGroup) ──────


@dataclass(frozen=True)
class InputMediaPhoto:
    media: str
    type: str = "photo"
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    show_caption_above_media: bool | None = None
    has_spoiler: bool | None = None


@dataclass(frozen=True)
class InputMediaVideo:
    media: str
    type: str = "video"
    thumbnail: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    show_caption_above_media: bool | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    supports_streaming: bool | None = None
    has_spoiler: bool | None = None
    cover: str | None = None
    start_timestamp: int | None = None


@dataclass(frozen=True)
class InputMediaAnimation:
    media: str
    type: str = "animation"
    thumbnail: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    show_caption_above_media: bool | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    has_spoiler: bool | None = None


@dataclass(frozen=True)
class InputMediaAudio:
    media: str
    type: str = "audio"
    thumbnail: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    duration: int | None = None
    performer: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class InputMediaDocument:
    media: str
    type: str = "document"
    thumbnail: str | None = None
    caption: str | None = None
    parse_mode: str | None = None
    caption_entities: list[MessageEntity] | None = None
    disable_content_type_detection: bool | None = None


InputMedia = (
    InputMediaPhoto
    | InputMediaVideo
    | InputMediaAnimation
    | InputMediaAudio
    | InputMediaDocument
)


# ─── Reactions ────────────────────────────


@dataclass(frozen=True)
class ReactionTypeEmoji:
    type: str = "emoji"
    emoji: str = ""


@dataclass(frozen=True)
class ReactionTypePaid:
    type: str = "paid"


ReactionType = ReactionTypeEmoji | ReactionTypePaid


@dataclass(frozen=True)
class MessageReactionUpdated:
    chat: Chat
    message_id: int
    date: int
    old_reaction: list[ReactionType]
    new_reaction: list[ReactionType]
    user: User | None = None
    actor_chat: Chat | None = None


@dataclass(frozen=True)
class MessageReactionCountUpdated:
    chat: Chat
    message_id: int
    date: int
    reactions: list[ReactionCount]


@dataclass(frozen=True)
class ReactionCount:
    type: ReactionType
    total_count: int


# ─── Callback Query ───────────────────────


@dataclass(frozen=True)
class CallbackQuery:
    id: str
    from_user: User
    message: Message | None = None
    inline_message_id: str | None = None
    chat_instance: str = ""
    data: str | None = None
    game_short_name: str | None = None

    async def answer(self, text: str | None = None, show_alert: bool | None = None,
                     url: str | None = None, cache_time: int | None = None) -> None:
        from telegram._bot import _BOT_INSTANCE
        bot = _BOT_INSTANCE.get()
        if bot:
            await bot.answer_callback_query(self.id, text=text, show_alert=show_alert,
                                            url=url, cache_time=cache_time)


# ─── File ─────────────────────────────────────


@dataclass(frozen=True)
class File:
    file_id: str
    file_unique_id: str
    file_size: int | None = None
    file_path: str | None = None

    async def download_to_drive(self, path: str) -> None:
        raise NotImplementedError("Set via _attach_download")


# ─── Webhook Info ──────────────────────────────


@dataclass(frozen=True)
class WebhookInfo:
    url: str
    has_custom_certificate: bool
    pending_update_count: int
    ip_address: str | None = None
    last_error_date: int | None = None
    last_error_message: str | None = None
    last_synchronization_error_date: int | None = None
    max_connections: int | None = None
    allowed_updates: list[str] | None = None


# ─── Business Connection (Bot API v10) ────────


@dataclass(frozen=True)
class BusinessIntro:
    title: str | None = None
    message: str | None = None
    sticker: Sticker | None = None


@dataclass(frozen=True)
class BusinessLocation:
    address: str
    location: Location | None = None


@dataclass(frozen=True)
class BusinessOpeningHoursInterval:
    opening_minute: int
    closing_minute: int


@dataclass(frozen=True)
class BusinessOpeningHours:
    time_zone_name: str
    opening_hours: list[BusinessOpeningHoursInterval]


@dataclass(frozen=True)
class BusinessConnection:
    id: str
    user: User
    user_chat_id: int
    date: int
    can_reply: bool
    is_enabled: bool
    business_intro: BusinessIntro | None = None
    business_location: BusinessLocation | None = None
    business_opening_hours: BusinessOpeningHours | None = None


# ─── Stars & Transactions ────────────────────


@dataclass(frozen=True)
class StarTransaction:
    id: str
    amount: int
    date: int
    source: Any | None = None
    receiver: Any | None = None


@dataclass(frozen=True)
class StarTransactions:
    transactions: list[StarTransaction]


# ─── Gifts (Bot API v10) ────────────────────


@dataclass(frozen=True)
class Gift:
    id: str
    title: str
    emoji: str
    price: int
    remaining_count: int | None = None
    total_count: int | None = None
    is_unlimited: bool | None = None
    is_sold_out: bool | None = None
    model: str | None = None
    model_animation: Animation | None = None
    model_scale: float | None = None
    model_pose: str | None = None
    model_tone: str | None = None
    is_custom_tone: bool | None = None
    backdrop: str | None = None
    backdrop_colors: list[str] | None = None
    symbol: str | None = None
    symbol_animation: Animation | None = None
    symbol_colors: list[str] | None = None
    can_upgrade_after_sending: bool | None = None
    has_effect: bool | None = None


@dataclass(frozen=True)
class Gifts:
    gifts: list[Gift]


# ─── Chat Boosts ────────────────────────────


@dataclass(frozen=True)
class ChatBoostAdded:
    boost_count: int


@dataclass(frozen=True)
class ChatBoost:
    boost_id: str
    add_date: int
    expiration_date: int
    source: Any  # ChatBoostSource


@dataclass(frozen=True)
class ChatBoostUpdated:
    chat: Chat
    boost: ChatBoost


@dataclass(frozen=True)
class ChatBoostRemoved:
    chat: Chat
    boost_id: str
    remove_date: int
    source: Any


# ─── Message ──────────────────────────────────


@dataclass(frozen=True)
class Message:
    message_id: int
    date: int
    chat: Chat
    from_user: User | None = None
    sender_chat: Chat | None = None
    sender_tag: str | None = None
    sender_boost_count: int | None = None
    is_topic_message: bool | None = None
    message_thread_id: int | None = None
    forum_topic_created: ForumTopicCreated | None = None
    forum_topic_closed: ForumTopicClosed | None = None
    forum_topic_reopened: ForumTopicReopened | None = None
    general_forum_topic_hidden: GeneralForumTopicHidden | None = None
    general_forum_topic_unhidden: GeneralForumTopicUnhidden | None = None
    write_access_allowed: WriteAccessAllowed | None = None
    text: str | None = None
    caption: str | None = None
    entities: list[MessageEntity] | None = None
    caption_entities: list[MessageEntity] | None = None
    photo: list[PhotoSize] | None = None
    voice: Voice | None = None
    audio: Audio | None = None
    document: Document | None = None
    video: Video | None = None
    video_note: VideoNote | None = None
    animation: Animation | None = None
    location: Location | None = None
    live_photo: LivePhoto | None = None
    venue: Venue | None = None
    contact: Contact | None = None
    dice: Dice | None = None
    game: Game | None = None
    poll: Poll | None = None
    sticker: Sticker | None = None
    invoice: Invoice | None = None
    successful_payment: SuccessfulPayment | None = None
    giveaway: Giveaway | None = None
    giveaway_winners: GiveawayWinners | None = None
    giveaway_created: GiveawayCreated | None = None
    poll_option_added: PollOptionAdded | None = None
    poll_option_deleted: PollOptionDeleted | None = None
    reply_to_message: Message | None = None
    reply_to_poll_option_id: int | None = None
    reply_markup: InlineKeyboardMarkup | None = None
    media_group_id: str | None = None
    link_preview_options: LinkPreviewOptions | None = None
    is_automatic_forward: bool | None = None
    has_protected_content: bool | None = None
    is_paid: bool | None = None
    paid_media_info: PaidMediaInfo | None = None
    business_connection_id: str | None = None
    sender_business_bot: User | None = None
    guest_bot_caller_user: User | None = None
    guest_bot_caller_chat: Chat | None = None
    guest_query_id: str | None = None
    is_topic_closed: bool | None = None
    message_auto_delete_timer_changed: MessageAutoDeleteTimerChanged | None = None
    boost_added: ChatBoostAdded | None = None
    connected_website: str | None = None
    passport_data: PassportData | None = None
    proximity_alert_triggered: ProximityAlertTriggered | None = None
    pinned_message: Message | None = None
    send_job_id: str | None = None
    sender_tag_v2: str | None = None

    @property
    def chat_id(self) -> int:
        return self.chat.id

    async def reply_text(self, text: str, **kwargs) -> Message:
        from telegram._bot import _BOT_INSTANCE
        bot = _BOT_INSTANCE.get()
        if bot:
            return await bot.send_message(chat_id=self.chat.id, text=text, **kwargs)
        raise RuntimeError("No active Bot instance for reply_text")

    async def edit_reply_markup(self, reply_markup: InlineKeyboardMarkup | None = None, **kwargs) -> Message:
        from telegram._bot import _BOT_INSTANCE
        bot = _BOT_INSTANCE.get()
        if bot:
            return await bot.edit_message_reply_markup(
                chat_id=self.chat.id, message_id=self.message_id,
                reply_markup=reply_markup, **kwargs,
            )
        raise RuntimeError("No active Bot instance for edit_reply_markup")


@dataclass(frozen=True)
class MessageAutoDeleteTimerChanged:
    message_auto_delete_time: int


@dataclass(frozen=True)
class ProximityAlertTriggered:
    traveler: User
    watcher: User
    distance: int


# ─── Update ───────────────────────────────────


@dataclass(frozen=True)
class Update:
    update_id: int
    message: Message | None = None
    edited_message: Message | None = None
    channel_post: Message | None = None
    edited_channel_post: Message | None = None
    business_connection: BusinessConnection | None = None
    business_message: Message | None = None
    edited_business_message: Message | None = None
    deleted_business_messages: BusinessMessagesDeleted | None = None
    guest_message: Message | None = None
    message_reaction: MessageReactionUpdated | None = None
    message_reaction_count: MessageReactionCountUpdated | None = None
    inline_query: InlineQuery | None = None
    chosen_inline_result: ChosenInlineResult | None = None
    callback_query: CallbackQuery | None = None
    shipping_query: ShippingQuery | None = None
    pre_checkout_query: PreCheckoutQuery | None = None
    purchased_paid_media: PurchasedPaidMedia | None = None
    poll: Poll | None = None
    poll_answer: PollAnswer | None = None
    my_chat_member: ChatMemberUpdated | None = None
    chat_member: ChatMemberUpdated | None = None
    chat_join_request: ChatJoinRequest | None = None
    chat_boost: ChatBoostUpdated | None = None
    removed_chat_boost: ChatBoostRemoved | None = None
    managed_bot: ManagedBotUpdate | None = None

    @property
    def effective_user(self) -> User | None:
        message = self.effective_message
        if message and message.from_user:
            return message.from_user
        if self.callback_query and self.callback_query.from_user:
            return self.callback_query.from_user
        if self.business_connection and self.business_connection.user:
            return self.business_connection.user
        return None

    @property
    def effective_chat(self) -> Chat | None:
        message = self.effective_message
        if message:
            return message.chat
        if self.callback_query and self.callback_query.message:
            return self.callback_query.message.chat
        if self.deleted_business_messages:
            return self.deleted_business_messages.chat
        return None

    @property
    def effective_message(self) -> Message | None:
        return (
            self.message
            or self.edited_message
            or self.business_message
            or self.edited_business_message
            or self.guest_message
            or self.channel_post
            or self.edited_channel_post
            or (self.callback_query.message if self.callback_query else None)
        )


@dataclass(frozen=True)
class BusinessMessagesDeleted:
    business_connection_id: str
    chat: Chat
    message_ids: list[int]


@dataclass(frozen=True)
class PurchasedPaidMedia:
    from_user: User
    paid_media: list[PaidMedia]


@dataclass(frozen=True)
class ManagedBotUpdate:
    bot_user: User
    access_settings: dict[str, Any] | None = None


# ─── Reply Parameters ─────────────────────


@dataclass(frozen=True)
class ReplyParameters:
    message_id: int
    chat_id: int | str | None = None
    allow_sending_without_reply: bool | None = None
    quote: str | None = None
    quote_parse_mode: str | None = None
    quote_entities: list[MessageEntity] | None = None
    quote_position: int | None = None
    poll_option_id: int | None = None


# ─── SendInvoice / LabeledPrice ────────────


@dataclass(frozen=True)
class LabeledPrice:
    label: str
    amount: int


@dataclass(frozen=True)
class ShippingOption:
    id: str
    title: str
    prices: list[LabeledPrice]
