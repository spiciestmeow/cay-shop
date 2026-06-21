"""
membership_gate.py — Forces users to join a Telegram group + channel
before they can use the bot. Re-checked on every action (strict mode),
so leaving after passing the check loses access again immediately.

SETUP REQUIRED:
1. Fill in GROUP_ID / GROUP_URL and CHANNEL_ID / CHANNEL_URL below.
2. The bot must be an ADMIN in both the group and the channel, or
   get_chat_member() will fail / return inaccurate results.
3. Wire into main.py — see the 3 hook points described at the bottom
   of this file.
"""

import logging
import time

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError

import db

logger = logging.getLogger(__name__)

# ─── CONFIG — fill these in ────────────────────────────────────────────────

# Numeric chat ID or "@username" works for get_chat_member.
GROUP_ID    = "@your_group_username"      # ← TODO: replace
CHANNEL_ID  = "@your_channel_username"    # ← TODO: replace

# Public-facing invite links shown on the buttons (can differ from the IDs
# above, e.g. if you use a private invite link instead of a public @username).
GROUP_URL   = "https://t.me/your_group_username"     # ← TODO: replace
CHANNEL_URL = "https://t.me/your_channel_username"    # ← TODO: replace

# How long (seconds) a "passed" membership check is cached in the session
# before we re-check with Telegram. Keeps strict enforcement without
# hammering get_chat_member on every single tap.
CACHE_SECONDS = 60

# Statuses that count as "still a member" for both groups and channels.
MEMBER_STATUSES = {"member", "administrator", "creator"}

GATE_TEXT = (
    "👋 <b>Hello there!</b>\n\n"
    "To use this bot and access our services, you must first join our "
    "Telegram group and channel.\n\n"
    "👇 Click the buttons below to join, then click <b>\"Check Membership\"</b>."
)


def _gate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Join Group", url=GROUP_URL)],
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("✅ Check Membership", callback_data="gate_check")],
    ])


async def _is_member_of(context: ContextTypes.DEFAULT_TYPE, chat_id: str, user_id: int) -> bool:
    """Low-level check against a single chat. Treats API errors as 'not a member'
    rather than crashing — e.g. user never started a DM with the bot, chat
    not found, bot lacks rights, etc."""
    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in MEMBER_STATUSES
    except TelegramError as e:
        logger.warning(f"get_chat_member failed for {chat_id} / user {user_id}: {e}")
        return False


async def check_membership(context: ContextTypes.DEFAULT_TYPE, user_id: int, use_cache: bool = True) -> bool:
    """
    Returns True if the user currently belongs to BOTH the group and the
    channel. Caches a positive result in the session for CACHE_SECONDS to
    avoid hammering Telegram on every tap; cache is skipped for negative
    results so re-joining is picked up immediately on next check.
    """
    ud = await db.get_session(user_id)

    if use_cache:
        cached_at = ud.get("gate_passed_at")
        if cached_at and (time.time() - cached_at) < CACHE_SECONDS:
            return True

    in_group   = await _is_member_of(context, GROUP_ID, user_id)
    in_channel = await _is_member_of(context, CHANNEL_ID, user_id)
    passed = in_group and in_channel

    if passed:
        ud["gate_passed_at"] = time.time()
        await db.set_session(user_id, ud)
    else:
        # Make sure a stale cached pass doesn't linger if they left.
        if "gate_passed_at" in ud:
            ud.pop("gate_passed_at", None)
            await db.set_session(user_id, ud)

    return passed


async def send_gate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the join-prompt screen. Works whether triggered by a text
    message or a callback query."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.message.edit_text(
                GATE_TEXT, parse_mode="HTML", reply_markup=_gate_keyboard()
            )
            return
        except Exception:
            # e.g. original message had a photo, can't edit_text on it
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=GATE_TEXT, parse_mode="HTML", reply_markup=_gate_keyboard(),
        )
    else:
        await update.message.reply_text(
            GATE_TEXT, parse_mode="HTML", reply_markup=_gate_keyboard()
        )


async def handle_gate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback handler for the 'Check Membership' button."""
    query = update.callback_query
    user_id = update.effective_user.id

    passed = await check_membership(context, user_id, use_cache=False)

    if passed:
        await query.answer("✅ Verified! Welcome in.", show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        # Caller's main.py should show the main menu right after this —
        # see main_after_gate() below, called from the handler in main.py.
    else:
        await query.answer(
            "❌ You haven't joined both the group and channel yet. "
            "Please join, then tap Check Membership again.",
            show_alert=True,
        )
