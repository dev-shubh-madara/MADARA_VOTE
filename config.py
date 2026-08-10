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
    database_path: str
    support_link: str
    powered_by_text: str
    banner_url: str
    donate_qr: str
    owner_ids: Tuple[int, ...]
    log_level: str


def _parse_owner_ids(raw: str) -> Tuple[int, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return ()
    return tuple(int(p) for p in parts)


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    username = os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    if not token:
        raise ValueError("BOT_TOKEN is required")

    return Settings(
        bot_token=token,
        bot_username=username,
        database_path=os.getenv("DATABASE_PATH", "giveaway.db"),
        support_link=os.getenv("SUPPORT_LINK", "https://t.me/+Vo8tTaZsz9Q5Njk9"),
        powered_by_text=os.getenv("POWERED_BY_TEXT", "Powered by Madara"),
        banner_url=os.getenv("BANNER_URL", "https://files.catbox.moe/odeutr.png"),
        donate_qr=os.getenv("DONATE_QR", "https://files.catbox.moe/nx4jci.png"),
        owner_ids=_parse_owner_ids(os.getenv("OWNER_IDS", "8762430892")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
