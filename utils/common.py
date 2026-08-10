from __future__ import annotations

import html

from aiogram import Bot
from aiogram.enums import ChatMemberStatus


def esc(text: str | None) -> str:
    """Escape user-supplied text so it can't break or inject HTML parse-mode messages."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


def parse_channel_input(raw: str) -> tuple[str, int]:
    raw = raw.strip()
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
    elif " " in raw:
        parts = [p.strip() for p in raw.split(None, 1)]
    else:
        raise ValueError("Invalid format")
    if len(parts) != 2:
        raise ValueError("Invalid format")
    username, chat_id_s = parts
    if not username.startswith("@"):
        raise ValueError("Channel username must start with @")
    chat_id = int(chat_id_s)
    return username, chat_id


async def ensure_channel_membership(bot: Bot, channel_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }
    except Exception:
        return False


def display_name(username: str | None, full_name: str | None, user_id: int) -> str:
    if username:
        return f"@{esc(username)}"
    if full_name:
        return esc(full_name)
    return str(user_id)


def medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"{rank}.")
