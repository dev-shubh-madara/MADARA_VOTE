from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    bot_token: str
    bot_username: str
    mongodb_uri: str
    mongodb_db_name: str
    support_link: str
    powered_by_text: str
    banner_url: str
    donate_qr: str
    owner_ids: Tuple[int, ...]
    log_level: str
    premium_emojis: dict[str, str]


def _parse_owner_ids(raw: str) -> Tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return ()
    return tuple(int(p) for p in parts)


def _parse_premium_emojis(raw: str) -> dict:
    """Parses PREMIUM_EMOJIS="name:id,name2:id2,..." into a dict.
    Unset/blank -> empty dict, and every call site degrades to plain emoji."""
    result: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        name, _, emoji_id = pair.partition(":")
        name, emoji_id = name.strip(), emoji_id.strip()
        if name and emoji_id:
            result[name] = emoji_id
    return result


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    if not token:
        raise ValueError("BOT_TOKEN is required")

    mongodb_uri = os.getenv("MONGODB_URI", "").strip()
    if not mongodb_uri:
        raise ValueError("MONGODB_URI is required")

    return Settings(
        bot_token=token,
        bot_username=username,
        mongodb_uri=mongodb_uri,
        mongodb_db_name=os.getenv("MONGODB_DB_NAME", "madara_vote"),
        support_link=os.getenv("SUPPORT_LINK", "https://t.me/+Vo8tTaZsz9Q5Njk9"),
        powered_by_text=os.getenv("POWERED_BY_TEXT", "Powered by Madara"),
        banner_url=os.getenv("BANNER_URL", "https://files.catbox.moe/odeutr.png"),
        donate_qr=os.getenv("DONATE_QR", "https://files.catbox.moe/nx4jci.png"),
        owner_ids=_parse_owner_ids(os.getenv("OWNER_IDS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        premium_emojis=_parse_premium_emojis(os.getenv("PREMIUM_EMOJIS", "")),
    )
