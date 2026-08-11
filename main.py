from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import Settings, load_settings
from database import Database
from handlers import chats, giveaway, owner, post_creator, start
from middlewares.ban import BanMiddleware
from utils import emoji


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def build_dispatcher(settings: Settings) -> tuple[Dispatcher, Database]:
    emoji.configure(settings.premium_emojis)
    db = Database(settings.mongodb_uri, settings.mongodb_db_name)
    await db.init()
    for owner_id in settings.owner_ids:
        await db.ensure_user(owner_id, None, f"owner_{owner_id}", is_admin=True)
    await db.set_initial_owners(settings.owner_ids)

    dp = Dispatcher()
    dp.message.middleware(BanMiddleware(db))
    dp.callback_query.middleware(BanMiddleware(db))

    dp["db"] = db
    dp["settings"] = settings

    dp.include_router(start.router)
    dp.include_router(giveaway.router)
    dp.include_router(chats.router)
    dp.include_router(post_creator.router)
    dp.include_router(owner.router)
    return dp, db


async def main() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp, _ = await build_dispatcher(settings)
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_member",
            "my_chat_member",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
