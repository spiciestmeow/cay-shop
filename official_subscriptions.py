"""
official_subscriptions.py
─────────────────────────
Handles the ✅ Official Subscriptions section of the bot.
"""

import db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    data = query.data or ""

    if data == "official_subs":
        await handle_official_subs(update, context)
        return True

    return False


async def handle_official_subs(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    # Fetch all categories marked as "official"
    all_cats = await db.get_categories()
    official_cats = [c for c in all_cats if c.get("type") == "official"]

    if not official_cats:
        await query.edit_message_text(
            "✅ <b>Official Subscriptions</b>\n\n"
            "📭 No subscriptions available yet.\n"
            "Check back soon!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back to services", callback_data="back_to_products")]
            ]),
        )
        return

    # Build buttons for each official category
    all_products = await db.get_all_products_flat()
    stock_by_cat: dict[int, int] = {}
    for p in all_products:
        stock_by_cat[p["category_id"]] = stock_by_cat.get(p["category_id"], 0) + p.get("stock", 0)

    buttons = []
    for cat in official_cats:
        has_stock = stock_by_cat.get(cat["id"], 0) > 0
        style = "default" if has_stock else "destructive"  # green if stock, red if not
        btn = InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_{cat['id']}",
        )
        btn.api_kwargs = {"style": style}
        buttons.append([btn])

    back_btn = InlineKeyboardButton("⬅️ Back to services", callback_data="back_to_products")
    back_btn.api_kwargs = {"style": "secondary"}  # gray
    buttons.append([back_btn])

    await query.edit_message_text(
        "Choose a product:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )