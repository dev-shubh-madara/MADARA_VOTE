from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards.main_menu import back_to_menu_kb
from utils.common import esc

router = Router(name="chats")


@router.callback_query(F.data == "menu:add_channel")
async def add_channel_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "📡 <b>Add Your Channel / Group</b>\n\n"
        "Forward any message from your channel or group where:\n"
        "• <b>You</b> are an admin\n"
        "• <b>This bot</b> is also an admin\n\n"
        "I will automatically detect and save it.",
        reply_markup=back_to_menu_kb(),
    )


@router.message(F.forward_from_chat)
async def save_forwarded_chat(message: Message, db: Database) -> None:
    chat = message.forward_from_chat
    if chat.type not in {"channel", "supergroup", "group"}:
        return

    try:
        member = await message.bot.get_chat_member(chat.id, message.from_user.id)
        if member.status not in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}:
            await message.answer(
                "❌ <b>You must be an admin</b> of that channel/group to add it.",
                reply_markup=back_to_menu_kb(),
            )
            return

        bot_member = await message.bot.get_chat_member(chat.id, message.bot.id)
        if bot_member.status not in {ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR}:
            await message.answer(
                "❌ <b>The bot must be an admin</b> of that channel/group.\n"
                "Please add the bot as admin first, then try again.",
                reply_markup=back_to_menu_kb(),
            )
            return
    except Exception as e:
        await message.answer(f"❌ Could not verify membership: {e}", reply_markup=back_to_menu_kb())
        return

    await db.save_user_chat(
        message.from_user.id,
        chat.id,
        chat.title or str(chat.id),
        chat.username,
        chat.type,
    )

    icon = "📢" if chat.type == "channel" else "👥"
    await message.answer(
        f"✅ <b>{icon} {chat.type.title()} Added!</b>\n\n"
        f"📌 <b>Name:</b> {esc(chat.title)}\n"
        f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
        f"🔗 <b>Username:</b> {'@' + esc(chat.username) if chat.username else 'Private'}",
        reply_markup=back_to_menu_kb(),
    )
