
from __future__ import annotations

import asyncio
import random
import re

from aiogram import F, Router
from aiogram.enums import ParseMode
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


def _fix_custom_emojis(text: str) -> str:
    """
    Telegram HTML does NOT support <emoji>.
    
    Convert:
        <emoji id="123">🎉</emoji>
    
    into:
        <tg-emoji emoji-id="123">🎉</tg-emoji>
    
    Also supports:
        <emoji emoji-id="123">🎉</emoji>
    """

    if not text:
        return text

    # <emoji id="123">...</emoji>
    text = re.sub(
        r'<emoji\s+id=["\'](\d+)["\']\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <emoji emoji-id="123">...</emoji>
    text = re.sub(
        r'<emoji\s+emoji-id=["\'](\d+)["\']\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # <emoji id=123>...</emoji>
    text = re.sub(
        r'<emoji\s+id=(\d+)\s*>(.*?)</emoji>',
        r'<tg-emoji emoji-id="\1">\2</tg-emoji>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # If an unsupported plain <emoji> remains, remove the tags
    # but preserve the emoji/text inside.
    text = re.sub(
        r'<emoji[^>]*>',
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r'</emoji>',
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text


def _safe_text(text: str) -> str:
    """
    Run your existing font/custom-emoji formatter,
    then make the result Telegram HTML compatible.
    """
    try:
        formatted = mf(text)
    except Exception:
        formatted = text

    return _fix_custom_emojis(formatted)


async def _play_intro(message: Message) -> None:
    """Sticker → delete after 2s → loading animation → delete."""

    # ── Step 1: random sticker ─────────────────────────────────────────────
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

    # ── Step 2: loading bar ────────────────────────────────────────────────
    anim_msg = None

    try:
        anim_msg = await message.answer(
            f"<code>{_LOADING_FRAMES[0]}</code>",
            parse_mode=ParseMode.HTML,
        )

        for frame in _LOADING_FRAMES[1:]:
            await asyncio.sleep(0.2)

            await anim_msg.edit_text(
                f"<code>{frame}</code>",
                parse_mode=ParseMode.HTML,
            )

        await asyncio.sleep(0.5)

    except Exception:
        pass

    if anim_msg:
        try:
            await anim_msg.delete()
        except Exception:
            pass


def _intro_text(settings: Settings) -> str:
    return _safe_text(
        f"{pe('fire', '🎉')} Welcome to the Giveaway Manager Bot!\n\n"
        f"{pe('trophy', '🏆')} The Most Advanced Giveaway Bot on Telegram\n\n"
        f"{pe('star', '✨')} Features:\n"
        f"├ {pe('box', '🗳')} Voting Contests &amp;  Lucky Draws\n"
        f"├ {pe('money', '💰')} Paid Votes (UPI / Telegram Stars)\n"
        f"├ {pe('link', '🔗')} Referral Bonus System\n"
        f"├ {pe('data', '📊')} Live Leaderboards\n"
        f"├ {pe('shield', '🛡')} Anti-Cheat Protection\n"
        f"├ {pe('bopu', '📢')} Channel Post Creator\n\n"
        f"🔹 {settings.powered_by_text}\n"
        f"🔗 Support: {settings.support_link}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# START DEEP LINK
# ─────────────────────────────────────────────────────────────────────────────

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

        await process_participation_link(
            message,
            db,
            settings,
            giveaway_id,
            referrer_id,
        )

        return

    # Deep link but not giveaway → run full intro
    await _play_intro(message)

    try:
        await message.answer_photo(
            settings.banner_url,
            caption=_intro_text(settings),
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML,
        )

    except Exception:
        # Fallback if banner/photo fails
        await message.answer(
            _intro_text(settings),
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# NORMAL /START
# ─────────────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def start_root(
    message: Message,
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

    await _play_intro(message)

    try:
        await message.answer_photo(
            settings.banner_url,
            caption=_intro_text(settings),
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML,
        )

    except Exception:
        # Fallback if banner/photo fails
        await message.answer(
            _intro_text(settings),
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:root")
async def menu_root(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:

    await state.clear()
    await callback.answer()

    text = _intro_text(settings)

    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=main_menu_kb(),
            parse_mode=ParseMode.HTML,
        )

    except Exception:

        try:
            await callback.message.edit_text(
                text,
                reply_markup=main_menu_kb(),
                parse_mode=ParseMode.HTML,
            )

        except Exception:

            await callback.message.answer(
                text,
                reply_markup=main_menu_kb(),
                parse_mode=ParseMode.HTML,
            )


# ─────────────────────────────────────────────────────────────────────────────
# HOW TO USE
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:how_to_use")
async def how_to_use(callback: CallbackQuery) -> None:

    await callback.answer()

    text = _safe_text(
        "📖 How To Use This Bot\n\n"

        "1️⃣ Create a Giveaway\n"
        "   • Click New Giveaway and follow the steps\n"
        "   • Choose between Voting Contest or Lucky Draw\n"
        "   • Set Free or Paid mode\n\n"

        "2️⃣ Share The Link\n"
        "   • Share your giveaway participation link\n"
        "   • Participants join via the deep link\n\n"

        "3️⃣ Voting\n"
        "   • Channel subscribers can vote for participants\n"
        "   • Each subscriber can vote once per giveaway\n"
        "   • Votes are removed if the voter leaves the channel\n\n"

        "4️⃣ Paid Votes\n"
        "   • Participants can buy extra votes via UPI or Stars\n"
        "   • You (host) approve/deny payment screenshots\n\n"

        "5️⃣ Referral System\n"
        "   • Enable referrals so participants earn bonus votes\n"
        "   • Each friend they invite = bonus votes\n\n"

        "6️⃣ End Giveaway\n"
        "   • Click End Giveaway to announce the winner\n"
        "   • Winner is announced in the channel automatically"
    )

    await callback.message.answer(
        text,
        reply_markup=back_to_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DONATE
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:donate")
async def donate(
    callback: CallbackQuery,
    settings: Settings,
) -> None:

    await callback.answer()

    caption = _safe_text(
        "💖 Support This Bot\n\n"
        "Your support helps keep this bot running and free!\n"
        "Scan the QR code above to donate. Thank you! 🙏"
    )

    try:
        await callback.message.answer_photo(
            settings.donate_qr,
            caption=caption,
            reply_markup=back_to_menu_kb(),
            parse_mode=ParseMode.HTML,
        )

    except Exception:
        await callback.message.answer(
            _safe_text("💖 Thank you for supporting this bot!"),
            reply_markup=back_to_menu_kb(),
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────────────────────────────────────
# SUPPORT
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:support")
async def support(
    callback: CallbackQuery,
    settings: Settings,
) -> None:

    await callback.answer()

    text = _safe_text(
        f"🆘 Support\n\n"
        f"Need help? Contact us:\n"
        f"{settings.support_link}"
    )

    await callback.message.answer(
        text,
        reply_markup=back_to_menu_kb(),
        parse_mode=ParseMode.HTML,
    )

