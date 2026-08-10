from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from config import Settings
from database import Database
from keyboards.main_menu import (
    end_confirm_kb,
    giveaway_mode_kb,
    giveaway_type_kb,
    manage_giveaway_kb,
    my_giveaways_kb,
    participant_vote_kb,
    participation_kb,
    payment_mode_kb,
    payment_review_kb,
    referral_setup_kb,
    back_to_menu_kb,
)
from states.giveaway import NewGiveawayState
from states.payment import PaymentState
from utils.common import display_name, ensure_channel_membership, esc, medal, parse_channel_input
from utils.fonts import mf

router = Router(name="giveaway")


# ── Create Giveaway ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:new_giveaway")
async def new_giveaway(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NewGiveawayState.title)
    await callback.answer()
    await callback.message.answer(
        mf(
            "🎁 <b>Create New Giveaway</b>\n\n"
            "<blockquote>"
            "Step 1️⃣ — Enter a <b>title</b> for your giveaway.\n"
            "<i>(Keep it short and catchy!)</i>"
            "</blockquote>"
        )
    )


@router.message(NewGiveawayState.title)
async def new_giveaway_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 3:
        await message.answer(mf("❌ <b>Title too short.</b> Please enter at least 3 characters."))
        return
    await state.update_data(title=esc(title))
    await state.set_state(NewGiveawayState.channel)
    await message.answer(
        mf(
            "📡 <b>Step 2️⃣ — Link Your Channel</b>\n\n"
            "<blockquote>"
            "Send the channel username and ID in this format:\n"
            "<code>@yourchannel , -1001234567890</code>\n\n"
            "⚠️ Make sure the bot is an <b>admin</b> in the channel with post &amp; delete permissions."
            "</blockquote>"
        )
    )


@router.message(NewGiveawayState.channel)
async def new_giveaway_channel(message: Message, state: FSMContext) -> None:
    try:
        username, channel_id = parse_channel_input(message.text or "")
    except Exception:
        await message.answer(
            mf("❌ <b>Invalid format.</b>\n\n<blockquote>Use: <code>@yourchannel , -1001234567890</code></blockquote>")
        )
        return

    try:
        bot_member = await message.bot.get_chat_member(channel_id, message.bot.id)
    except Exception:
        await message.answer(mf("❌ <b>Could not access this channel.</b> Make sure the bot is added as admin."))
        return

    if bot_member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        await message.answer(mf("❌ <b>Bot is not an admin</b> in this channel. Please add it first."))
        return

    await state.update_data(channel_username=esc(username), channel_id=channel_id)
    await state.set_state(NewGiveawayState.giveaway_type)
    await message.answer(
        mf(
            "🎯 <b>Step 3️⃣ — Giveaway Type</b>\n\n"
            "<blockquote>"
            "🗳 <b>Voting Contest</b> — Participants collect votes. Most votes wins.\n"
            "🎰 <b>Lucky Draw</b> — Random winner picked from all participants."
            "</blockquote>"
        ),
        reply_markup=giveaway_type_kb(),
    )


@router.callback_query(NewGiveawayState.giveaway_type, F.data.startswith("newg:type:"))
async def new_giveaway_type(callback: CallbackQuery, state: FSMContext) -> None:
    gtype = callback.data.split(":")[-1]
    await state.update_data(giveaway_type=gtype)
    await callback.answer()
    await state.set_state(NewGiveawayState.mode)
    await callback.message.answer(
        mf(
            "💳 <b>Step 4️⃣ — Payment Mode</b>\n\n"
            "<blockquote>"
            "🆓 <b>Free</b> — No payment required\n"
            "💰 <b>Paid (UPI/QR)</b> — Participants pay for extra votes\n"
            "⭐ <b>Stars</b> — Pay with Telegram Stars for extra votes"
            "</blockquote>"
        ),
        reply_markup=giveaway_mode_kb(),
    )


@router.callback_query(NewGiveawayState.mode, F.data.startswith("newg:mode:"))
async def new_giveaway_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[-1]
    await state.update_data(mode=mode)
    await callback.answer()

    if mode == "paid":
        await state.set_state(NewGiveawayState.payment_info)
        await state.update_data(payment_sub="upi")
        await callback.message.answer(
            mf(
                "💰 <b>UPI Payment Setup</b>\n\n"
                "<blockquote>"
                "Send your <b>UPI ID</b> for receiving payments:\n"
                "<i>Example: yourname@upi</i>"
                "</blockquote>"
            )
        )
    elif mode == "stars":
        await state.set_state(NewGiveawayState.payment_info)
        await state.update_data(payment_sub="stars")
        await callback.message.answer(
            mf(
                "⭐ <b>Stars Payment Setup</b>\n\n"
                "<blockquote>"
                "Send the Telegram username where Stars should be sent:\n"
                "<i>Example: @yourusername</i>"
                "</blockquote>"
            )
        )
    else:
        await state.set_state(NewGiveawayState.referral_setup)
        await callback.message.answer(
            mf(
                "🔗 <b>Step 5️⃣ — Referral Bonus</b>\n\n"
                "<blockquote>"
                "Would you like to enable a referral system?\n"
                "When enabled, participants earn bonus votes for inviting friends!"
                "</blockquote>"
            ),
            reply_markup=referral_setup_kb(),
        )


@router.message(NewGiveawayState.payment_info)
async def new_giveaway_payment_info(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sub = data.get("payment_sub", "upi")
    value = (message.text or "").strip()

    if sub == "upi":
        await state.update_data(upi_id=esc(value), qr_file_id=None, stars_username=None)
    else:
        stars_username = value.lstrip("@")
        await state.update_data(stars_username=f"@{esc(stars_username)}", upi_id=None, qr_file_id=None)

    await state.set_state(NewGiveawayState.referral_setup)
    await message.answer(
        mf(
            "🔗 <b>Step 5️⃣ — Referral Bonus</b>\n\n"
            "<blockquote>"
            "Would you like to enable a referral system?\n"
            "Participants earn bonus votes for each friend they invite!"
            "</blockquote>"
        ),
        reply_markup=referral_setup_kb(),
    )


@router.callback_query(NewGiveawayState.referral_setup, F.data.startswith("newg:referral:"))
async def new_giveaway_referral(callback: CallbackQuery, state: FSMContext, db: Database, settings: Settings) -> None:
    referral = callback.data.split(":")[-1] == "yes"
    await callback.answer()
    data = await state.get_data()

    giveaway_id = await db.create_giveaway(
        host_id=callback.from_user.id,
        title=data["title"],
        channel_id=data["channel_id"],
        channel_username=data["channel_username"],
        giveaway_type=data.get("giveaway_type", "voting"),
        mode=data.get("mode", "free"),
        qr_file_id=data.get("qr_file_id"),
        stars_username=data.get("stars_username"),
        upi_id=data.get("upi_id"),
        referral_enabled=int(referral),
        votes_per_referral=1,
    )

    link = f"https://t.me/{settings.bot_username}?start=giveaway_{giveaway_id}"
    gtype = data.get("giveaway_type", "voting")
    mode = data.get("mode", "free")
    type_icon = "🗳" if gtype == "voting" else "🎰"
    mode_icon = {"free": "🆓", "paid": "💰", "stars": "⭐"}.get(mode, "🆓")

    await state.set_state(NewGiveawayState.optional_image)
    await state.update_data(giveaway_id=giveaway_id)

    await callback.message.answer(
        mf(
            "🎉 <b>Giveaway Created!</b>\n\n"
            "<blockquote>"
            f"📌 <b>Title:</b> {data['title']}\n"
            f"{type_icon} <b>Type:</b> {gtype.title()}\n"
            f"{mode_icon} <b>Mode:</b> {mode.title()}\n"
            f"🔗 <b>Referral:</b> {'Enabled ✅' if referral else 'Disabled ❌'}\n"
            f"📢 <b>Channel:</b> {data['channel_username']}"
            "</blockquote>\n\n"
            f"🔗 <b>Participation Link:</b>\n<code>{link}</code>"
        ),
        reply_markup=manage_giveaway_kb(
            giveaway_id,
            gtype,
            paid=mode in ("paid", "stars"),
            referral=referral,
        ),
    )
    await callback.message.answer(
        mf("📸 <b>Optional:</b> Send a banner/photo for this giveaway, or tap /skip")
    )


@router.message(NewGiveawayState.optional_image, F.photo)
async def optional_image(message: Message, state: FSMContext, db: Database) -> None:
    data = await state.get_data()
    giveaway = await db.get_giveaway(data["giveaway_id"])
    if giveaway:
        try:
            await message.bot.send_photo(
                giveaway.channel_id,
                message.photo[-1].file_id,
                caption=mf(f"🎁 <b>{giveaway.title}</b>\n\nJoin now and participate! 🔥"),
            )
        except Exception:
            pass
    await state.clear()
    await message.answer(mf("✅ <b>Banner posted to channel!</b> Your giveaway is live!"), reply_markup=back_to_menu_kb())


@router.message(NewGiveawayState.optional_image, F.text == "/skip")
async def skip_optional_image(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(mf("✅ <b>Giveaway is live!</b> Share the link with participants."), reply_markup=back_to_menu_kb())


# ── My Giveaways ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:my_giveaways")
async def my_giveaways(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    giveaways = await db.get_host_giveaways(callback.from_user.id, "active")
    counts = await db.host_giveaway_counts(callback.from_user.id)

    if not giveaways:
        await callback.message.answer(
            mf(
                "📋 <b>My Giveaways</b>\n\n"
                f"<blockquote>✅ Active: {counts['active']} | 🏁 Past: {counts['past']}</blockquote>\n\n"
                "You have no active giveaways. Create one!"
            ),
            reply_markup=back_to_menu_kb(),
        )
        return

    await callback.message.answer(
        mf(
            f"📋 <b>My Giveaways</b>\n\n"
            f"<blockquote>✅ Active: {counts['active']} | 🏁 Past: {counts['past']}</blockquote>\n\n"
            "Select a giveaway to manage:"
        ),
        reply_markup=my_giveaways_kb(giveaways),
    )


@router.callback_query(F.data.startswith("giveaway:manage:"))
async def manage_giveaway(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    await callback.answer()

    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("❌ Not found or not your giveaway.", show_alert=True)
        return

    participants = await db.count_participants(gid)
    link = f"https://t.me/{settings.bot_username}?start=giveaway_{gid}"
    type_icon = "🗳" if giveaway.giveaway_type == "voting" else "🎰"

    await callback.message.answer(
        mf(
            f"{type_icon} <b>{giveaway.title}</b>\n\n"
            "<blockquote>"
            f"📌 <b>Type:</b> {giveaway.giveaway_type.title()}\n"
            f"💳 <b>Mode:</b> {giveaway.mode.title()}\n"
            f"👥 <b>Participants:</b> {participants}\n"
            f"🔗 <b>Referral:</b> {'On ✅' if giveaway.referral_enabled else 'Off ❌'}\n"
            f"🗳 <b>Paid Votes:</b> {'On ✅' if giveaway.paid_votes_enabled else 'Off ❌'}\n"
            f"🔓 <b>Participation:</b> {'Open ✅' if giveaway.participation_enabled else 'Closed 🔒'}"
            "</blockquote>\n\n"
            f"🔗 <b>Link:</b> <code>{link}</code>"
        ),
        reply_markup=manage_giveaway_kb(
            gid,
            giveaway.giveaway_type,
            paid=giveaway.mode in ("paid", "stars"),
            referral=bool(giveaway.referral_enabled),
        ),
    )


# ── Giveaway Management Callbacks ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("giveaway:stats:"))
async def giveaway_stats(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("❌ Not your giveaway.", show_alert=True)
        return
    await callback.answer()
    participants = await db.count_participants(gid)
    board = await db.leaderboard(gid, limit=5)
    text = mf(
        "📊 <b>Giveaway Stats</b>\n\n"
        "<blockquote>"
        f"📌 <b>{giveaway.title}</b>\n"
        f"👥 Participants: {participants}"
        "</blockquote>"
    )
    if board:
        text += mf("\n\n🏆 <b>Top 5:</b>\n")
        for i, r in enumerate(board):
            name = display_name(r.get("username"), r.get("full_name"), r["user_id"])
            text += mf(f"{medal(i+1)} {name} — {r['vote_count']} votes\n")
    await callback.message.answer(text, reply_markup=back_to_menu_kb())


@router.callback_query(F.data.startswith("giveaway:leaderboard:"))
async def leaderboard(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway:
        await callback.answer("Giveaway not found.", show_alert=True)
        return
    await callback.answer()
    board = await db.leaderboard(gid, limit=20)
    if not board:
        await callback.message.answer(
            mf(f"🏆 <b>{giveaway.title}</b>\n\n<blockquote>No participants yet.</blockquote>"),
            reply_markup=back_to_menu_kb(),
        )
        return
    text = mf(f"🏆 <b>Leaderboard — {giveaway.title}</b>\n\n")
    for i, r in enumerate(board):
        name = display_name(r.get("username"), r.get("full_name"), r["user_id"])
        line = f"{medal(i+1)} {name} — <b>{r['vote_count']}</b> votes"
        if r.get("referral_count"):
            line += f" (+{r['referral_count']} ref)"
        text += mf(line) + "\n"
    await callback.message.answer(text, reply_markup=back_to_menu_kb())


@router.callback_query(F.data.startswith("giveaway:copy_link:"))
async def copy_link(callback: CallbackQuery, settings: Settings, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    await callback.answer()
    participant = await db.get_participant(gid, callback.from_user.id)

    if participant:
        ref_link = f"https://t.me/{settings.bot_username}?start=giveaway_{gid}_ref_{callback.from_user.id}"
        await callback.message.answer(
            mf(
                "🔗 <b>Your Referral Link</b>\n\n"
                "<blockquote>"
                "Share this link to earn bonus votes!\n\n"
                f"<code>{ref_link}</code>\n\n"
                f"📊 Your referrals: <b>{participant.get('referral_count', 0)}</b>"
                "</blockquote>"
            ),
            reply_markup=back_to_menu_kb(),
        )
    else:
        link = f"https://t.me/{settings.bot_username}?start=giveaway_{gid}"
        await callback.message.answer(
            mf(f"🔗 <b>Giveaway Link</b>\n\n<blockquote><code>{link}</code></blockquote>"),
            reply_markup=back_to_menu_kb(),
        )


@router.callback_query(F.data.startswith("giveaway:stop_paid:"))
async def stop_paid(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return
    new_val = 0 if giveaway.paid_votes_enabled else 1
    await db.update_giveaway_flags(gid, paid_votes_enabled=new_val)
    status = "disabled ❌" if new_val == 0 else "enabled ✅"
    await callback.answer(f"Paid votes {status}", show_alert=True)


@router.callback_query(F.data.startswith("giveaway:stop_part:"))
async def stop_part(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return
    new_val = 0 if giveaway.participation_enabled else 1
    await db.update_giveaway_flags(gid, participation_enabled=new_val)
    status = "closed 🔒" if new_val == 0 else "open 🔓"
    await callback.answer(f"Participation {status}", show_alert=True)


@router.callback_query(F.data.startswith("giveaway:toggle_ref:"))
async def toggle_ref(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return
    new_val = 0 if giveaway.referral_enabled else 1
    await db.update_giveaway_flags(gid, referral_enabled=new_val)
    status = "enabled ✅" if new_val else "disabled ❌"
    await callback.answer(f"Referral {status}", show_alert=True)


@router.callback_query(F.data.startswith("giveaway:end:"))
async def end_giveaway_prompt(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        mf(
            "⚠️ <b>End Giveaway?</b>\n\n"
            "<blockquote>"
            f"Are you sure you want to end <b>{giveaway.title}</b>?\n"
            "A winner will be announced in the channel."
            "</blockquote>"
        ),
        reply_markup=end_confirm_kb(gid),
    )


@router.callback_query(F.data.startswith("giveaway:end_confirm:"))
async def end_giveaway(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return

    await db.update_giveaway_flags(gid, status="ended")
    await callback.answer()

    if giveaway.giveaway_type == "lucky":
        winner = await db.random_winner(gid)
        win_type = "🎰 Lucky Draw"
    else:
        winner = await db.top_participant(gid)
        win_type = "🗳 Voting Contest"

    if winner:
        name = display_name(winner.get("username"), winner.get("full_name"), winner["user_id"])
        votes_text = f"\n🗳 Votes: {winner.get('vote_count', 0)}" if giveaway.giveaway_type == "voting" else ""
        announce = mf(
            "🏆 <b>GIVEAWAY ENDED!</b>\n\n"
            "<blockquote>"
            f"🎁 <b>{giveaway.title}</b>\n"
            f"{win_type}\n\n"
            f"🥇 <b>WINNER:</b> {name}{votes_text}"
            "</blockquote>\n\n"
            "🎊 Congratulations to the winner!"
        )
        try:
            await callback.bot.send_message(giveaway.channel_id, announce)
        except Exception:
            pass
        await callback.message.answer(
            mf(f"🏁 <b>Giveaway ended!</b>\n\n<blockquote>🥇 Winner: {name}</blockquote>"),
            reply_markup=back_to_menu_kb(),
        )
    else:
        await callback.message.answer(
            mf("🏁 <b>Giveaway ended</b> with no participants."),
            reply_markup=back_to_menu_kb(),
        )


@router.callback_query(F.data.startswith("giveaway:clear_posts:"))
async def clear_posts(callback: CallbackQuery, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return
    ids = await db.clear_channel_posts(gid)
    cleared = 0
    for mid in ids:
        try:
            await callback.bot.delete_message(giveaway.channel_id, mid)
            cleared += 1
        except TelegramBadRequest:
            pass
    await callback.answer(f"Cleared {cleared} posts ✅", show_alert=True)


# ── Participation ──────────────────────────────────────────────────────────────

async def process_participation_link(
    message: Message,
    db: Database,
    settings: Settings,
    giveaway_id: int,
    referrer_id: int | None = None,
) -> None:
    giveaway = await db.get_giveaway(giveaway_id)
    if not giveaway or giveaway.status != "active":
        await message.answer(mf("❌ <b>This giveaway is no longer active.</b>"))
        return
    if not giveaway.participation_enabled:
        await message.answer(mf("🔒 <b>Participation for this giveaway is currently closed.</b>"))
        return

    is_member = await ensure_channel_membership(message.bot, giveaway.channel_id, message.from_user.id)
    if not is_member:
        await message.answer(
            mf(
                "⚠️ <b>Subscribe Required!</b>\n\n"
                "<blockquote>"
                f"You must join <b>{giveaway.channel_username}</b> first, then click the link again."
                "</blockquote>"
            )
        )
        return

    participant_id = await db.add_participant(
        giveaway_id,
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
        referred_by=referrer_id,
    )

    already_joined = participant_id is None
    if already_joined:
        participant = await db.get_participant(giveaway_id, message.from_user.id)
        participant_id = participant["id"] if participant else None
    else:
        name = display_name(message.from_user.username, message.from_user.full_name, message.from_user.id)
        try:
            ch_msg = await message.bot.send_message(
                giveaway.channel_id,
                mf(
                    "🔥 <b>NEW PARTICIPANT!</b>\n\n"
                    "<blockquote>"
                    f"🎁 <b>Giveaway:</b> {giveaway.title}\n"
                    f"👤 <b>Name:</b> {name}\n"
                    f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>"
                    "</blockquote>\n\n"
                    "🗳 Tap below to vote for this participant!"
                ),
                reply_markup=participant_vote_kb(giveaway_id, participant_id, 0),
            )
            await db.set_participant_post_message(participant_id, ch_msg.message_id)
        except Exception:
            pass

        if referrer_id and giveaway.referral_enabled and referrer_id != message.from_user.id:
            ref_participant = await db.get_participant(giveaway_id, referrer_id)
            if ref_participant:
                votes = giveaway.votes_per_referral
                await db.credit_referral(giveaway_id, referrer_id, votes)
                try:
                    await message.bot.send_message(
                        referrer_id,
                        mf(
                            "🎉 <b>Referral Bonus!</b>\n\n"
                            "<blockquote>"
                            f"Someone joined <b>{giveaway.title}</b> via your link!\n"
                            f"You earned <b>+{votes} bonus vote(s)</b>! 🔥"
                            "</blockquote>"
                        ),
                    )
                    if ref_participant.get("post_message_id"):
                        new_count = await db.participant_votes(ref_participant["id"])
                        try:
                            await message.bot.edit_message_reply_markup(
                                chat_id=giveaway.channel_id,
                                message_id=ref_participant["post_message_id"],
                                reply_markup=participant_vote_kb(giveaway_id, ref_participant["id"], new_count),
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

    my_link = f"https://t.me/{settings.bot_username}?start=giveaway_{giveaway_id}_ref_{message.from_user.id}"
    if already_joined:
        await message.answer(
            mf(
                "✅ <b>You're already in this giveaway!</b>\n\n"
                "<blockquote>"
                f"🔗 <b>Your referral link:</b>\n<code>{my_link}</code>"
                "</blockquote>"
            ),
            reply_markup=participation_kb(giveaway_id, bool(giveaway.paid_votes_enabled), bool(giveaway.referral_enabled)),
        )
    else:
        await message.answer(
            mf(
                "🎉 <b>You've joined the giveaway!</b>\n\n"
                "<blockquote>"
                f"🎁 <b>{giveaway.title}</b>\n\n"
                f"🔗 <b>Your referral link (share to earn votes):</b>\n<code>{my_link}</code>"
                "</blockquote>"
            ),
            reply_markup=participation_kb(giveaway_id, bool(giveaway.paid_votes_enabled), bool(giveaway.referral_enabled)),
        )


# ── Voting ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vote:"))
async def vote_participant(callback: CallbackQuery, db: Database) -> None:
    parts = callback.data.split(":")
    giveaway_id, participant_id = int(parts[1]), int(parts[2])
    giveaway = await db.get_giveaway(giveaway_id)

    if not giveaway or giveaway.status != "active":
        await callback.answer("❌ This giveaway is no longer active.", show_alert=True)
        return

    is_member = await ensure_channel_membership(callback.bot, giveaway.channel_id, callback.from_user.id)
    if not is_member:
        await callback.answer(
            f"❌ You must be a subscriber of {giveaway.channel_username} to vote!",
            show_alert=True,
        )
        return

    participant = await db.get_participant_by_id(participant_id)
    if participant and participant["user_id"] == callback.from_user.id:
        await callback.answer("❌ You cannot vote for yourself!", show_alert=True)
        return

    ok = await db.add_vote(giveaway_id, participant_id, callback.from_user.id)
    if not ok:
        await callback.answer("⚠️ You already voted in this giveaway!", show_alert=True)
        return

    count = await db.participant_votes(participant_id)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=participant_vote_kb(giveaway_id, participant_id, count)
        )
    except TelegramBadRequest:
        pass
    await callback.answer("✅ Vote counted! Thank you!")


# ── Anti-cheat: member leave ───────────────────────────────────────────────────

@router.chat_member()
async def channel_member_update(event: ChatMemberUpdated, db: Database) -> None:
    if event.chat.type != "channel":
        return
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    left = {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
    was_member = old_status in {ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    now_left = new_status in left

    if was_member and now_left:
        user_id = event.new_chat_member.user.id
        rows = await db.remove_votes_by_voter_for_channel(event.chat.id, user_id)
        for row in rows:
            count = await db.participant_votes(row["participant_id"])
            if row.get("post_message_id"):
                try:
                    await event.bot.edit_message_reply_markup(
                        chat_id=event.chat.id,
                        message_id=row["post_message_id"],
                        reply_markup=participant_vote_kb(row["giveaway_id"], row["participant_id"], count),
                    )
                except TelegramBadRequest:
                    pass


# ── Payment ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("payment:start:"))
async def payment_start(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    gid = int(callback.data.split(":")[-1])
    giveaway = await db.get_giveaway(gid)
    if not giveaway or not giveaway.paid_votes_enabled:
        await callback.answer("❌ Paid votes are disabled for this giveaway.", show_alert=True)
        return
    participant = await db.get_participant(gid, callback.from_user.id)
    if not participant:
        await callback.answer("❌ You must join the giveaway first!", show_alert=True)
        return

    await state.set_state(PaymentState.choose_mode)
    await state.update_data(giveaway_id=gid, participant_id=participant["id"])
    await callback.answer()
    await callback.message.answer(
        mf("💳 <b>Buy Extra Votes</b>\n\n<blockquote>Choose your payment method:</blockquote>"),
        reply_markup=payment_mode_kb(gid),
    )


@router.callback_query(F.data.startswith("payment:mode:"))
async def payment_mode(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    parts = callback.data.split(":")
    mode, gid_s = parts[2], parts[3]
    giveaway = await db.get_giveaway(int(gid_s))
    if not giveaway:
        await callback.answer("Giveaway not found.", show_alert=True)
        return

    await state.update_data(payment_mode=mode)
    await state.set_state(PaymentState.screenshot)
    await callback.answer()

    if mode == "money":
        upi = giveaway.upi_id or "Contact host for UPI details"
        if giveaway.qr_file_id:
            try:
                await callback.message.answer_photo(
                    giveaway.qr_file_id,
                    caption=mf(
                        "💰 <b>Pay via UPI</b>\n\n"
                        "<blockquote>"
                        f"UPI ID: <code>{upi}</code>\n\n"
                        "After payment, send your screenshot here."
                        "</blockquote>"
                    ),
                )
                await callback.message.answer(mf("📸 <b>Upload your payment screenshot now:</b>"))
                return
            except Exception:
                pass
        await callback.message.answer(
            mf(
                "💰 <b>Pay via UPI</b>\n\n"
                "<blockquote>"
                f"UPI ID: <code>{upi}</code>\n\n"
                "After payment, send your payment screenshot here."
                "</blockquote>"
            )
        )
    else:
        stars_user = giveaway.stars_username or "Contact host"
        await callback.message.answer(
            mf(
                "⭐ <b>Pay via Telegram Stars</b>\n\n"
                "<blockquote>"
                f"Send Stars to: <b>{stars_user}</b>\n\n"
                "After payment, send your screenshot here."
                "</blockquote>"
            )
        )


@router.message(PaymentState.screenshot, F.photo)
async def payment_screenshot(message: Message, state: FSMContext) -> None:
    await state.update_data(screenshot_file_id=message.photo[-1].file_id)
    await state.set_state(PaymentState.ref)
    await message.answer(
        mf(
            "🔢 <b>Transaction Reference</b>\n\n"
            "<blockquote>"
            "Send your <b>UTR number</b> (for UPI) or <b>Stars transaction ID</b>:"
            "</blockquote>"
        )
    )


@router.message(PaymentState.ref)
async def payment_ref(message: Message, state: FSMContext) -> None:
    await state.update_data(ref=esc((message.text or "").strip()))
    await state.set_state(PaymentState.amount)
    await message.answer(
        mf("💰 <b>Amount</b>\n\n<blockquote>How much did you pay? (Enter the amount as a number)</blockquote>")
    )


@router.message(PaymentState.amount)
async def payment_amount(message: Message, state: FSMContext, db: Database) -> None:
    try:
        amount = int((message.text or "").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(mf("❌ <b>Please enter a valid positive number.</b>"))
        return

    data = await state.get_data()
    payment_id = await db.save_payment(
        giveaway_id=data["giveaway_id"],
        participant_id=data["participant_id"],
        payer_id=message.from_user.id,
        mode=data.get("payment_mode", "money"),
        screenshot_file_id=data["screenshot_file_id"],
        ref=data["ref"],
        amount=amount,
    )

    giveaway = await db.get_giveaway(data["giveaway_id"])
    mode_label = "⭐ Stars" if data.get("payment_mode") == "stars" else "💵 UPI"
    owner_caption = mf(
        "💳 <b>Payment Review Required</b>\n\n"
        "<blockquote>"
        f"🆔 Payment ID: <code>{payment_id}</code>\n"
        f"💳 Mode: {mode_label}\n"
        f"👤 From: <code>{message.from_user.id}</code> (@{message.from_user.username or 'N/A'})\n"
        f"🎁 Giveaway: {giveaway.title if giveaway else data['giveaway_id']}\n"
        f"🔢 Ref: <code>{data['ref']}</code>\n"
        f"💰 Amount: {amount}"
        "</blockquote>"
    )

    try:
        await message.bot.send_photo(
            giveaway.host_id,
            data["screenshot_file_id"],
            caption=owner_caption,
            reply_markup=payment_review_kb(payment_id),
        )
    except Exception:
        pass

    await message.answer(
        mf(
            "✅ <b>Payment Submitted!</b>\n\n"
            "<blockquote>"
            "Your payment has been sent to the giveaway host for review.\n"
            "You'll receive votes once it's approved."
            "</blockquote>"
        ),
        reply_markup=back_to_menu_kb(),
    )
    await state.clear()


@router.callback_query(F.data.startswith("payment:approve:"))
async def payment_approve(callback: CallbackQuery, db: Database) -> None:
    pid = int(callback.data.split(":")[-1])
    payment = await db.get_payment(pid)
    if not payment:
        await callback.answer("Payment not found.", show_alert=True)
        return

    giveaway = await db.get_giveaway(payment["giveaway_id"])
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return

    changed = await db.update_payment_status(pid, "approved", callback.from_user.id)
    if not changed:
        await callback.answer("⚠️ This payment was already reviewed.", show_alert=True)
        return

    votes = max(1, payment["amount"])
    await db.add_manual_votes(payment["participant_id"], votes)

    participant = await db.get_participant_by_id(payment["participant_id"])
    if participant and participant.get("post_message_id"):
        new_count = await db.participant_votes(payment["participant_id"])
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=giveaway.channel_id,
                message_id=participant["post_message_id"],
                reply_markup=participant_vote_kb(payment["giveaway_id"], payment["participant_id"], new_count),
            )
        except Exception:
            pass

    try:
        await callback.bot.send_message(
            payment["payer_id"],
            mf(
                "✅ <b>Payment Approved!</b>\n\n"
                "<blockquote>"
                f"Your payment of {payment['amount']} has been approved.\n"
                f"<b>+{votes} votes</b> have been added to your score! 🎉"
                "</blockquote>"
            ),
        )
    except Exception:
        pass

    await callback.answer(f"✅ Approved! +{votes} votes added.", show_alert=True)
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + mf("\n\n✅ <b>APPROVED</b>"),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("payment:deny:"))
async def payment_deny(callback: CallbackQuery, db: Database) -> None:
    pid = int(callback.data.split(":")[-1])
    payment = await db.get_payment(pid)
    if not payment:
        await callback.answer("Payment not found.", show_alert=True)
        return
    giveaway = await db.get_giveaway(payment["giveaway_id"])
    if not giveaway or giveaway.host_id != callback.from_user.id:
        await callback.answer("Host only!", show_alert=True)
        return

    changed = await db.update_payment_status(pid, "denied", callback.from_user.id)
    if not changed:
        await callback.answer("⚠️ This payment was already reviewed.", show_alert=True)
        return

    try:
        await callback.bot.send_message(
            payment["payer_id"],
            mf(
                "❌ <b>Payment Denied</b>\n\n"
                "<blockquote>"
                "Your payment was not approved by the host.\n"
                "Please contact support if you believe this is an error."
                "</blockquote>"
            ),
        )
    except Exception:
        pass

    await callback.answer("❌ Denied.", show_alert=True)
    try:
        await callback.message.edit_caption(
            caption=callback.message.caption + mf("\n\n❌ <b>DENIED</b>"),
        )
    except Exception:
        pass
