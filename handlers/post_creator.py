from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import Database
from keyboards.main_menu import back_to_menu_kb
from states.post_creator import PostCreatorState
from utils.fonts import mf, btn

router = Router(name="post_creator")


def _parse_buttons(raw: str) -> InlineKeyboardMarkup | None:
    rows = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if len(parts) == 2 and parts[1].startswith("http"):
            rows.append([InlineKeyboardButton(text=parts[0], url=parts[1])])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "menu:create_post")
async def create_post_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PostCreatorState.photo)
    await callback.answer()
    await callback.message.answer(
        mf(
            "📝 <b>Post Creator</b>\n\n"
            "<blockquote>"
            "Step f{pe('one', '✨')} — Send a <b>photo</b> for your post.\n"
            "Or tap /skip for a text-only post."
            "</blockquote>"
        ),
    )


@router.message(PostCreatorState.photo, F.photo)
async def post_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(PostCreatorState.caption)
    await message.answer(
        mf(
            "✍️ <b>Step 2️⃣ — Caption</b>\n\n"
            "<blockquote>"
            "Send the caption/text for your post.\n"
            "You can use <b>HTML formatting</b>."
            "</blockquote>"
        )
    )


@router.message(PostCreatorState.photo, F.text == "/skip")
async def post_photo_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await state.set_state(PostCreatorState.caption)
    await message.answer(
        mf("✍️ <b>Step 2️⃣ — Text</b>\n\n<blockquote>Send the text/message for your post.</blockquote>")
    )


@router.message(PostCreatorState.caption)
async def post_caption(message: Message, state: FSMContext) -> None:
    await state.update_data(caption=message.text or message.caption or "")
    await state.set_state(PostCreatorState.buttons)
    await message.answer(
        mf(
            "🔘 <b>Step 3️⃣ — Inline Buttons</b>\n\n"
            "<blockquote>"
            "Add inline URL buttons in this format (one per line):\n"
            "<code>Button Text | https://yourlink.com</code>\n\n"
            "Type /skip for no buttons."
            "</blockquote>"
        ),
    )


@router.message(PostCreatorState.buttons, F.text == "/skip")
async def post_buttons_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(buttons_raw=None)
    await state.set_state(PostCreatorState.confirm)
    await _show_preview(message, state)


@router.message(PostCreatorState.buttons)
async def post_buttons(message: Message, state: FSMContext) -> None:
    await state.update_data(buttons_raw=message.text)
    await state.set_state(PostCreatorState.confirm)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    caption = data.get("caption", "")
    photo = data.get("photo_file_id")
    buttons_raw = data.get("buttons_raw")
    kb = _parse_buttons(buttons_raw) if buttons_raw else None

    await message.answer(mf("👁 <b>Preview:</b>"))
    try:
        if photo:
            await message.answer_photo(photo, caption=caption, reply_markup=kb)
        else:
            await message.answer(caption, reply_markup=kb)
    except Exception as e:
        await message.answer(mf(f"⚠️ <b>Preview error:</b> <code>{e}</code>"))

    await message.answer(
        mf(
            "📡 <b>Send to Channel</b>\n\n"
            "<blockquote>"
            "Send the <b>channel username</b> or <b>chat ID</b> to post this to:\n"
            "<code>@yourchannel</code> or <code>-1001234567890</code>\n\n"
            "Or /cancel to discard."
            "</blockquote>"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn("❌ Cancel"), callback_data="post:cancel")],
        ]),
    )


@router.message(PostCreatorState.confirm)
async def post_send(message: Message, state: FSMContext, db: Database) -> None:
    target = (message.text or "").strip()
    if target == "/cancel":
        await state.clear()
        await message.answer(mf("❌ <b>Post cancelled.</b>"), reply_markup=back_to_menu_kb())
        return

    data = await state.get_data()
    caption = data.get("caption", "")
    photo = data.get("photo_file_id")
    buttons_raw = data.get("buttons_raw")
    kb = _parse_buttons(buttons_raw) if buttons_raw else None

    chat_id: int | str
    if target.lstrip("-").isdigit():
        chat_id = int(target)
    else:
        chat_id = target if target.startswith("@") else f"@{target}"

    # Only allow posting to chats this user has actually added (proven admin via forward check).
    owned_chats = await db.list_user_chats(message.from_user.id)
    target_username = str(chat_id).lstrip("@").lower() if isinstance(chat_id, str) else None
    is_owned = any(
        (isinstance(chat_id, int) and c["chat_id"] == chat_id)
        or (target_username and (c.get("chat_username") or "").lower() == target_username)
        for c in owned_chats
    )
    if not is_owned:
        await message.answer(
            mf(
                "❌ <b>You can only post to channels/groups you've added</b> via "
                "<b>➕ Add Channel</b> (forward a message from it first).\n\n"
                "This prevents posting to chats you don't actually control."
            ),
            reply_markup=back_to_menu_kb(),
        )
        return

    try:
        if photo:
            await message.bot.send_photo(chat_id, photo, caption=caption, reply_markup=kb)
        else:
            await message.bot.send_message(chat_id, caption, reply_markup=kb)
        await state.clear()
        await message.answer(mf("✅ <b>Post sent successfully!</b>"), reply_markup=back_to_menu_kb())
    except Exception as e:
        await message.answer(
            mf(f"❌ <b>Failed to send post:</b>\n<code>{e}</code>\n\nMake sure the bot is admin in that channel."),
        )


@router.callback_query(F.data == "post:cancel")
async def post_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(mf("❌ <b>Post cancelled.</b>"), reply_markup=back_to_menu_kb())
