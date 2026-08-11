from __future__ import annotations

"""Premium (custom) emoji support, added in Telegram Bot API 9.4 (Feb 2026).

Two independent features live here:

1. `pe(name, fallback)` - wraps a fallback emoji in a <tg-emoji> HTML tag so it
   renders as your custom/premium emoji inside message TEXT. Requires parse_mode
   HTML. Only works in messages the bot sends directly to private, group, and
   supergroup chats, and ONLY if the bot's owner account (the one that created it
   in @BotFather) has an active Telegram Premium subscription. It does NOT work
   in channel posts unless the bot has purchased a separate username on Fragment.
   If no ID is configured for `name`, this just returns the plain fallback emoji
   with no tag - always safe to call even before you've set any IDs.

2. `eid(name)` - returns the raw custom_emoji_id (or None) for use as the
   `icon_custom_emoji_id` parameter on InlineKeyboardButton/KeyboardButton, which
   shows a small custom emoji icon on the button itself. Same Premium-owner
   restriction as above applies. Button *color* (the `style` parameter, e.g.
   style="primary"/"success"/"danger") is a SEPARATE feature with no such
   restriction - it works everywhere, including channel posts.

How to get a custom_emoji_id: open a chat with your Premium account, send the
custom emoji you want to use, then forward that message to a bot like
@RawDataBot or @JsonDumpBot - it'll reply with the message JSON, which contains
a "custom_emoji" entity with the numeric ID you need.
"""

_REGISTRY: dict[str, str] = {}


def configure(emojis: dict[str, str]) -> None:
    """Called once at startup with the PREMIUM_EMOJIS mapping from Settings."""
    _REGISTRY.clear()
    _REGISTRY.update({k: v for k, v in emojis.items() if v})


def eid(name: str) -> str | None:
    """Raw custom_emoji_id for `name`, or None if not configured."""
    return _REGISTRY.get(name) or None


def pe(name: str, fallback: str) -> str:
    """Fallback emoji, wrapped in a <tg-emoji> tag if an ID is configured for `name`.
    Safe to call unconditionally - degrades to plain `fallback` text otherwise."""
    emoji_id = eid(name)
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
