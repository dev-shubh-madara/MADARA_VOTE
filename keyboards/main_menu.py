from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.emoji import eid
from utils.fonts import btn


# ── Main Menu ──────────────────────────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn("🎁 New Giveaway"), callback_data="menu:new_giveaway",
                                  style=ButtonStyle.PRIMARY, icon_custom_emoji_id=eid("rocket")),
            InlineKeyboardButton(text=btn("📋 My Giveaways"), callback_data="menu:my_giveaways"),
        ],
        [
            InlineKeyboardButton(text=btn("➕ Add Channel"), callback_data="menu:add_channel"),
            InlineKeyboardButton(text=btn("📝 Create Post"), callback_data="menu:create_post"),
        ],
        [
            InlineKeyboardButton(text=btn("📖 How To Use"), callback_data="menu:how_to_use"),
            InlineKeyboardButton(text=btn("💖 Donate"), callback_data="menu:donate"),
        ],
        [InlineKeyboardButton(text=btn("🆘 Support"), callback_data="menu:support")],
    ])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("🔙 Main Menu"), callback_data="menu:root")],
    ])


# ── Giveaway Creation ──────────────────────────────────────────────────────────
def giveaway_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("🗳 Voting Contest"), callback_data="newg:type:voting", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=btn("🎰 Lucky Draw"), callback_data="newg:type:lucky", style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=btn("🔙 Cancel"), callback_data="menu:root", style=ButtonStyle.DANGER)],
    ])


def giveaway_mode_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("🆓 Free Mode"), callback_data="newg:mode:free")],
        [InlineKeyboardButton(text=btn("💰 Paid Mode (UPI/QR)"), callback_data="newg:mode:paid",
                               icon_custom_emoji_id=eid("money"))],
        [InlineKeyboardButton(text=btn("⭐ Stars Mode"), callback_data="newg:mode:stars",
                               icon_custom_emoji_id=eid("star"))],
        [InlineKeyboardButton(text=btn("🔙 Back"), callback_data="newg:back:type")],
    ])


def referral_setup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("✅ Enable Referral Bonus"), callback_data="newg:referral:yes",
                               style=ButtonStyle.SUCCESS, icon_custom_emoji_id=eid("check"))],
        [InlineKeyboardButton(text=btn("❌ No Referral"), callback_data="newg:referral:no", style=ButtonStyle.DANGER)],
    ])


def skip_kb(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("⏭ Skip"), callback_data=callback_data)],
    ])


# ── Manage Giveaway ────────────────────────────────────────────────────────────
def manage_giveaway_kb(giveaway_id: int, giveaway_type: str = "voting", paid: bool = True, referral: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=btn("🏆 Leaderboard"), callback_data=f"giveaway:leaderboard:{giveaway_id}",
                               icon_custom_emoji_id=eid("trophy"))],
        [InlineKeyboardButton(text=btn("📊 Stats"), callback_data=f"giveaway:stats:{giveaway_id}")],
    ]
    if paid:
        rows.append([InlineKeyboardButton(text=btn("🛑 Stop Paid Votes"), callback_data=f"giveaway:stop_paid:{giveaway_id}",
                                           style=ButtonStyle.DANGER)])
    rows.append([InlineKeyboardButton(text=btn("🔒 Stop Participation"), callback_data=f"giveaway:stop_part:{giveaway_id}",
                                       style=ButtonStyle.DANGER)])
    if referral:
        rows.append([InlineKeyboardButton(text=btn("🔗 Toggle Referral"), callback_data=f"giveaway:toggle_ref:{giveaway_id}")])
    rows.append([InlineKeyboardButton(text=btn("🗑 Clear Channel Posts"), callback_data=f"giveaway:clear_posts:{giveaway_id}",
                                       style=ButtonStyle.DANGER)])
    rows.append([InlineKeyboardButton(text=btn("🏁 End Giveaway"), callback_data=f"giveaway:end:{giveaway_id}",
                                       style=ButtonStyle.DANGER)])
    rows.append([InlineKeyboardButton(text=btn("🔙 Main Menu"), callback_data="menu:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_giveaways_kb(giveaways: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for g in giveaways:
        icon = "🗳" if g["giveaway_type"] == "voting" else "🎰"
        label = btn(f"{icon} {g['title'][:30]}")
        rows.append([InlineKeyboardButton(text=label, callback_data=f"giveaway:manage:{g['id']}")])
    rows.append([InlineKeyboardButton(text=btn("🔙 Main Menu"), callback_data="menu:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def end_confirm_kb(giveaway_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn("✅ Yes, End It"), callback_data=f"giveaway:end_confirm:{giveaway_id}",
                                  style=ButtonStyle.SUCCESS, icon_custom_emoji_id=eid("check")),
            InlineKeyboardButton(text=btn("❌ Cancel"), callback_data=f"giveaway:manage:{giveaway_id}",
                                  style=ButtonStyle.DANGER, icon_custom_emoji_id=eid("cross")),
        ],
    ])


# ── Participation ──────────────────────────────────────────────────────────────
# NOTE: these render inside channel posts, where icon_custom_emoji_id can't display
# (custom emoji on buttons/messages needs Fragment for channels - see utils/emoji.py).
# `style` (button color) has no such restriction and works fine here.
def participation_kb(giveaway_id: int, paid_enabled: bool, referral_enabled: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=btn("📋 Copy My Vote Link"), callback_data=f"giveaway:copy_link:{giveaway_id}",
                               style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton(text=btn("🏆 Live Leaderboard"), callback_data=f"giveaway:leaderboard:{giveaway_id}")],
    ]
    if paid_enabled:
        rows.insert(1, [InlineKeyboardButton(text=btn("💰 Buy Extra Votes"), callback_data=f"payment:start:{giveaway_id}",
                                              style=ButtonStyle.SUCCESS)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def participant_vote_kb(giveaway_id: int, participant_id: int, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn(f"🗳 Vote ({count})"), callback_data=f"vote:{giveaway_id}:{participant_id}",
                               style=ButtonStyle.PRIMARY)],
    ])


# ── Payment ────────────────────────────────────────────────────────────────────
def payment_mode_kb(giveaway_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn("💵 UPI / Money"), callback_data=f"payment:mode:money:{giveaway_id}",
                               icon_custom_emoji_id=eid("money"))],
        [InlineKeyboardButton(text=btn("⭐ Telegram Stars"), callback_data=f"payment:mode:stars:{giveaway_id}",
                               icon_custom_emoji_id=eid("star"))],
        [InlineKeyboardButton(text=btn("🔙 Back"), callback_data=f"giveaway:copy_link:{giveaway_id}")],
    ])


def payment_review_kb(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn("✅ Approve"), callback_data=f"payment:approve:{payment_id}",
                                  style=ButtonStyle.SUCCESS, icon_custom_emoji_id=eid("check")),
            InlineKeyboardButton(text=btn("❌ Deny"), callback_data=f"payment:deny:{payment_id}",
                                  style=ButtonStyle.DANGER, icon_custom_emoji_id=eid("cross")),
        ],
    ])


# ── Admin Panel ────────────────────────────────────────────────────────────────
def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn("📊 Bot Stats"), callback_data="admin:stats"),
            InlineKeyboardButton(text=btn("📢 Broadcast"), callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton(text=btn("👤 User Info"), callback_data="admin:userinfo"),
            InlineKeyboardButton(text=btn("🚫 Ban User"), callback_data="admin:ban",
                                  style=ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton(text=btn("✅ Unban User"), callback_data="admin:unban",
                                  style=ButtonStyle.SUCCESS),
            InlineKeyboardButton(text=btn("👑 Add Admin"), callback_data="admin:addadmin",
                                  icon_custom_emoji_id=eid("crown")),
        ],
        [InlineKeyboardButton(text=btn("🔙 Main Menu"), callback_data="menu:root")],
    ])


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn("✅ Send Broadcast"), callback_data="admin:broadcast_confirm",
                                  style=ButtonStyle.SUCCESS, icon_custom_emoji_id=eid("check")),
            InlineKeyboardButton(text=btn("❌ Cancel"), callback_data="admin:broadcast_cancel",
                                  style=ButtonStyle.DANGER, icon_custom_emoji_id=eid("cross")),
        ],
    ])
