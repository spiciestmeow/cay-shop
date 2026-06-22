import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db

logger = logging.getLogger(__name__)

# ─── CALLBACK PREFIXES ────────────────────────────────────────────────────────
CB_PENDING_LIST    = "pending_gcash_list"
CB_PENDING_REFRESH = "pending_gcash_refresh"
CB_PENDING_BACK    = "pending_gcash_back"

# ─── SETTINGS KEY used to store pending list in cay_shop_settings ────────────
# We reuse the existing settings table as a lightweight pending store.
# Key format:  gcash_pending_{user_id}
# Value format: JSON string with deposit info

import json

PENDING_KEY_PREFIX = "gcash_pending_"


# ─── PUBLIC: save/clear a pending receipt (called from gcash_topup.py) ────────

async def register_pending(user_id: int, pending: dict, photo_file_id: str) -> None:
    """
    Call this right after forwarding the receipt photo to the admin.
    Stores a lightweight record so the admin panel can list it.
    """
    record = {
        "user_id":       user_id,
        "unique_amount": pending.get("unique_amount", 0),
        "usd_equivalent": pending.get("usd_equivalent", 0),
        "rate_used":     pending.get("rate_used", 0),
        "photo_file_id": photo_file_id,
        "submitted_at":  datetime.utcnow().strftime("%m/%d %H:%M"),
    }
    await db.set_setting(f"{PENDING_KEY_PREFIX}{user_id}", json.dumps(record))


async def clear_pending(user_id: int) -> None:
    """
    Call this after approving or rejecting a deposit.
    Removes the pending record from the settings store.
    """
    await db.set_setting(f"{PENDING_KEY_PREFIX}{user_id}", "")


async def get_all_pending() -> list[dict]:
    """
    Return all pending GCash deposits from cay_shop_settings.
    """
    try:
        c = db._client()
        result = (
            c.table(db.SETTINGS_TABLE)
            .select("key, value")
            .like("key", f"{PENDING_KEY_PREFIX}%")
            .execute()
        )
        rows = result.data or []
        out = []
        for row in rows:
            val = row.get("value", "")
            if not val:
                continue
            try:
                record = json.loads(val)
                out.append(record)
            except Exception:
                continue
        return out
    except Exception as e:
        logger.error(f"Failed to fetch pending GCash list: {e}", exc_info=e)
        return []


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

async def show_pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    rows = await get_all_pending()

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

    lines = [f"💳 <b>Pending GCash Deposits</b> — {len(rows)} waiting\n"]
    for row in rows:
        user_id    = row.get("user_id", "?")
        amount_php = float(row.get("unique_amount", 0))
        amount_usd = float(row.get("usd_equivalent", 0))
        submitted  = row.get("submitted_at", "—")
        lines.append(
            f"• <code>{user_id}</code> — ₱{amount_php:.2f} (≈${amount_usd:.2f}) — {submitted}"
        )

    lines.append(
        "\n<i>Approve or Reject from the receipt photo sent to your admin chat.</i>"
    )

    await query.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data=CB_PENDING_REFRESH)],
            [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_main")],
        ]),
    )


# ─── CALLBACK ROUTER ─────────────────────────────────────────────────────────

async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data  = query.data

    if data in (CB_PENDING_LIST, CB_PENDING_REFRESH, CB_PENDING_BACK):
        await show_pending_list(update, context)
        return True

    return False