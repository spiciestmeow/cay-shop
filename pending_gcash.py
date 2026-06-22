import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db

logger = logging.getLogger(__name__)

# ─── CALLBACK PREFIXES ────────────────────────────────────────────────────────
CB_PENDING_LIST    = "pending_gcash_list"
CB_PENDING_REFRESH = "pending_gcash_refresh"
CB_PENDING_DETAIL  = "pending_gcash_detail_"   # pending_gcash_detail_{tx_id}
CB_PENDING_BACK    = "pending_gcash_back"


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

async def show_pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Display all pending (unverified) GCash deposits in one list.
    Called from admin panel button or refresh callback.
    """
    query = update.callback_query
    await query.answer()

    rows = await _fetch_pending()

    if not rows:
        await query.message.edit_text(
            "💳 <b>Pending GCash Deposits</b>\n\n"
            "✅ No pending deposits right now.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data=CB_PENDING_REFRESH)],
                [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_main")],
            ]),
        )
        return

    lines = [f"💳 <b>Pending GCash Deposits</b> ({len(rows)} pending)\n"]
    buttons = []

    for row in rows:
        try:
            dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            date_str = dt.strftime("%m/%d %H:%M")
        except Exception:
            date_str = "—"

        user_id    = row.get("user_id", "?")
        amount_php = float(row.get("amount_php", 0))
        amount_usd = float(row.get("amount_usd", 0))
        tx_id      = row.get("id", "")

        lines.append(
            f"• <code>{user_id}</code> — ₱{amount_php:.0f} (${amount_usd:.2f}) — {date_str}"
        )
        buttons.append([
            InlineKeyboardButton(
                f"👁 ₱{amount_php:.0f} · {date_str}",
                callback_data=f"{CB_PENDING_DETAIL}{tx_id}",
            )
        ])

    buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data=CB_PENDING_REFRESH)])
    buttons.append([InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_main")])

    await query.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ─── DETAIL VIEW ─────────────────────────────────────────────────────────────

async def show_pending_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, tx_id: str
) -> None:
    """Show detail for a single pending deposit with approve/reject buttons."""
    query = update.callback_query
    await query.answer()

    row = await _fetch_pending_by_id(tx_id)
    if not row:
        await query.answer("❌ Transaction not found or already resolved.", show_alert=True)
        return

    user_id    = row.get("user_id")
    amount_php = float(row.get("amount_php", 0))
    amount_usd = float(row.get("amount_usd", 0))
    ref_no     = row.get("reference_no") or "—"
    photo_id   = row.get("receipt_photo_id")

    try:
        dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        date_str = dt.strftime("%m/%d/%Y %H:%M")
    except Exception:
        date_str = "—"

    target_user = await db.get_user(user_id)
    name = target_user.get("full_name", "Unknown") if target_user else "Unknown"

    detail_text = (
        f"💳 <b>GCash Deposit Detail</b>\n\n"
        f"👤 User: <code>{user_id}</code> ({name})\n"
        f"💵 Amount: ₱{amount_php:.2f} → ${amount_usd:.2f}\n"
        f"🧾 Reference: <code>{ref_no}</code>\n"
        f"📅 Submitted: {date_str}\n"
        f"📌 Status: <b>PENDING VERIFICATION</b>"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"admin_approve_gcash_{user_id}_{amount_php}",
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"admin_reject_gcash_{user_id}",
            ),
        ],
        [InlineKeyboardButton("⬅️ Back to list", callback_data=CB_PENDING_BACK)],
    ])

    if photo_id:
        try:
            await query.message.delete()
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=photo_id,
                caption=detail_text.replace("<b>", "").replace("</b>", "")
                         .replace("<code>", "").replace("</code>", ""),
                reply_markup=kb,
            )
            return
        except Exception as e:
            logger.warning(f"Could not send receipt photo: {e}")

    await query.message.edit_text(
        detail_text + "\n\n<i>No receipt photo on file.</i>",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─── CALLBACK ROUTER ─────────────────────────────────────────────────────────

async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Route pending GCash callbacks. Returns True if handled.
    Call this near the top of main.handle_callback.
    """
    query = update.callback_query
    data  = query.data

    if data in (CB_PENDING_LIST, CB_PENDING_REFRESH):
        await show_pending_list(update, context)
        return True

    if data.startswith(CB_PENDING_DETAIL):
        tx_id = data[len(CB_PENDING_DETAIL):]
        await show_pending_detail(update, context, tx_id)
        return True

    if data == CB_PENDING_BACK:
        await show_pending_list(update, context)
        return True

    return False


# ─── DB HELPERS ──────────────────────────────────────────────────────────────
# These query a `gcash_deposits` table. Adjust table/column names to match
# whatever gcash_topup.py uses in your Supabase setup.

GCASH_TABLE = "gcash_deposits"   # ← change if your table is named differently

async def _fetch_pending():
    """Return all rows where status = 'pending', newest first."""
    try:
        result = (
            db._client()
            .table(GCASH_TABLE)
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch pending GCash deposits: {e}", exc_info=e)
        return []


async def _fetch_pending_by_id(tx_id: str):
    """Return a single pending deposit row by its id."""
    try:
        result = (
            db._client()
            .table(GCASH_TABLE)
            .select("*")
            .eq("id", tx_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Failed to fetch GCash deposit {tx_id}: {e}", exc_info=e)
        return None