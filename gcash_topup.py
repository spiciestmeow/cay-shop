"""
GCash top-up flow.

Mirrors the existing TRC20 deposit pattern:
  1. User taps "🇵🇭 GCash" from the payment methods menu
  2. Bot asks for the deposit amount (PHP)
  3. Bot generates a unique centavo suffix (e.g. 1000 -> 1000.37) so admin
     can match the incoming GCash transaction to this specific request
  4. Bot shows a static GCash QR image (placeholder path below) + the exact
     amount to send + a 15-minute expiry, same as the TRC20 screen
  5. User taps "✅ I've Paid" -> bot DMs ADMIN_NOTIFY_CHAT_ID with the
     user's id, username, requested amount, and unique amount to verify
  6. Admin manually checks the GCash app transaction history and credits
     balance with /credit or whatever your existing admin balance command is
     (not included here — wire to whatever you already use for manual
     balance credits, since that wasn't in the code you shared)

Drop this file next to main.py and db.py, then wire it in per the
instructions at the bottom of this file.
"""

import random
import logging
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import ContextTypes

import db  # reuse your existing db module for sessions / users

logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────

# Swap this with your real GCash QR screenshot once ready.
# Must be a local file path (preferred — instant, no network dependency)
# or a direct HTTPS image URL.
GCASH_QR_IMAGE_PATH = "https://i.ibb.co/CKd4m9GB/photo-2026-06-20-11-02-58.jpg"

GCASH_ACCOUNT_NAME = "CL**DE B."
GCASH_NUMBER = "9956274340"

ADMIN_NOTIFY_CHAT_ID = 7399488750

MIN_AMOUNT_PHP = 50.0
MAX_AMOUNT_PHP = 50000.0
EXPIRY_MINUTES = 15

def _generate_unique_amount(base_amount: float) -> float:
    """
    Append a small unique centavo suffix to the requested amount so the
    admin can tell concurrent deposits apart in the GCash transaction
    history, the same way the TRC20 flow appends unique micro-USDT.
    e.g. 1000 -> 1000.37
    """
    cents = random.randint(1, 99)
    return round(base_amount + cents / 100, 2)


def _format_php(amount: float) -> str:
    return f"₱{amount:,.2f}"


# ─── ENTRY POINT: "🇵🇭 GCash" button pressed ─────────────────────────────

async def start_gcash_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Call this from the payment_gcash callback instead of just showing
    GCASH_INFO directly, if you want the amount-entry + QR flow.
    """
    query = update.callback_query
    user_id = update.effective_user.id

    await db.set_session(user_id, {"awaiting": "gcash_amount"})
    await query.answer()
    await query.message.edit_text(
        "<blockquote>🇵🇭 <b>Enter deposit amount</b> ‟</blockquote>\n\n"
        f"<b>Method:</b> GCash\n"
        f"<b>Minimum:</b> {_format_php(MIN_AMOUNT_PHP)}\n"
        f"<b>Maximum:</b> {_format_php(MAX_AMOUNT_PHP)}\n\n"
        "<i>Send numbers only, e.g. 500</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
        ]),
    )


# ─── TEXT INPUT HANDLER: amount typed in ─────────────────────────────────
# Call this from your _process_admin_input-style router, or add a parallel
# check in handle_message for awaiting == "gcash_amount" (this isn't an
# admin-only flow, so it shouldn't live inside the is_admin gate).

async def handle_gcash_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE, ud: dict) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please send numbers only, e.g. 500")
        return

    if amount < MIN_AMOUNT_PHP or amount > MAX_AMOUNT_PHP:
        await update.message.reply_text(
            f"❌ Amount must be between {_format_php(MIN_AMOUNT_PHP)} and {_format_php(MAX_AMOUNT_PHP)}."
        )
        return

    unique_amount = _generate_unique_amount(amount)
    expires_at = (datetime.utcnow() + timedelta(minutes=EXPIRY_MINUTES)).isoformat()

    ud["awaiting"] = None
    ud["gcash_pending"] = {
        "requested_amount": amount,
        "unique_amount": unique_amount,
        "expires_at": expires_at,
    }
    await db.set_session(user_id, ud)

    caption = (
        "<blockquote>📱 <b>GCash Payment Request</b> ‟</blockquote>\n\n"
        "✅ Scan the QR code or send payment to the number below.\n"
        f"⏳ <b>Expires in:</b> {EXPIRY_MINUTES} minutes\n\n"
        f"💰 <b>Amount to send:</b>\n<code>{unique_amount:.2f}</code>\n\n"
        f"📛 <b>Account name:</b> {GCASH_ACCOUNT_NAME}\n"
        f"📞 <b>GCash number:</b> <code>{GCASH_NUMBER}</code>\n\n"
        "<blockquote>📌 <b>Important</b> ‟</blockquote>\n\n"
        "• All deposits are <b>non-refundable</b>.\n"
        "• Send the <b>exact amount</b> shown above — the centavos matter, "
        "they're how we match your payment.\n"
        "• Only send via <b>GCash</b>.\n\n"
        "<blockquote>🕓 <b>Manual Confirmation</b> ‟</blockquote>\n\n"
        "<i>Once you've paid, tap \"I've Paid\" below. Your balance will be "
        "credited after our team verifies the transaction — usually within "
        "a few minutes.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data="gcash_paid")],
        [InlineKeyboardButton("❌ Cancel request", callback_data="gcash_cancel")],
    ])

    try:
        await update.message.reply_photo(
            photo=open(GCASH_QR_IMAGE_PATH, "rb"),
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except FileNotFoundError:
        # Falls back to text-only until the real QR image is in place.
        logger.warning(f"GCash QR image not found at {GCASH_QR_IMAGE_PATH}, sending text only.")
        await update.message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# ─── CALLBACKS: "I've Paid" / "Cancel request" ───────────────────────────
# Add these branches inside your existing handle_callback function.

async def handle_gcash_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    tg_user = update.effective_user

    ud = await db.get_session(user_id)
    pending = ud.get("gcash_pending")

    if not pending:
        await query.answer("⚠️ This request has expired. Please start a new deposit.", show_alert=True)
        return

    expires_at = datetime.fromisoformat(pending["expires_at"])
    if datetime.utcnow() > expires_at:
        ud.pop("gcash_pending", None)
        await db.set_session(user_id, ud)
        await query.answer("⚠️ This request has expired. Please start a new deposit.", show_alert=True)
        await query.message.edit_caption(
            caption="⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
            parse_mode="HTML",
        ) if query.message.caption else await query.message.edit_text(
            "⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit."
        )
        return

    await query.answer("✅ Thanks! We're verifying your payment.", show_alert=True)

    username = f"@{tg_user.username}" if tg_user.username else "no username"
    notify_text = (
        "🇵🇭 <b>New GCash Payment Claim</b>\n\n"
        f"👤 User: {tg_user.full_name} ({username})\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Requested: ₱{pending['requested_amount']:.2f}\n"
        f"🔢 Unique amount to verify: <code>{pending['unique_amount']:.2f}</code>\n\n"
        "Please check GCash transaction history for this exact amount, "
        "then credit the user's balance manually."
    )
    await context.bot.send_message(
        chat_id=ADMIN_NOTIFY_CHAT_ID,
        text=notify_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Open user profile", callback_data=f"admin_view_user_{user_id}")],
        ]),
    )

    confirmation_text = (
        "✅ <b>Payment claim received!</b>\n\n"
        "Our team will verify your transaction and credit your balance shortly. "
        "You'll be notified once it's confirmed."
    )
    if query.message.caption:
        await query.message.edit_caption(caption=confirmation_text, parse_mode="HTML")
    else:
        await query.message.edit_text(confirmation_text, parse_mode="HTML")


async def handle_gcash_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id

    ud = await db.get_session(user_id)
    ud.pop("gcash_pending", None)
    await db.set_session(user_id, ud)

    await query.answer("Request cancelled.")
    cancel_text = "❌ <b>GCash deposit request cancelled.</b>"
    if query.message.caption:
        await query.message.edit_caption(caption=cancel_text, parse_mode="HTML")
    else:
        await query.message.edit_text(cancel_text, parse_mode="HTML")