from __future__ import annotations

import asyncio
import random

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Settings
from database import Database
from keyboards.main_menu import main_menu_kb, back_to_menu_kb
from utils.emoji import pe
from utils.fonts import mf

router = Router(name="start")

_STICKER_PACK = "Koylakoyla_by_fStikBot"

_LOADING_FRAMES = [
    "[ ▒▒▒▒▒▒▒▒▒▒ ] 0%",
    "[ ████▒▒▒▒▒▒ ] 40%",
    "[ ████████▒▒ ] 80%",
    "[ ██████████ ] 100%\n˹ 𝐕ᴏᴛᴇ 𝐁ᴏᴛ ˼",
]


async def _play_intro(message: Message) -> None:
    """Sticker → delete after 2s → loading bar animation → delete → main msg."""
    # ── Step 1: random sticker ────────────────────────────────────────────────
    sticker_msg = None
    try:
        pack = await message.bot.get_sticker_set(_STICKER_PACK)
        stk = random.choice(pack.stickers)
        sticker_msg = await message.answer_sticker(stk.file_id)
        await asyncio.sleep(2)
    except Exception:
        pass
    if sticker_msg:
        try:
            await sticker_msg.delete()
        except Exception:
            pass

    # ── Step 2: loading bar ───────────────────────────────────────────────────
    anim_msg = None
    try:
        anim_msg = await message.answer(f"<code>{_LOADING_FRAMES[0]}</code>")
        for frame in _LOADING_FRAMES[1:]:
            await asyncio.sleep(0.2)
            await anim_msg.edit_text(f"<code>{frame}</code>")
        await asyncio.sleep(0.5)
    except Exception:
        pass
    if anim_msg:
        try:
            await anim_msg.delete()
        except Exception:
            pass


def _intro_text(settings: Settings) -> str:
    return mf(
        f"{pe('fire', '🎉')} <b>Welcome to the Giveaway Manager Bot!</b>\n\n"
        f"{pe('trophy', '🏆')} <b>The Most Advanced Giveaway Bot on Telegram</b>\n\n"
        "<blockquote>"
        f"{pe('star', '✨')} <b>Features:</b>\n"
        "├ 🗳 Voting Contests &amp; 🎰 Lucky Draws\n"
        f"├ {pe('money', '💰')} Paid Votes (UPI / Telegram Stars)\n"
        "├ 🔗 Referral Bonus System\n"
        "├ 📊 Live Leaderboards\n"
        "├ 🛡 Anti-Cheat Protection\n"
        "└ 📢 Channel Post Creator"
        "</blockquote>\n\n"
        f"🔹 {settings.powered_by_text}\n"
        f"🆘 Support: {settings.support_link}"
    )


@router.message(CommandStart(deep_link=True))
async def start_deeplink(
    message: Message,
    command: CommandStart,
    db: Database,
    settings: Settings,
    state: FSMContext,
) -> None:
    await db.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name or "",
    )
    await state.clear()
    arg = command.args or ""

    if arg.startswith("giveaway_"):
        parts = arg.replace("giveaway_", "").split("_ref_")
        giveaway_id = int(parts[0])
        referrer_id = int(parts[1]) if len(parts) > 1 else None
        from handlers.giveaway import process_participation_link
        await process_participation_link(message, db, settings, giveaway_id, referrer_id)
        return

    # Deep link but not giveaway → run full intro
    await _play_intro(message)
    try:
        await message.answer_photo(
            settings.banner_url,
            caption=_intro_text(settings),
            reply_markup=main_menu_kb(),
        )
    except Exception:
        await message.answer(_intro_text(settings), reply_markup=main_menu_kb())


@router.message(CommandStart())
async def start_root(message: Message, db: Database, settings: Settings, state: FSMContext) -> None:
    await db.ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name or "",
    )
    await state.clear()

    await _play_intro(message)

    try:
        await message.answer_photo(
            settings.banner_url,
            caption=_intro_text(settings),
            reply_markup=main_menu_kb(),
        )
    except Exception:
        await message.answer(_intro_text(settings), reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:root")
async def menu_root(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    try:
        await callback.message.edit_caption(
            caption=_intro_text(settings),
            reply_markup=main_menu_kb(),
        )
    except Exception:
        try:
            await callback.message.edit_text(_intro_text(settings), reply_markup=main_menu_kb())
        except Exception:
            await callback.message.answer(_intro_text(settings), reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:how_to_use")
async def how_to_use(callback: CallbackQuery) -> None:
    await callback.answer()
    text = mf(
        "📖 <b>How To Use This Bot</b>\n\n"
        "<blockquote>"
        "<b>1️⃣ Create a Giveaway</b>\n"
        "   • Click <b>New Giveaway</b> and follow the steps\n"
        "   • Choose between <b>Voting Contest</b> or <b>Lucky Draw</b>\n"
        "   • Set Free or Paid mode"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>2️⃣ Share The Link</b>\n"
        "   • Share your giveaway participation link\n"
        "   • Participants join via the deep link"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>3️⃣ Voting</b>\n"
        "   • Channel subscribers can vote for participants\n"
        "   • Each subscriber can vote once per giveaway\n"
        "   • Votes are removed if the voter leaves the channel"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>4️⃣ Paid Votes</b>\n"
        "   • Participants can buy extra votes via UPI or Stars\n"
        "   • You (host) approve/deny payment screenshots"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>5️⃣ Referral System</b>\n"
        "   • Enable referrals so participants earn bonus votes\n"
        "   • Each friend they invite = bonus votes"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>6️⃣ End Giveaway</b>\n"
        "   • Click <b>End Giveaway</b> to announce the winner\n"
        "   • Winner is announced in the channel automatically"
        "</blockquote>"
    )
    await callback.message.answer(text, reply_markup=back_to_menu_kb())


@router.callback_query(F.data == "menu:donate")
async def donate(callback: CallbackQuery, settings: Settings) -> None:
    await callback.answer()
    try:
        await callback.message.answer_photo(
            settings.donate_qr,
            caption=mf(
                "💖 <b>Support This Bot</b>\n\n"
                "<blockquote>"
                "Your support helps keep this bot running and free!\n"
                "Scan the QR code above to donate. Thank you! 🙏"
                "</blockquote>"
            ),
            reply_markup=back_to_menu_kb(),
        )
    except Exception:
        await callback.message.answer(
            mf("💖 <b>Thank you for supporting this bot!</b>"),
            reply_markup=back_to_menu_kb(),
        )


@router.callback_query(F.data == "menu:support")
async def support(callback: CallbackQuery, settings: Settings) -> None:
    await callback.answer()
    await callback.message.answer(
        mf(
            f"🆘 <b>Support</b>\n\n"
            f"<blockquote>Need help? Contact us:\n{settings.support_link}</blockquote>"
        ),
        reply_markup=back_to_menu_kb(),
    )
