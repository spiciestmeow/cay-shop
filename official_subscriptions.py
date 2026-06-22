"""
official_subscriptions.py
─────────────────────────
Handles the ✅ Official Subscriptions section of the bot.

HOW TO WIRE INTO main.py
────────────────────────
1. Import:  import official_subscriptions

2. In handle_callback(), add at the very top (before other if blocks):
       if await official_subscriptions.route_callback(update, context):
           return
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


# ─── ROUTE HELPER ────────────────────────────────────────────────────────────

async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Call at the very top of handle_callback():
        if await official_subscriptions.route_callback(update, context):
            return
    Returns True if handled, False to let handle_callback continue.
    """
    query = update.callback_query
    data = query.data or ""

    if data == "official_subs":
        await handle_official_subs(update, context)
        return True

    return False


# ─── HANDLER ─────────────────────────────────────────────────────────────────

async def handle_official_subs(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "✅ <b>Official Subscriptions</b>\n\n"
        "📭 No subscriptions available yet.\n"
        "Check back soon!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to services", callback_data="back_to_products")]
        ]),
    )
