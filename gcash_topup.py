"""
GCash top-up flow.

Mirrors the existing TRC20 deposit pattern:
  1. User taps "🇵🇭 GCash" from the payment methods menu
  2. Bot asks for the deposit amount (PHP)
  3. Bot generates a unique centavo suffix (e.g. 1000 -> 1000.37) so admin
     can match the incoming GCash transaction to this specific request
  4. Bot shows a static GCash QR image + the exact amount to send + a
     15-minute expiry, same as the TRC20 screen
  5. User taps "✅ I've Paid" -> bot DMs ADMIN_NOTIFY_CHAT_ID with the
     user's id, username, requested amount, and unique amount to verify
  6. Admin manually checks the GCash app transaction history and credits
     balance with /credit or whatever your existing admin balance command is
     (not included here — wire to whatever you already use for manual
     balance credits)

Drop this file next to main.py and db.py.
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

# Can be a local file path OR a direct HTTPS image URL (e.g. imgbb "Direct
# links" output). URLs are detected automatically below.
GCASH_QR_IMAGE_PATH = "https://i.ibb.co/CKd4m9GB/photo-2026-06-20-11-02-58.jpg"

GCASH_ACCOUNT_NAME = "CL**DE B."
GCASH_NUMBER = "9956274340"

ADMIN_NOTIFY_CHAT_ID = -1004441073113

# Keep this in sync with MENU_BUTTONS in main.py. Duplicated here (rather
# than imported) to avoid a circular import, since main.py imports this
# module.
MENU_BUTTONS = {
    "🛒 Products", "👤 Profile", "🎁 Invite Center",
    "💰 Top up balance", "🎫 Redeem Code", "📋 Bot Policy", "❓ Help",
}

MIN_AMOUNT_PHP = 50.0
MAX_AMOUNT_PHP = 50000.0
EXPIRY_MINUTES = 15        # real value for production
EXPIRY_SECONDS_TEST = 15    # TEMP: short expiry for testing — remove when done testing
USE_TEST_EXPIRY = True     # TEMP: flip to False to use EXPIRY_MINUTES instead


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


def _is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def _expiry_seconds() -> int:
    """TEMP: returns the short test duration if USE_TEST_EXPIRY is on,
    otherwise the real EXPIRY_MINUTES converted to seconds."""
    if USE_TEST_EXPIRY:
        return EXPIRY_SECONDS_TEST
    return EXPIRY_MINUTES * 60


# ─── ENTRY POINT: "🇵🇭 GCash" button pressed ─────────────────────────────

async def start_gcash_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id

    await db.set_session(user_id, {"awaiting": "gcash_amount"})
    await query.answer()
    await query.message.edit_text(
        "<blockquote>🇵🇭 <b>Enter deposit amount</b></blockquote>\n\n"
        f"Network: <b>GCash</b>\n"
        f"Minimum: <b>{_format_php(MIN_AMOUNT_PHP)}</b>\n"
        f"Maximum: <b>{_format_php(MAX_AMOUNT_PHP)}</b>\n\n"
        "<i>Send numbers only, e.g. <b>50</b></i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
        ]),
    )


# ─── TEXT INPUT HANDLER: amount typed in ─────────────────────────────────

async def handle_gcash_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE, ud: dict) -> None:
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    # If the user tapped a main-menu button instead of typing an amount,
    # treat it as cancelling this GCash request rather than an invalid
    # amount — then let the message fall through to the normal menu
    # handler so their tap still does something.
    if text in MENU_BUTTONS:
        ud.pop("awaiting", None)
        ud.pop("gcash_pending", None)
        await db.set_session(user_id, ud)
        await update.message.reply_text("❌ GCash deposit request cancelled.")
        return "fallthrough"

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
    seconds = _expiry_seconds()
    expires_at = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()

    ud["awaiting"] = None
    ud["gcash_pending"] = {
        "requested_amount": amount,
        "unique_amount": unique_amount,
        "expires_at": expires_at,
    }
    await db.set_session(user_id, ud)

    expires_label = (
        f"{seconds} seconds" if USE_TEST_EXPIRY
        else f"{EXPIRY_MINUTES} minutes"
    )

    caption = (
        "<blockquote>📱 <b>Php Payment Request(GCash)</b></blockquote>\n\n"
        "✅ Scan the QR code or send payment to the number below.\n"
        f"⏳ <b>Expires in:</b> {expires_label}\n\n"
        f"🪙 <b>currency:</b> PHP (₱)\n"
        f"💰 <b>Amount to send:</b>👇\n"
        f"<pre><code>{unique_amount:.2f}</code></pre>\n"
        f"📛 <b>Account name:</b>👇\n"
        f"<pre><code>{GCASH_ACCOUNT_NAME}</code></pre>\n"
        f"📞 <b>GCash number:</b>👇\n"
        f"<pre><code>{GCASH_NUMBER}</code></pre>\n\n"
        "⚠️ <i>Transfer fees may apply depending on your bank/e-wallet.</i>\n\n"
        "<blockquote>🔔 <b>Transfer Fee Notice</b></blockquote>\n\n"
        "• Some banks/e-wallets deduct a small transfer fee when sending via InstaPay.\n"
        f"• The amount received in our wallet must be exactly <code>{unique_amount:.2f}</code>.\n"
        "• If your platform deducts fees, please add them on top of the payment amount.\n\n"
        "<blockquote>📌 <b>Important</b></blockquote>\n\n"
        "• All deposits are <b>non-refundable</b>.\n"
        "• Send the <b>exact amount</b> shown above — the centavos matter, "
        "they're how we match your payment.\n"
        "• Only send via <b>GCash</b>.\n\n"
        "<blockquote>🕓 <b>Manual Confirmation</b></blockquote>"
        "<i>Once you've paid, tap <b>\"I've Paid\"</b> below. Your balance will be "
        "credited after our team verifies the transaction — usually within "
        "a few minutes.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data="gcash_paid")],
        [InlineKeyboardButton("❌ Cancel request", callback_data="gcash_cancel")],
    ])

    sent_message = None
    try:
        photo = GCASH_QR_IMAGE_PATH if _is_url(GCASH_QR_IMAGE_PATH) else open(GCASH_QR_IMAGE_PATH, "rb")
        sent_message = await update.message.reply_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except FileNotFoundError:
        logger.warning(f"GCash QR image not found at {GCASH_QR_IMAGE_PATH}, sending text only.")
        sent_message = await update.message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        # Catches Telegram API errors (bad/unreachable URL, etc.) so the
        # flow degrades to text instead of crashing the handler.
        logger.warning(f"GCash QR image failed to send ({GCASH_QR_IMAGE_PATH}): {e}")
        sent_message = await update.message.reply_text(
            caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # Schedule auto-expiry: after `seconds`, if the request is still
    # pending (user never tapped Paid/Cancel), delete the message and
    # clear the session so a stale request can't be marked paid later.
    if sent_message is not None and context.job_queue is not None:
        context.job_queue.run_once(
            _expire_gcash_request,
            when=seconds,
            data={
                "user_id": user_id,
                "chat_id": sent_message.chat_id,
                "message_id": sent_message.message_id,
                "unique_amount": unique_amount,
            },
            name=f"gcash_expire_{user_id}_{sent_message.message_id}",
        )
    elif context.job_queue is None:
        logger.warning(
            "context.job_queue is None — JobQueue is not enabled. "
            "Install with `pip install python-telegram-bot[job-queue]` "
            "for auto-expiry to work."
        )


# ─── AUTO-EXPIRY JOB ──────────────────────────────────────────────────────

async def _expire_gcash_request(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Runs once, `seconds` after a GCash request is created. If the user
    never tapped "I've Paid" or "Cancel", this deletes the message and
    clears gcash_pending so the request can't be claimed late.
    """
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]
    unique_amount = job_data["unique_amount"]

    ud = await db.get_session(user_id)
    pending = ud.get("gcash_pending")

    # Already paid or cancelled — nothing to expire.
    if not pending or pending.get("unique_amount") != unique_amount:
        return

    ud.pop("gcash_pending", None)
    await db.set_session(user_id, ud)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to delete expired GCash message ({chat_id}/{message_id}): {e}")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⌛️ Deposit request expired. Please create a new one.",
        )
    except Exception as e:
        logger.warning(f"Failed to send GCash expiry notice to {chat_id}: {e}")


# ─── CALLBACKS: "I've Paid" / "Cancel request" ───────────────────────────

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
        if query.message.caption:
            await query.message.edit_caption(
                caption="⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
                parse_mode="HTML",
            )
        else:
            await query.message.edit_text(
                "⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit."
            )
        return

    # ✅ ADD THIS — clear gcash_pending so the expiry job sees it's been handled
    ud.pop("gcash_pending", None)
    await db.set_session(user_id, ud)

    await query.answer("✅ Thanks! We're verifying your payment.", show_alert=True)

    username = f"@{tg_user.username}" if tg_user.username else "no username"
    notify_text = (
        "🇵🇭 <b>New GCash Payment Claim</b>\n"
        "🟡 <b>Status: PENDING VERIFICATION</b>\n\n"
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
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_gcash_{user_id}_{pending['requested_amount']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_gcash_{user_id}"),
            ],
            [InlineKeyboardButton("👤 Open user profile", callback_data=f"admin_view_user_{user_id}")],
        ]),
    )

    confirmation_text = (
        "✅ <b>Payment claim received!</b>\n\n"
        "Our team will verify your transaction and credit your balance shortly. "
        "You'll be notified once it's confirmed."
    )
    # Delete the QR photo message, then send a plain text confirmation
    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=confirmation_text,
        parse_mode="HTML",
    )

async def handle_gcash_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id

    ud = await db.get_session(user_id)
    ud.pop("gcash_pending", None)
    await db.set_session(user_id, ud)

    await query.answer("Request cancelled.")
    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="❌ <b>GCash deposit request cancelled.</b>",
        parse_mode="HTML",
    )