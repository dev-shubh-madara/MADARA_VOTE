from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Settings
from database import Database
from keyboards.main_menu import admin_panel_kb, back_to_menu_kb, broadcast_confirm_kb, participant_vote_kb
from states.admin import BroadcastState, AdminState
from utils.fonts import mf

router = Router(name="owner")


async def _is_owner(message: Message, db: Database) -> bool:
    if not await db.is_owner(message.from_user.id):
        await message.answer(mf("❌ <b>This command is for owners only.</b>"))
        return False
    return True


async def _is_owner_cb(callback: CallbackQuery, db: Database) -> bool:
    if not await db.is_owner(callback.from_user.id):
        await callback.answer("❌ Owners only!", show_alert=True)
        return False
    return True


# ── /admin command ─────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def admin_cmd(message: Message, db: Database) -> None:
    if not await _is_owner(message, db):
        return
    await message.answer(
        mf("👑 <b>Admin Panel</b>\n\n<blockquote>Welcome, Admin! Choose an action below.</blockquote>"),
        reply_markup=admin_panel_kb(),
    )


# ── Admin Panel callbacks ──────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, db: Database) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    total_users = await db.total_users()
    total_giveaways = await db.total_giveaways()
    active = await db.active_giveaways()
    text = mf(
        "📊 <b>Bot Statistics</b>\n\n"
        "<blockquote>"
        f"👥 <b>Total Users:</b> {total_users:,}\n"
        f"🎁 <b>Total Giveaways:</b> {total_giveaways:,}\n"
        f"✅ <b>Active Giveaways:</b> {active:,}\n"
        f"🏁 <b>Ended Giveaways:</b> {total_giveaways - active:,}"
        "</blockquote>"
    )
    await callback.message.answer(text, reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_prompt(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    await state.set_state(BroadcastState.message)
    await callback.message.answer(
        mf(
            "📢 <b>Send Broadcast</b>\n\n"
            "<blockquote>"
            "Send the message you want to broadcast to all bot users.\n"
            "Supports text, photos, and formatted messages.\n\n"
            "Type /cancel to abort."
            "</blockquote>"
        ),
        reply_markup=back_to_menu_kb(),
    )


@router.message(BroadcastState.message, F.text == "/cancel")
async def admin_broadcast_cancel_input(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(mf("❌ <b>Broadcast cancelled.</b>"), reply_markup=admin_panel_kb())


@router.message(BroadcastState.message, F.photo)
async def admin_broadcast_preview_photo(message: Message, state: FSMContext) -> None:
    text = message.caption or ""
    await state.update_data(broadcast_text=text, broadcast_photo=message.photo[-1].file_id)
    await state.set_state(BroadcastState.confirm)
    await message.answer_photo(
        message.photo[-1].file_id,
        caption=mf(f"📋 <b>Broadcast Preview:</b>\n\n<blockquote>{text or '(no caption)'}</blockquote>\n\nConfirm sending this to all users?"),
        reply_markup=broadcast_confirm_kb(),
    )


@router.message(BroadcastState.message)
async def admin_broadcast_preview(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    await state.update_data(broadcast_text=text, broadcast_photo=None)
    await state.set_state(BroadcastState.confirm)
    await message.answer(
        mf(f"📋 <b>Broadcast Preview:</b>\n\n<blockquote>{text}</blockquote>\n\nConfirm sending this to all users?"),
        reply_markup=broadcast_confirm_kb(),
    )


@router.callback_query(F.data == "admin:broadcast_confirm", BroadcastState.confirm)
async def admin_broadcast_send(callback: CallbackQuery, db: Database, state: FSMContext, settings: Settings) -> None:
    if not await _is_owner_cb(callback, db):
        return
    data = await state.get_data()
    await state.clear()
    await callback.answer("📤 Broadcasting...", show_alert=False)

    text = data.get("broadcast_text", "")
    photo = data.get("broadcast_photo")
    user_ids = await db.get_all_user_ids()
    sent = 0
    failed = 0

    status_msg = await callback.message.answer(
        mf(f"📢 <b>Broadcasting...</b>\n\n<blockquote>0 / {len(user_ids)} sent</blockquote>")
    )

    for i, uid in enumerate(user_ids):
        try:
            if photo:
                await callback.bot.send_photo(uid, photo, caption=text or None)
            else:
                await callback.bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        # Stay under Telegram's ~30 msgs/sec global rate limit so sends don't get
        # throttled and miscounted as failures.
        await asyncio.sleep(0.04)
        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(
                    mf(f"📢 <b>Broadcasting...</b>\n\n<blockquote>{i+1} / {len(user_ids)} sent</blockquote>")
                )
            except Exception:
                pass

    await db.save_broadcast(callback.from_user.id, text, len(user_ids), sent)
    await status_msg.edit_text(
        mf(
            "✅ <b>Broadcast Complete!</b>\n\n"
            "<blockquote>"
            f"📤 Sent: {sent}\n"
            f"❌ Failed: {failed}\n"
            f"👥 Total: {len(user_ids)}"
            "</blockquote>"
        )
    )


@router.callback_query(F.data == "admin:broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Cancelled")
    await callback.message.answer(mf("❌ <b>Broadcast cancelled.</b>"), reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:ban")
async def admin_ban_prompt(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    await state.set_state(AdminState.waiting)
    await state.update_data(action="ban")
    await callback.message.answer(
        mf(
            "🚫 <b>Ban User</b>\n\n"
            "<blockquote>"
            "Send the user ID to ban:\n<code>123456789</code>\n\n"
            "Or with reason:\n<code>123456789 spamming</code>"
            "</blockquote>"
        ),
        reply_markup=back_to_menu_kb(),
    )


@router.callback_query(F.data == "admin:unban")
async def admin_unban_prompt(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    await state.set_state(AdminState.waiting)
    await state.update_data(action="unban")
    await callback.message.answer(
        mf("✅ <b>Unban User</b>\n\n<blockquote>Send the user ID to unban:</blockquote>"),
        reply_markup=back_to_menu_kb(),
    )


@router.callback_query(F.data == "admin:addadmin")
async def admin_addadmin_prompt(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    await state.set_state(AdminState.waiting)
    await state.update_data(action="addadmin")
    await callback.message.answer(
        mf("👑 <b>Add Admin</b>\n\n<blockquote>Send the user ID to promote:</blockquote>"),
        reply_markup=back_to_menu_kb(),
    )


@router.callback_query(F.data == "admin:userinfo")
async def admin_userinfo_prompt(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _is_owner_cb(callback, db):
        return
    await callback.answer()
    await state.set_state(AdminState.waiting)
    await state.update_data(action="userinfo")
    await callback.message.answer(
        mf("👤 <b>User Info</b>\n\n<blockquote>Send the user ID to look up:</blockquote>"),
        reply_markup=back_to_menu_kb(),
    )


@router.message(AdminState.waiting)
async def admin_action_handler(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    action = data.get("action")
    await state.clear()

    args = (message.text or "").split(maxsplit=1)
    if not args:
        await message.answer(mf("❌ <b>Invalid input.</b>"), reply_markup=admin_panel_kb())
        return

    try:
        user_id = int(args[0])
    except ValueError:
        await message.answer(mf("❌ <b>Invalid user ID.</b>"), reply_markup=admin_panel_kb())
        return

    if action == "ban":
        reason = args[1] if len(args) > 1 else None
        await db.ban_user(user_id, message.from_user.id, reason)
        await message.answer(
            mf(
                f"🚫 <b>User {user_id} banned</b>"
                + (f"\n<blockquote>Reason: {reason}</blockquote>" if reason else "")
            ),
            reply_markup=admin_panel_kb(),
        )
    elif action == "unban":
        await db.unban_user(user_id)
        await message.answer(mf(f"✅ <b>User {user_id} unbanned</b>"), reply_markup=admin_panel_kb())
    elif action == "addadmin":
        await db.add_owner(user_id)
        await message.answer(mf(f"👑 <b>User {user_id} is now an admin</b>"), reply_markup=admin_panel_kb())
    elif action == "userinfo":
        is_banned = await db.is_banned(user_id)
        is_owner = await db.is_owner(user_id)
        counts = await db.host_giveaway_counts(user_id)
        await message.answer(
            mf(
                "👤 <b>User Info</b>\n\n"
                "<blockquote>"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"👑 Admin: {'Yes' if is_owner else 'No'}\n"
                f"🚫 Banned: {'Yes' if is_banned else 'No'}\n"
                f"🎁 Active Giveaways: {counts['active']}\n"
                f"🏁 Past Giveaways: {counts['past']}"
                "</blockquote>"
            ),
            reply_markup=admin_panel_kb(),
        )


# ── Direct Commands ────────────────────────────────────────────────────────────
@router.message(Command("ban"))
async def ban_cmd(message: Message, db: Database) -> None:
    if not await _is_owner(message, db):
        return
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 2:
        await message.answer(mf("Usage: /ban <code>user_id</code> [reason]"))
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer(mf("❌ <b>Invalid user ID.</b>"))
        return
    reason = args[2] if len(args) > 2 else None
    await db.ban_user(user_id, message.from_user.id, reason)
    await message.answer(mf(f"🚫 User <code>{user_id}</code> has been banned."))


@router.message(Command("unban"))
async def unban_cmd(message: Message, db: Database) -> None:
    if not await _is_owner(message, db):
        return
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer(mf("Usage: /unban <code>user_id</code>"))
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer(mf("❌ <b>Invalid user ID.</b>"))
        return
    await db.unban_user(user_id)
    await message.answer(mf(f"✅ User <code>{user_id}</code> has been unbanned."))


@router.message(Command("addvote"))
async def addvote_cmd(message: Message, db: Database) -> None:
    if not await _is_owner(message, db):
        return
    args = (message.text or "").split(maxsplit=2)
    if len(args) < 3:
        await message.answer(mf("Usage: /addvote <code>participant_id</code> <code>amount</code>"))
        return
    try:
        participant_id = int(args[1])
        amount = int(args[2])
    except ValueError:
        await message.answer(mf("❌ <b>Invalid participant ID or amount.</b>"))
        return

    participant = await db.get_participant_by_id(participant_id)
    if not participant:
        await message.answer(mf("❌ <b>No participant found with that ID.</b>"))
        return

    await db.add_manual_votes(participant_id, amount)

    # Keep the public vote count on the channel post in sync.
    if participant.get("post_message_id"):
        new_count = await db.participant_votes(participant_id)
        giveaway = await db.get_giveaway(participant["giveaway_id"])
        if giveaway:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=giveaway.channel_id,
                    message_id=participant["post_message_id"],
                    reply_markup=participant_vote_kb(participant["giveaway_id"], participant_id, new_count),
                )
            except Exception:
                pass

    await message.answer(mf(f"✅ Added <b>{amount}</b> votes to participant <code>{participant_id}</code>."))


@router.message(Command("stats"))
async def stats_cmd(message: Message, db: Database) -> None:
    if not await _is_owner(message, db):
        return
    total_users = await db.total_users()
    total_giveaways = await db.total_giveaways()
    active = await db.active_giveaways()
    await message.answer(
        mf(
            "📊 <b>Bot Stats</b>\n\n"
            "<blockquote>"
            f"👥 Users: {total_users:,}\n"
            f"🎁 Total Giveaways: {total_giveaways:,}\n"
            f"✅ Active: {active:,}\n"
            f"🏁 Ended: {total_giveaways - active:,}"
            "</blockquote>"
        )
    )
