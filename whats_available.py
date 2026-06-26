"""
whats_available.py
──────────────────
Handles the 🟢 What's Available section.
"""

import db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if query.data == "whats_available":
        await handle_whats_available(update, context)
        return True
    return False


async def handle_whats_available(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = await db.get_all_products_availability()
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_products")]
        ]),
    )