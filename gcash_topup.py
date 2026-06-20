"""
GCash top-up flow — with USD conversion display + receipt upload.

Changes vs previous version:
  • USD equivalent shown next to the PHP amount in the payment card
  • After tapping "I've Paid", bot asks for a screenshot/receipt
  • User sends the photo; bot forwards it to the admin channel with the
    claim details and Approve / Reject buttons
  • main.py needs ONE extra handler (see bottom of this file for the
    snippet to paste in)
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

import db

logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────

GCASH_QR_IMAGE_PATH = "https://i.ibb.co/CKd4m9GB/photo-2026-06-20-11-02-58.jpg"

GCASH_ACCOUNT_NAME = "CL**DE B."
GCASH_NUMBER       = "9956274340"

ADMIN_NOTIFY_CHAT_ID = -1004441073113

# Exchange rate: how many PHP = 1 USD.
# Change this to whatever your current rate is.
PHP_TO_USD_RATE = 56.0

MENU_BUTTONS = {
    "🛒 Products", "👤 Profile", "🎁 Invite Center",
    "💰 Top up balance", "🎫 Redeem Code", "📋 Bot Policy", "❓ Help",
}

MIN_AMOUNT_PHP     = 50.0
MAX_AMOUNT_PHP     = 50_000.0
EXPIRY_MINUTES     = 15       # production value
EXPIRY_SECONDS_TEST = 15      # TEMP – short expiry for testing
USE_TEST_EXPIRY    = True     # TEMP – flip to False for production


# ─── HELPERS ──────────────────────────────────────────────────────────────

def _php_to_usd(php: float) -> float:
    return round(php / PHP_TO_USD_RATE, 2)

def _format_php(amount: float) -> str:
    return f"₱{amount:,.2f}"

def _is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")

def _expiry_seconds() -> int:
    return EXPIRY_SECONDS_TEST if USE_TEST_EXPIRY else EXPIRY_MINUTES * 60

def _generate_unique_amount(base_amount: float) -> float:
    """Append a random centavo suffix so the admin can match the transaction."""
    cents = random.randint(1, 99)
    return round(base_amount + cents / 100, 2)


# ─── STEP 1 – "🇵🇭 GCash" button pressed ────────────────────────────────

async def start_gcash_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    user_id = update.effective_user.id

    await db.set_session(user_id, {"awaiting": "gcash_amount"})
    await query.answer()
    await query.message.edit_text(
        "<blockquote>🇵🇭 <b>Enter deposit amount</b></blockquote>\n\n"
        f"Network: <b>GCash</b>\n"
        f"Minimum: <b>{_format_php(MIN_AMOUNT_PHP)}</b> "
        f"(≈ <b>${_php_to_usd(MIN_AMOUNT_PHP):.2f}</b>)\n"
        f"Maximum: <b>{_format_php(MAX_AMOUNT_PHP)}</b> "
        f"(≈ <b>${_php_to_usd(MAX_AMOUNT_PHP):.2f}</b>)\n\n"
        "<i>Send numbers only, e.g. <b>500</b></i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
        ]),
    )


# ─── STEP 2 – user types the PHP amount ──────────────────────────────────

async def handle_gcash_amount_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, ud: dict
) -> None:
    user_id = update.effective_user.id
    text    = (update.message.text or "").strip()

    # Menu button tapped instead of typing an amount → cancel gracefully
    if text in MENU_BUTTONS:
        ud.pop("awaiting", None)
        ud.pop("gcash_pending", None)
        await db.set_session(user_id, ud)
        await update.message.reply_text("❌ GCash deposit request cancelled.")
        return "fallthrough"

    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid amount.\nSend numbers only (e.g. <b>500</b> or <b>500.5</b>).",
            parse_mode="HTML",
        )
        return

    if amount < MIN_AMOUNT_PHP or amount > MAX_AMOUNT_PHP:
        await update.message.reply_text(
            f"⚠️ Amount must be between "
            f"{_format_php(MIN_AMOUNT_PHP)} and {_format_php(MAX_AMOUNT_PHP)}."
        )
        return

    unique_amount  = _generate_unique_amount(amount)
    usd_equivalent = _php_to_usd(unique_amount)
    seconds        = _expiry_seconds()
    expires_at     = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()

    ud["awaiting"]     = None
    ud["gcash_pending"] = {
        "requested_amount": amount,
        "unique_amount":    unique_amount,
        "usd_equivalent":   usd_equivalent,
        "expires_at":       expires_at,
    }
    await db.set_session(user_id, ud)

    expires_label = (
        f"{seconds} seconds" if USE_TEST_EXPIRY
        else f"{EXPIRY_MINUTES} minutes"
    )

    caption = (
        "<blockquote>📱 <b>PHP Payment Request (GCash)</b></blockquote>\n\n"
        "✅ Scan the QR code or send payment to the number below.\n"
        f"⏳ <b>Expires in:</b> {expires_label}\n\n"

        # ── Amount block (PHP + USD) ──
        f"🪙 <b>Currency:</b> PHP (₱)\n"
        f"💰 <b>Amount to send (PHP):</b>\n"
        f"<pre><code>{unique_amount:.2f}</code></pre>\n"
        f"💵 <b>Equivalent in USD:</b>\n"
        f"<pre><code>≈ ${usd_equivalent:.2f}</code></pre>\n"
        f"<i>(Rate: ₱{PHP_TO_USD_RATE:.0f} = $1.00)</i>\n\n"

        f"📛 <b>Account name:</b>\n"
        f"<pre><code>{GCASH_ACCOUNT_NAME}</code></pre>\n"
        f"📞 <b>GCash number:</b>\n"
        f"<pre><code>{GCASH_NUMBER}</code></pre>\n\n"

        "⚠️ <i>Transfer fees may apply depending on your bank/e-wallet.</i>\n\n"

        "<blockquote>🔔 <b>Transfer Fee Notice</b></blockquote>\n\n"
        "• Some banks/e-wallets deduct a small transfer fee when sending via InstaPay.\n"
        f"• The amount received in our wallet must be exactly "
        f"<code>{unique_amount:.2f}</code>.\n"
        "• If your platform deducts fees, please add them on top of the payment amount.\n\n"

        "<blockquote>📌 <b>Important</b></blockquote>\n\n"
        "• All deposits are <b>non-refundable</b>.\n"
        "• Send the <b>exact amount</b> shown above — the centavos matter, "
        "they're how we match your payment.\n"
        "• Only send via <b>GCash</b>.\n\n"

        "<blockquote>🕓 <b>Manual Confirmation</b></blockquote>\n"
        "<i>Once you've paid, tap <b>\"I've Paid\"</b> below.\n"
        "You'll be asked to send your <b>payment receipt screenshot</b>.\n"
        "Your balance will be credited after our team verifies — usually within "
        "a few minutes.</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid", callback_data="gcash_paid")],
        [InlineKeyboardButton("❌ Cancel request", callback_data="gcash_cancel")],
    ])

    sent_message = None
    try:
        photo        = GCASH_QR_IMAGE_PATH if _is_url(GCASH_QR_IMAGE_PATH) \
                       else open(GCASH_QR_IMAGE_PATH, "rb")
        sent_message = await update.message.reply_photo(
            photo=photo, caption=caption,
            parse_mode="HTML", reply_markup=keyboard,
        )
    except FileNotFoundError:
        logger.warning("GCash QR image not found — sending text only.")
        sent_message = await update.message.reply_text(
            caption, parse_mode="HTML", reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning(f"GCash QR image failed ({GCASH_QR_IMAGE_PATH}): {e}")
        sent_message = await update.message.reply_text(
            caption, parse_mode="HTML", reply_markup=keyboard,
        )

    # Schedule auto-expiry job
    if sent_message is not None and context.job_queue is not None:
        context.job_queue.run_once(
            _expire_gcash_request,
            when=seconds,
            data={
                "user_id":       user_id,
                "chat_id":       sent_message.chat_id,
                "message_id":    sent_message.message_id,
                "unique_amount": unique_amount,
            },
            name=f"gcash_expire_{user_id}_{sent_message.message_id}",
        )
    elif context.job_queue is None:
        logger.warning(
            "context.job_queue is None — install python-telegram-bot[job-queue] "
            "for auto-expiry."
        )


# ─── AUTO-EXPIRY JOB ──────────────────────────────────────────────────────

async def _expire_gcash_request(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data       = context.job.data
    user_id        = job_data["user_id"]
    chat_id        = job_data["chat_id"]
    message_id     = job_data["message_id"]
    unique_amount  = job_data["unique_amount"]

    ud      = await db.get_session(user_id)
    pending = ud.get("gcash_pending")

    if not pending or pending.get("unique_amount") != unique_amount:
        return   # already paid / cancelled

    ud.pop("gcash_pending", None)
    ud.pop("awaiting_receipt", None)
    await db.set_session(user_id, ud)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Failed to delete expired GCash message: {e}")

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⌛️ Deposit request expired. Please create a new one.",
        )
    except Exception as e:
        logger.warning(f"Failed to send GCash expiry notice: {e}")


# ─── STEP 3a – "I've Paid" button ────────────────────────────────────────

async def handle_gcash_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    user_id = update.effective_user.id

    ud      = await db.get_session(user_id)
    pending = ud.get("gcash_pending")

    if not pending:
        await query.answer(
            "⚠️ This request has expired. Please start a new deposit.",
            show_alert=True,
        )
        return

    expires_at = datetime.fromisoformat(pending["expires_at"])
    if datetime.utcnow() > expires_at:
        ud.pop("gcash_pending", None)
        await db.set_session(user_id, ud)
        await query.answer(
            "⚠️ This request has expired. Please start a new deposit.",
            show_alert=True,
        )
        try:
            if query.message.caption:
                await query.message.edit_caption(
                    caption="⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
                    parse_mode="HTML",
                )
            else:
                await query.message.edit_text(
                    "⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
                    parse_mode="HTML",
                )
        except Exception:
            pass
        return

    # Mark that we're now waiting for the receipt photo
    ud["awaiting_receipt"] = True
    await db.set_session(user_id, ud)

    await query.answer("📸 Please send your receipt!", show_alert=False)

    # Delete the QR card and ask for the screenshot
    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            "📸 <b>Send your payment receipt</b>\n\n"
            "Please send a <b>screenshot</b> of your GCash transaction as a photo.\n\n"
            "<i>This helps our team verify your payment faster.</i>"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="gcash_cancel")],
        ]),
    )


# ─── STEP 3b – user sends the receipt photo ──────────────────────────────

async def handle_gcash_receipt_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Called by the photo MessageHandler in main.py when awaiting_receipt=True.
    Forwards the photo to admin with Approve / Reject buttons.
    """
    user_id = update.effective_user.id
    tg_user = update.effective_user

    ud      = await db.get_session(user_id)
    pending = ud.get("gcash_pending")

    if not ud.get("awaiting_receipt") or not pending:
        # Not in receipt flow — ignore (let main.py handle it normally)
        return

    # Validate the pending request hasn't expired
    expires_at = datetime.fromisoformat(pending["expires_at"])
    if datetime.utcnow() > expires_at:
        ud.pop("gcash_pending", None)
        ud.pop("awaiting_receipt", None)
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
            parse_mode="HTML",
        )
        return

    # Clear session — receipt collected, pending consumed
    ud.pop("awaiting_receipt", None)
    ud.pop("gcash_pending", None)
    await db.set_session(user_id, ud)

    php_amount  = pending["requested_amount"]
    unique_php  = pending["unique_amount"]
    usd_eq      = pending.get("usd_equivalent", round(unique_php / PHP_TO_USD_RATE, 2))
    username    = f"@{tg_user.username}" if tg_user.username else "no username"

    caption_admin = (
        "🇵🇭 <b>New GCash Payment Claim</b>\n"
        "🟡 <b>Status: PENDING VERIFICATION</b>\n\n"
        f"👤 <b>User:</b> {tg_user.full_name} ({username})\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>Requested:</b> ₱{php_amount:.2f} (≈ ${_php_to_usd(php_amount):.2f})\n"
        f"🔢 <b>Unique amount to verify:</b> <code>{unique_php:.2f}</code>\n"
        f"💵 <b>USD equivalent:</b> ≈ <b>${usd_eq:.2f}</b>\n\n"
        "📸 <b>Receipt attached above.</b>\n"
        "Check GCash for the exact centavo amount, then approve or reject below."
    )

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"admin_approve_gcash_{user_id}_{php_amount}",
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"admin_reject_gcash_{user_id}",
            ),
        ],
        [InlineKeyboardButton("👤 Open user profile", callback_data=f"admin_view_user_{user_id}")],
    ])

    # Forward the receipt photo to the admin channel
    photo_file_id = update.message.photo[-1].file_id   # best quality
    try:
        await context.bot.send_photo(
            chat_id=ADMIN_NOTIFY_CHAT_ID,
            photo=photo_file_id,
            caption=caption_admin,
            parse_mode="HTML",
            reply_markup=admin_keyboard,
        )
    except Exception as e:
        logger.error(f"Failed to forward receipt to admin: {e}")
        # Fallback: send text only
        try:
            await context.bot.send_message(
                chat_id=ADMIN_NOTIFY_CHAT_ID,
                text=caption_admin + "\n\n⚠️ <i>Receipt photo could not be forwarded.</i>",
                parse_mode="HTML",
                reply_markup=admin_keyboard,
            )
        except Exception as e2:
            logger.error(f"Admin text fallback also failed: {e2}")

    # Confirm to user
    await update.message.reply_text(
        "✅ <b>Receipt received!</b>\n\n"
        f"💰 PHP: <b>₱{unique_php:.2f}</b>\n"
        f"💵 USD equivalent: <b>≈ ${usd_eq:.2f}</b>\n\n"
        "Our team will verify your payment and credit your balance shortly. "
        "You'll be notified once confirmed. 🙏",
        parse_mode="HTML",
    )


# ─── "Cancel request" button ─────────────────────────────────────────────

async def handle_gcash_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    user_id = update.effective_user.id

    ud = await db.get_session(user_id)
    ud.pop("gcash_pending", None)
    ud.pop("awaiting_receipt", None)
    await db.set_session(user_id, ud)

    await query.answer("Request cancelled.")
    try:
        await query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="❌ <b>GCash deposit request cancelled.</b>",
        parse_mode="HTML",
    )


# ─── SNIPPET TO ADD IN main.py ────────────────────────────────────────────
#
# 1. In handle_message(), BEFORE the admin-input block, add:
#
#        # ── GCash receipt photo (any user) ──
#        if ud.get("awaiting_receipt"):
#            # handled by the photo handler below — ignore text here
#            await update.message.reply_text(
#                "📸 Please send your GCash receipt as a <b>photo</b>.",
#                parse_mode="HTML",
#            )
#            return
#
# 2. Register a new handler BEFORE the existing MessageHandler line:
#
#        app.add_handler(MessageHandler(
#            filters.PHOTO & ~filters.COMMAND,
#            handle_gcash_receipt,
#        ))
#
# 3. Add the handler function somewhere in main.py:
#
#        async def handle_gcash_receipt(
#            update: Update, context: ContextTypes.DEFAULT_TYPE
#        ) -> None:
#            user_id = update.effective_user.id
#            ud = await db.get_session(user_id)
#            if ud.get("awaiting_receipt"):
#                await gcash_topup.handle_gcash_receipt_photo(update, context)