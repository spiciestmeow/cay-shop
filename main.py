import os
import asyncio
import logging
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    PicklePersistence,
)
from telegram.error import Conflict, NetworkError
import gcash_topup
import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🛒 Products")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🎁 Invite Center")],
        [KeyboardButton("💰 Top up balance"), KeyboardButton("🎫 Redeem Code")],
        [KeyboardButton("📋 Bot Policy"), KeyboardButton("❓ Help")],
    ],
    resize_keyboard=True,
)

BOT_POLICY = (
    "🗒 <b>Bot Policy</b>\n\n"
    "We believe in complete transparency with our customers and do not seek to annoy or exploit anyone. "
    "Please read the following policy carefully before using our services:\n\n"
    "1️⃣ <b>Refund Policy:</b>\n"
    "Funds cannot be refunded after depositing to the bot, except in one case only: if you deposit and do not "
    "purchase any product (i.e., the transaction is incomplete), in this case your money will be fully refunded.\n\n"
    "2️⃣ <b>Warranty Policy:</b>\n"
    "We guarantee all products that mention warranty. In case of any problem during the warranty period, "
    "we will take one of the following actions:\n"
    "• Replace the service immediately and compensate the user.\n"
    "• Or if the user does not wish to replace, the amount will be returned as balance in the bot and can be "
    "used to purchase any other product.\n\n"
    "3️⃣ <b>Free Credits:</b>\n"
    "Funds received by the user through redeem codes or referral rewards cannot be refunded.\n\n"
    "4️⃣ <b>Our Commitment:</b>\n"
    "We are fully responsible for our services and strive to ensure that no customer is annoyed or harmed.\n\n"
    "5️⃣ <b>Our Promise:</b>\n"
    "We promise to always be honest and faithful with you, and strive to be the best in providing these services."
)

HELP_TEXT = (
    "💬 <b>Support &amp; Assistance</b>\n\n"
    "✉️ If you need help, please contact\n"
    "<b>Customer Support:</b> @caydigitals\n\n"
    "⏳ You will receive a response once your request has been reviewed"
)

# ─── PAYMENT METHODS ──────────────────────────────────────────────────────
PAYMENT_METHODS_TEXT = (
    "<blockquote>💳 <b>Choose your preferred payment method:</b></blockquote>\n"
    "• <b>BEP20 (USDT)</b> — BNB Smart Chain\n"
    "• <b>Polygon (USDT)</b> — Polygon Network\n"
    "• <b>TRC20 (USDT)</b> — Tron Network\n"
    "• ⭐ <b>Telegram Stars</b>\n"
    "• 🇵🇭 <b>GCash</b> — Philippines\n\n"
    "<blockquote>🔗 <b>Binance is supported</b></blockquote>\n"
    "<i>When withdrawing from Binance, make sure to select the <b>exact same network</b> shown here.</i>\n\n"
    "<b>Examples:</b>\n"
    "• TRC20 → Tron (TRC20)\n"
    "• BEP20 → BNB Smart Chain (BEP20)\n"
    "• Polygon → Polygon\n"
    "• Gcash → Gcash\n\n"
    "<blockquote>🚨 <b>How to send from Binance:</b>\n"
    "1️⃣ Open Binance → <b>Wallets</b> → <b>Withdraw</b>\n"
    "2️⃣ Select <b>USDT</b>\n"
    "3️⃣ Paste the <b>wallet address provided</b>\n"
    "4️⃣ Choose the <b>matching network</b>\n"
    "5️⃣ Enter the amount and confirm the withdrawal</blockquote>\n\n"
    "<blockquote>✅ <i><b>It is Auto Pay, your order is completed within a few minutes.</b></i></blockquote>\n\n"
    "⚠️ <tg-spoiler><b>Sending through the wrong network may result in loss of funds.</b></tg-spoiler>"
)

BINANCE_PAY_INFO = (
    "💳 <b>Choose your preferred payment method:</b>\n\n"
    "• <code>BEP20 (USDT)</code> — BNB Smart Chain\n"
    "• <code>Polygon (USDT)</code> — Polygon Network\n"
    "• <code>TRC20 (USDT)</code> — Tron Network\n"
    "• ⭐ <code>Telegram Stars</code>\n\n"
    "🔗 <b>Binance is supported</b>\n\n"
    "When withdrawing from Binance, make sure to select the <b>exact same network</b> shown here.\n\n"
    "<b>Examples:</b>\n"
    "• <code>TRC20</code> → Tron (TRC20)\n"
    "• <code>BEP20</code> → BNB Smart Chain (BEP20)\n"
    "• <code>Polygon</code> → Polygon\n\n"
    "🚨 <b>How to send from Binance:</b>\n"
    "1️⃣ Open Binance → Wallets → Withdraw\n"
    "2️⃣ Select USDT\n"
    "3️⃣ Paste the wallet address provided\n"
    "4️⃣ Choose the <b>matching network</b>\n"
    "5️⃣ Enter the amount and confirm\n\n"
    "✅ <b>It is Auto Pay</b> — your order is completed within a few minutes.\n\n"
    "⚠️ <b>Warning:</b> Sending through the wrong network may result in loss of funds."
)

POLYGON_INFO = (
    "🔗 <b>Polygon (USDT)</b>\n\n"
    "<b>Network:</b> Polygon Network\n\n"
    "<b>How to send:</b>\n"
    "1️⃣ Open your wallet\n"
    "2️⃣ Select Polygon Network\n"
    "3️⃣ Paste the wallet address provided\n"
    "4️⃣ Enter the amount\n"
    "5️⃣ Confirm and send\n\n"
    "✅ <b>Auto Pay:</b> Your order is completed within a few minutes."
)

TRC20_INFO = (
    "🔗 <b>TRC20 (USDT)</b>\n\n"
    "<b>Network:</b> Tron Network\n\n"
    "<b>How to send:</b>\n"
    "1️⃣ Open your wallet\n"
    "2️⃣ Select Tron Network\n"
    "3️⃣ Paste the wallet address provided\n"
    "4️⃣ Enter the amount\n"
    "5️⃣ Confirm and send\n\n"
    "✅ <b>Auto Pay:</b> Your order is completed within a few minutes."
)

TELEGRAM_STARS_INFO = (
    "We would like to inform you that if you are unable to make a payment via Binance, you can complete the payment using Telegram Stars.\n\n"
    "📌 <b>Payment Method:</b>\n"
    "You can send Stars as a gift to the following username:\n"
    "@caydigitals\n\n"
    "💰 <b>Available Packages:</b>\n\n"
    "- 300 Stars = $3\n"
    "- 500 Stars = $6\n"
    "- 1200 Stars = $16\n\n"
    "📩 After completing the payment, you will receive a Redeem Code in the same chat from the support team.\n\n"
    "Thank you for your cooperation 🌟"
)

MENU_BUTTONS = {
    "🛒 Products", "👤 Profile", "🎁 Invite Center",
    "💰 Top up balance", "🎫 Redeem Code", "📋 Bot Policy", "❓ Help",
}

CATEGORY_EMOJIS = [
    "🤖", "💻", "📱", "🎮", "🎬", "🎵",
    "📚", "🌐", "🎨", "🔧", "💡", "🎁",
    "🌟", "🔥", "💎", "🚀", "👑", "🏆",
    "💰", "⚡", "🛒", "🎯", "🛡", "📦",
]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def build_emoji_picker() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(CATEGORY_EMOJIS), 6):
        rows.append([
            InlineKeyboardButton(e, callback_data=f"emoji_{i + j}")
            for j, e in enumerate(CATEGORY_EMOJIS[i:i + 6])
        ])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel_flow")])
    return InlineKeyboardMarkup(rows)


def get_emoji_by_index(index: int) -> str:
    if 0 <= index < len(CATEGORY_EMOJIS):
        return CATEGORY_EMOJIS[index]
    return "📦"


def build_payment_methods_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Binance Pay", callback_data="payment_binance")],
        [InlineKeyboardButton("🔗 Polygon (USDT)", callback_data="payment_polygon")],
        [InlineKeyboardButton("🔗 TRC20 (USDT)", callback_data="payment_trc20")],
        [InlineKeyboardButton("⭐ Telegram Stars", callback_data="payment_stars")],
        [InlineKeyboardButton("🇵🇭 GCash", callback_data="payment_gcash")],
        [InlineKeyboardButton("✕ Close", callback_data="close")],
    ])  

# ─── USER-FACING KEYBOARDS ───────────────────────────────────────────────────

async def build_products_keyboard() -> InlineKeyboardMarkup:
    categories = await db.get_categories()
    rows = [[InlineKeyboardButton("✅ Official Subscriptions", callback_data="noop")]]
    pairs = []
    for cat in categories:
        pairs.append(InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_{cat['id']}"
        ))
    for i in range(0, len(pairs), 2):
        rows.append(pairs[i:i + 2])
    rows.append([InlineKeyboardButton("🟢 What's Available", callback_data="whats_available")])
    rows.append([InlineKeyboardButton("✕ Close", callback_data="close")])
    return InlineKeyboardMarkup(rows)


def build_profile_text(tg_user, db_user: dict) -> str:
    full_name = tg_user.full_name if tg_user else "Unknown"
    user_id = tg_user.id if tg_user else "N/A"
    balance = db_user.get("balance", 0.0) if db_user else 0.0
    total_purchases = db_user.get("total_purchases", 0) if db_user else 0
    total_spent = db_user.get("total_spent", 0.0) if db_user else 0.0
    joined_at = db_user.get("joined_at") if db_user else None
    if joined_at:
        try:
            dt = datetime.fromisoformat(joined_at.replace("Z", "+00:00"))
            reg_date = dt.strftime("%m/%d/%Y, %H:%M")
        except Exception:
            reg_date = joined_at[:16]
    else:
        reg_date = datetime.now().strftime("%m/%d/%Y, %H:%M")
    return (
        f"👤 <b>Profile</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"💰 <b>Balance:</b> ${balance:.2f}\n"
        f"⭐ <b>Level:</b> Newbie (1)\n"
        f"🏷️ <b>Product discount:</b> 0%\n"
        f"🛒 <b>Total purchases:</b> {total_purchases}\n"
        f"💸 <b>Spent (net):</b> ${total_spent:.2f}\n"
        f"🤝 <b>Reseller discount:</b> ❌\n"
        f"📅 <b>Registration date:</b> {reg_date}"
    )


PROFILE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🏅 My Status", callback_data="profile_status"),
        InlineKeyboardButton("📋 My Orders", callback_data="profile_orders"),
    ],
    [
        InlineKeyboardButton("💸 Withdraw", callback_data="profile_withdraw"),
        InlineKeyboardButton("👛 Wallet statement", callback_data="profile_wallet"),
    ],
    [
        InlineKeyboardButton("📝 Withdraw requests", callback_data="profile_withdraw_req"),
        InlineKeyboardButton("📄 Withdraw profile", callback_data="profile_withdraw_pro"),
    ],
    [InlineKeyboardButton("✕ Close", callback_data="close")],
])


# ─── ADMIN PANEL BUILDERS ────────────────────────────────────────────────────

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Manage Categories", callback_data="admin_categories")],
        [InlineKeyboardButton("📦 Manage Products", callback_data="admin_products")],
        [InlineKeyboardButton("✕ Close", callback_data="close")],
    ])


async def admin_categories_keyboard() -> InlineKeyboardMarkup:
    cats = await db.get_categories()
    rows = []
    for cat in cats:
        rows.append([
            InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"admin_cat_{cat['id']}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"admin_delcat_{cat['id']}"),
        ])
    rows.append([InlineKeyboardButton("➕ Add Category", callback_data="admin_addcat")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_main")])
    return InlineKeyboardMarkup(rows)


def admin_cat_edit_keyboard(cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Name", callback_data=f"admin_editcat_name_{cat_id}")],
        [InlineKeyboardButton("🎨 Change Emoji", callback_data=f"admin_editcat_emoji_{cat_id}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_categories")],
    ])


async def admin_products_pick_cat_keyboard() -> InlineKeyboardMarkup:
    cats = await db.get_categories()
    rows = []
    for cat in cats:
        rows.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"admin_prodcat_{cat['id']}"
        )])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_main")])
    return InlineKeyboardMarkup(rows)

async def admin_products_keyboard(cat_id: int):
    products = await db.get_products(cat_id)
    cat = await db.get_category(cat_id)
    rows = []
    for p in products:
        stock_icon = "✅" if p["stock"] > 0 else "❌"
        rows.append([
            InlineKeyboardButton(
                f"{stock_icon} #{p['id']} {p['name']} (${p['price']:.2f}, {p['stock']}x)",
                callback_data=f"admin_prod_{p['id']}"
            ),
        ])
    rows.append([InlineKeyboardButton("➕ Add Product", callback_data=f"admin_addprod_{cat_id}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_products")])
    cat_name = f"{cat['emoji']} {cat['name']}" if cat else "Category"
    return InlineKeyboardMarkup(rows), cat_name

def build_admin_prod_detail_text(prod: dict) -> str:
    stock_icon = "✅" if prod["stock"] > 0 else "❌"
    demo = prod.get("demo_url") or "—"
    desc = (prod.get("description") or "—").strip()
    return (
        f"📦 <b>#{prod['id']} {prod['name']}</b>\n\n"
        f"💲 <b>Price:</b> ${prod['price']:.2f}\n"
        f"📦 <b>Stock:</b> {stock_icon} {prod['stock']}x\n"
        f"⏳ <b>Duration:</b> {prod.get('duration') or '—'}\n"
        f"🛡 <b>Warranty:</b> {prod.get('warranty') or 'No warranty'}\n"
        f"📬 <b>Delivery:</b> {prod.get('delivery') or 'LINK'}\n"
        f"🎮 <b>Demo URL:</b> {demo}\n\n"
        f"📝 <b>Description:</b>\n{desc}"
    )

def admin_prod_edit_keyboard(prod_id: int, cat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Name",        callback_data=f"admin_editprod_name_{prod_id}"),
            InlineKeyboardButton("💲 Price",        callback_data=f"admin_editprod_price_{prod_id}"),
        ],
        [
            InlineKeyboardButton("📝 Description",  callback_data=f"admin_editprod_desc_{prod_id}"),
            InlineKeyboardButton("📦 Stock",        callback_data=f"admin_editprod_stock_{prod_id}"),
        ],
        [
            InlineKeyboardButton("⏳ Duration",     callback_data=f"admin_editprod_duration_{prod_id}"),
            InlineKeyboardButton("🛡 Warranty",     callback_data=f"admin_editprod_warranty_{prod_id}"),
        ],
        [
            InlineKeyboardButton("📬 Delivery",     callback_data=f"admin_editprod_delivery_{prod_id}"),
            InlineKeyboardButton("🎮 Demo URL",     callback_data=f"admin_editprod_demo_{prod_id}"),
        ],
        [InlineKeyboardButton("🗑 Delete Product",  callback_data=f"admin_delprod_{prod_id}")],
        [InlineKeyboardButton("⬅️ Back",            callback_data=f"admin_prodcat_{cat_id}")],
    ])

# ─── USER COMMAND HANDLERS ───────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    await db.get_or_create_user(
        user_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )

    # Clear any stale GCash deposit flow if user runs /start mid-flow
    ud = await db.get_session(tg_user.id)
    if ud.get("awaiting") == "gcash_amount" or ud.get("gcash_pending"):
        ud.pop("awaiting", None)
        ud.pop("gcash_pending", None)
        await db.set_session(tg_user.id, ud)
    await update.message.reply_text(
        "<blockquote><b>👋 Welcome to CayShop Bot!</b></blockquote>\nI'm here to help you purchase subscriptions and digital services easily and securely.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU,
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 أهلاً بك في ToolAI Bot\nالرجاء اختيار لغتك المفضلة / Please select your preferred language:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🇸🇦 Arabic عربي", callback_data="lang_ar"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            ]
        ]),
    )


async def contactadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✕ Close", callback_data="close")]
        ]),
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return
    await update.message.reply_text(
        "🔧 <b>Admin Panel</b>\n\nManage your bot's categories and products below:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard(),
    )


# ─── COMBINED MESSAGE HANDLER ─────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    # ── GCash amount entry (any user, not just admins) ──
    ud = await db.get_session(user_id)
    if ud.get("awaiting") == "gcash_amount":
        result = await gcash_topup.handle_gcash_amount_input(update, context, ud)
        if result != "fallthrough":
            return
        # else: fall through below so the menu button still does its thing

    if is_admin(user_id) and text not in MENU_BUTTONS:
        ud = await db.get_session(user_id)
        if ud.get("awaiting"):
            await _process_admin_input(update, user_id, ud)
            return

    if text == "🛒 Products":
        kb = await build_products_keyboard()
        await update.message.reply_text("<b>Choose a service:</b>", parse_mode="HTML", reply_markup=kb)

    elif text == "👤 Profile":
        db_user = await db.get_user(update.effective_user.id)
        await update.message.reply_text(
            build_profile_text(update.effective_user, db_user),
            parse_mode="HTML",
            reply_markup=PROFILE_KEYBOARD,
        )

    elif text == "🎁 Invite Center":
        await update.message.reply_text(
            "🎁 <b>Invite Center</b>\n\nShare your referral link and earn rewards!",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

    elif text == "💰 Top up balance":
            await update.message.reply_text(
                PAYMENT_METHODS_TEXT,
                parse_mode="HTML",
                reply_markup=build_payment_methods_keyboard(),
            )

    elif text == "🎫 Redeem Code":
        await update.message.reply_text(
            "Please send your redeem code:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Request Redeem Code", url="https://t.me/caydigitals")],
                [InlineKeyboardButton("✕ Close", callback_data="close")],
            ]),
        )

    elif text == "📋 Bot Policy":
        await update.message.reply_text(
            BOT_POLICY,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✕ Close", callback_data="close")]
            ]),
        )

    elif text == "❓ Help":
        await update.message.reply_text(
            HELP_TEXT,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✕ Close", callback_data="close")]
            ]),
        )

    else:
        await update.message.reply_text(
            "Please choose an option from the menu below:",
            reply_markup=MAIN_MENU,
        )


# ─── ADMIN TEXT INPUT LOGIC ──────────────────────────────────────────────────

async def _process_admin_input(update: Update, user_id: int, ud: dict) -> None:
    """
    Process admin text input. `ud` is the session dict loaded from Supabase.
    Each branch must call db.set_session / db.clear_session after mutating `ud`.
    """
    awaiting = ud.get("awaiting")
    text = update.message.text.strip() if update.message.text else ""

    if awaiting == "cat_name":
        ud["new_cat_name"] = text
        ud["awaiting"] = "cat_emoji"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            f"📂 Category name set to: <b>{text}</b>\n\nNow pick an emoji for it:",
            parse_mode="HTML",
            reply_markup=build_emoji_picker(),
        )

    elif awaiting == "edit_cat_name":
        cat_id = ud.pop("edit_cat_id", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        if not cat_id:
            await update.message.reply_text("❌ Session expired. Please open the category again.")
            return
        try:
            await db.update_category(cat_id, name=text)
        except Exception as e:
            logger.error(f"Failed to update category name: {e}", exc_info=e)
            await update.message.reply_text("❌ Failed to update name. Please try again.")
            return
        cat = await db.get_category(cat_id)
        label = f"{cat['emoji']} {cat['name']}" if cat else text
        await update.message.reply_text(
            f"✅ Category renamed to <b>{label}</b>!",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

    elif awaiting == "prod_name":
        ud["new_prod_name"] = text
        ud["awaiting"] = "prod_desc"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter a <b>description</b> for this product:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_desc":
        ud["new_prod_desc"] = text
        ud["awaiting"] = "prod_price"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter the <b>price</b> (e.g. 4.99):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_price":
        try:
            price = float(text)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid price. Please enter a number like 4.99:",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        ud["new_prod_price"] = price
        ud["awaiting"] = "prod_stock"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter the <b>stock quantity</b> (e.g. 10):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_stock":
        try:
            stock = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid quantity. Enter a whole number:")
            return
        ud["new_prod_stock"] = stock
        ud["awaiting"] = "prod_duration"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter the <b>duration</b> (e.g. <code>540 days</code>, <code>1 Year</code>). Send <code>-</code> to skip:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_duration":
        ud["new_prod_duration"] = "" if text.strip() == "-" else text.strip()
        ud["awaiting"] = "prod_warranty"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter the <b>warranty</b> (e.g. <code>No warranty</code>, <code>30 days</code>):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_warranty":
        ud["new_prod_warranty"] = text.strip()
        ud["awaiting"] = "prod_delivery"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter the <b>delivery type</b> (e.g. <code>LINK</code>, <code>ACCOUNT</code>, <code>FILE</code>):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_delivery":
        ud["new_prod_delivery"] = text.strip()
        ud["awaiting"] = "prod_demo_url"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            "Enter a <b>demo URL</b> for users to try the product (e.g. <code>https://t.me/yourbot?start=demo</code>).\n\nSend <code>-</code> to skip:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    elif awaiting == "prod_demo_url":
        cat_id   = ud.pop("new_prod_cat_id", None)
        name     = ud.pop("new_prod_name", None)
        desc     = ud.pop("new_prod_desc", None)
        price    = ud.pop("new_prod_price", None)
        stock    = ud.pop("new_prod_stock", None)
        duration = ud.pop("new_prod_duration", "")
        warranty = ud.pop("new_prod_warranty", "No warranty")
        delivery = ud.pop("new_prod_delivery", "LINK")
        demo_url = "" if text.strip() == "-" else text.strip()
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        await db.add_product(cat_id, name, desc, price, stock, duration, warranty, delivery, demo_url)
        cat = await db.get_category(cat_id)
        cat_name = f"{cat['emoji']} {cat['name']}" if cat else "category"
        await update.message.reply_text(
            f"✅ Product <b>{name}</b> added to <b>{cat_name}</b>!\n"
            f"💲 ${price:.2f} | 📦 {stock}x in stock | 📬 {delivery}",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

    elif awaiting in ("prod_edit_name", "prod_edit_price", "prod_edit_desc",
                      "prod_edit_stock", "prod_edit_duration", "prod_edit_warranty",
                      "prod_edit_delivery", "prod_edit_demo"):
        prod_id = ud.pop("edit_prod_id", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        if not prod_id:
            await update.message.reply_text("❌ Session expired. Please open the product again.")
            return
        val = text.strip()
        field_db_map = {
            "prod_edit_name":     ("name",        lambda v: v),
            "prod_edit_price":    ("price",       float),
            "prod_edit_desc":     ("description", lambda v: v),
            "prod_edit_stock":    ("stock",       int),
            "prod_edit_duration": ("duration",    lambda v: "" if v == "-" else v),
            "prod_edit_warranty": ("warranty",    lambda v: v),
            "prod_edit_delivery": ("delivery",    lambda v: v),
            "prod_edit_demo":     ("demo_url",    lambda v: "" if v == "-" else v),
        }
        db_field, converter = field_db_map[awaiting]
        try:
            converted = converter(val)
        except (ValueError, TypeError):
            await update.message.reply_text(f"❌ Invalid value. Please try again.")
            return
        try:
            await db.update_product(prod_id, **{db_field: converted})
        except Exception as e:
            logger.error(f"Failed to update product field {db_field}: {e}", exc_info=e)
            await update.message.reply_text("❌ Failed to save. Please try again.")
            return
        prod = await db.get_product(prod_id)
        await update.message.reply_text(
            f"✅ Updated! Here's the product:\n\n{build_admin_prod_detail_text(prod)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit more", callback_data=f"admin_prod_{prod_id}")],
                [InlineKeyboardButton("⬅️ Back to list", callback_data=f"admin_prodcat_{prod['category_id']}")],
            ]),
        )

    elif awaiting == "stock":
        try:
            stock = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid quantity. Enter a whole number:")
            return
        prod_id = ud.pop("stock_prod_id", None)
        ud.pop("stock_cat_id", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        prod = await db.get_product(prod_id)
        await db.update_product_stock(prod_id, stock)
        await update.message.reply_text(
            f"✅ Stock for <b>{prod['name']}</b> updated to <b>{stock}x</b>.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

# ─── MAIN CALLBACK HANDLER ───────────────────────────────────────────────────
# FIX: Do NOT call query.answer() at the top. Each branch answers the query
# exactly once. Calling it twice causes a silent Telegram error, resulting in
# "no response" for the user.

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # ── General ──
    if data == "close":
        await query.answer()
        await query.message.delete()
        return

    if data == "noop":
        await query.answer()
        return

    # ── Cancel admin flow ──
    if data == "admin_cancel_flow":
        await db.clear_session(user_id)
        await query.answer("Cancelled.")
        await query.message.delete()
        await query.message.reply_text("❌ Cancelled.", reply_markup=MAIN_MENU)
        return

    # ── Crypto/Stars top-up — admin only for now. GCash stays open to all users. ──
    if data in ("payment_binance", "payment_polygon", "payment_trc20"):
        if not is_admin(user_id):
            await query.answer("🚧 This payment method is currently unavailable.", show_alert=True)
            return

    if data == "payment_gcash":
        await gcash_topup.start_gcash_topup(update, context)
        return

    if data == "gcash_paid":
        await gcash_topup.handle_gcash_paid(update, context)
        return

    if data == "gcash_cancel":
        await gcash_topup.handle_gcash_cancel(update, context)
        return

    # ── Payment Methods ──
    if data == "payment_binance":
        await query.answer()
        await query.message.edit_text(
            BINANCE_PAY_INFO,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
            ]),
        )
        return

    if data == "payment_polygon":
        await query.answer()
        await query.message.edit_text(
            POLYGON_INFO,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
            ]),
        )
        return

    if data == "payment_trc20":
        await query.answer()
        await query.message.edit_text(
            TRC20_INFO,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
            ]),
        )
        return

    if data == "payment_stars":
        await query.answer()
        await query.message.edit_text(
            TELEGRAM_STARS_INFO,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Send as Gift", url="https://t.me/caydigitals")],
                [InlineKeyboardButton("⬅️ Back", callback_data="payment_back")],
            ]),
        )
        return

    if data == "payment_back":
        await query.answer()
        await query.message.edit_text(
            PAYMENT_METHODS_TEXT,
            parse_mode="HTML",
            reply_markup=build_payment_methods_keyboard(),
        )
        return

    # ── Emoji picker (category creation OR emoji edit) ──
    # Emojis are stored by index to avoid multi-byte callback_data issues.
    if data.startswith("emoji_"):
        if not is_admin(user_id):
            await query.answer("⛔ Admins only.", show_alert=True)
            return
        try:
            index = int(data[len("emoji_"):])
            emoji = get_emoji_by_index(index)
        except (ValueError, IndexError):
            await query.answer("Invalid emoji selection.", show_alert=True)
            return

        ud = await db.get_session(user_id)

        # ── Edit mode: changing emoji on an existing category ──
        edit_cat_id = ud.get("edit_cat_id")
        if edit_cat_id:
            try:
                await db.update_category(edit_cat_id, emoji=emoji)
            except Exception as e:
                logger.error(f"Failed to update category emoji: {e}", exc_info=e)
                await query.answer("❌ Failed to update emoji. Please try again.", show_alert=True)
                return
            ud.pop("edit_cat_id", None)
            ud.pop("awaiting", None)
            await db.set_session(user_id, ud)
            cat = await db.get_category(edit_cat_id)
            label = f"{cat['emoji']} {cat['name']}" if cat else f"{emoji} category"
            kb = await admin_categories_keyboard()
            await query.answer(f"✅ Emoji updated!")
            await query.message.edit_text(
                f"✅ Emoji updated — <b>{label}</b>\n\n📂 <b>Categories</b>:",
                parse_mode="HTML",
                reply_markup=kb,
            )
            return

        # ── Create mode: picking emoji for a new category ──
        # Use get() first — only pop() after the DB call succeeds so retries
        # still have the name available if something goes wrong.
        name = ud.get("new_cat_name")

        if not name:
            await query.answer("Session expired — please start /admin again.", show_alert=True)
            await query.message.delete()
            return

        try:
            await db.add_category(name, emoji)
        except Exception as e:
            logger.error(f"Failed to add category: {e}", exc_info=e)
            await query.answer("❌ Failed to save category. Please try again.", show_alert=True)
            return

        # Success — now clear the state
        ud.pop("new_cat_name", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)

        kb = await admin_categories_keyboard()
        await query.answer(f"✅ Category '{emoji} {name}' added!")
        await query.message.edit_text(
            f"✅ Category <b>{emoji} {name}</b> added!\n\n📂 <b>Categories</b>:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # ── Language ──
    if data == "lang_ar":
        await query.answer()
        await query.message.edit_text(
            "✅ تم اختيار اللغة العربية\n\nاللغة العربية غير متاحة حالياً، سيتم إضافتها قريباً."
        )
        return

    if data == "lang_en":
        await query.answer()
        await query.message.edit_text(
            "✅ English language selected.\n\nYou are now using the bot in English."
        )
        return

    # ── Profile ──
    if data in ("profile_status", "profile_orders", "profile_withdraw",
                "profile_wallet", "profile_withdraw_req", "profile_withdraw_pro"):
        labels = {
            "profile_status": "🏅 My Status",
            "profile_orders": "📋 My Orders",
            "profile_withdraw": "💸 Withdraw",
            "profile_wallet": "👛 Wallet statement",
            "profile_withdraw_req": "📝 Withdraw requests",
            "profile_withdraw_pro": "📄 Withdraw profile",
        }
        await query.answer(f"{labels[data]} — coming soon", show_alert=True)
        return

    # ── Products (user) ──
    if data == "whats_available":
        text = await db.get_all_products_availability()
        await query.answer()
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_products")]
            ]),
        )
        return

    if data == "back_to_products":
        kb = await build_products_keyboard()
        await query.answer()
        await query.message.edit_text("<b>Choose a service:</b>", parse_mode="HTML", reply_markup=kb)
        return

    NUM_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

    if data.startswith("cat_"):
        cat_id = int(data.split("_")[1])
        cat = await db.get_category(cat_id)
        products = await db.get_products(cat_id)
        cat_emoji = cat["emoji"] if cat else "📦"
        cat_name  = cat["name"]  if cat else "Category"
        if not products:
            await query.answer()
            await query.message.edit_text(
                f"{cat_emoji} <b>{cat_name}</b>\n\n🚫 No products available in this category yet.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Services", callback_data="back_to_products")]
                ]),
            )
            return
        product_buttons = [
            [InlineKeyboardButton(f"{cat_emoji} {p['name']}", callback_data=f"user_prod_{p['id']}")]
            for p in products
        ]
        product_buttons.append([InlineKeyboardButton("⬅️ Services", callback_data="back_to_products")])
        await query.answer()
        await query.message.edit_text(
            f"{cat_emoji} Choose your <b>{cat_name}</b> plan:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(product_buttons),
        )
        return

    # ── User product detail ──
    if data.startswith("user_prod_"):
        prod_id = int(data.split("_")[2])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        cat = await db.get_category(prod["category_id"])
        cat_emoji = cat["emoji"] if cat else "📦"
        price    = prod["price"]
        duration = prod.get("duration") or "—"
        warranty = prod.get("warranty") or "No warranty"
        delivery = prod.get("delivery") or "LINK"
        desc     = (prod.get("description") or "").strip()
        text = (
            f"📦 <b>{prod['name']}</b>\n\n"
            f"💰 {price:.2f} USD\n"
            f"⏳ Duration: {duration}\n"
            f"🛡 Warranty: {warranty}\n"
            f"📦 Delivery: {delivery}\n"
        )
        if desc:
            text += f"\n{desc}\n"
        await query.answer()
        # Build the button row — Demo beside Buy only when a URL exists
        demo_url = (prod.get("demo_url") or "").strip()
        action_row = []
        if demo_url:
            action_row.append(InlineKeyboardButton("🎮 Demo", url=demo_url))
        if prod["stock"] > 0:
            action_row.append(InlineKeyboardButton("🚀 Buy", callback_data=f"buy_{prod_id}"))
        else:
            action_row.append(InlineKeyboardButton("❌ Out of Stock", callback_data="noop"))

        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                action_row,
                [InlineKeyboardButton("⬅️ Back to plans", callback_data=f"cat_{prod['category_id']}")],
            ]),
        )
        return

    # ── Buy flow ──
    if data.startswith("buy_"):
        prod_id = int(data.split("_")[1])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        if prod["stock"] <= 0:
            await query.answer("❌ This product is out of stock.", show_alert=True)
            return
        db_user = await db.get_user(user_id)
        balance = float(db_user.get("balance", 0)) if db_user else 0.0
        price = prod["price"]
        if balance < price:
            await query.answer()
            await query.message.edit_text(
                f"❌ <b>Insufficient balance.</b>\n\n"
                f"Required: {price:.2f} USD\n"
                f"Your balance: {balance:.2f} USD",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data=f"user_prod_{prod_id}")],
                ]),
            )
            return
        # TODO: deduct balance and deliver product
        await query.answer("✅ Purchase processing — coming soon!", show_alert=True)
        return

    # ── ADMIN PANEL ──────────────────────────────────────────────────────────
    if not is_admin(user_id):
        await query.answer("⛔ Admins only.", show_alert=True)
        return

    if data == "admin_main":
        await query.answer()
        await query.message.edit_text(
            "🔧 <b>Admin Panel</b>\n\nManage your bot's categories and products below:",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard(),
        )
        return

    if data == "admin_categories":
        kb = await admin_categories_keyboard()
        await query.answer()
        await query.message.edit_text(
            "📂 <b>Categories</b>\n\nAdd, view or delete categories:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    # ── Product detail page ──
    if data.startswith("admin_prod_"):
        prod_id = int(data.split("_")[2])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        await query.answer()
        await query.message.edit_text(
            build_admin_prod_detail_text(prod),
            parse_mode="HTML",
            reply_markup=admin_prod_edit_keyboard(prod_id, prod["category_id"]),
        )
        return

    # ── Edit individual product field ──
    if data.startswith("admin_editprod_"):
        parts = data.split("_")        # ["admin", "editprod", field, prod_id]
        field = parts[2]
        prod_id = int(parts[3])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        field_map = {
            "name":     ("prod_edit_name",     "✏️ Enter a new <b>name</b>:"),
            "price":    ("prod_edit_price",    "💲 Enter a new <b>price</b> (e.g. <code>9.99</code>):"),
            "desc":     ("prod_edit_desc",     "📝 Enter a new <b>description</b>:"),
            "stock":    ("prod_edit_stock",    "📦 Enter new <b>stock quantity</b>:"),
            "duration": ("prod_edit_duration", "⏳ Enter a new <b>duration</b> (e.g. <code>30 days</code>). Send <code>-</code> to clear:"),
            "warranty": ("prod_edit_warranty", "🛡 Enter a new <b>warranty</b>:"),
            "delivery": ("prod_edit_delivery", "📬 Enter a new <b>delivery type</b> (e.g. <code>LINK</code>, <code>ACCOUNT</code>):"),
            "demo":     ("prod_edit_demo",     "🎮 Enter a new <b>demo URL</b>. Send <code>-</code> to clear:"),
        }
        if field not in field_map:
            await query.answer()
            return
        awaiting_key, prompt = field_map[field]
        db_field = {"desc": "description", "demo": "demo_url"}.get(field, field)
        current_val = str(prod.get(db_field) or "—")
        await db.set_session(user_id, {"awaiting": awaiting_key, "edit_prod_id": prod_id})
        await query.answer()
        await query.message.reply_text(
            f"{prompt}\n\n<i>Current: {current_val}</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data == "admin_products":
        cats = await db.get_categories()
        if not cats:
            await query.answer("No categories yet. Add a category first.", show_alert=True)
            return
        kb = await admin_products_pick_cat_keyboard()
        await query.answer()
        await query.message.edit_text(
            "📦 <b>Products</b>\n\nSelect a category to manage its products:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("admin_prodcat_"):
        cat_id = int(data.split("_")[2])
        kb, cat_name = await admin_products_keyboard(cat_id)
        await query.answer()
        await query.message.edit_text(
            f"📦 <b>Products — {cat_name}</b>\n\nManage products below:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("admin_cat_") and not data.startswith("admin_categories"):
        cat_id = int(data.split("_")[2])
        cat = await db.get_category(cat_id)
        if not cat:
            await query.answer("Category not found.", show_alert=True)
            return
        await query.answer()
        await query.message.edit_text(
            f"✏️ <b>Edit Category</b>\n\n"
            f"Current: <b>{cat['emoji']} {cat['name']}</b>\n\n"
            f"What would you like to change?",
            parse_mode="HTML",
            reply_markup=admin_cat_edit_keyboard(cat_id),
        )
        return

    if data.startswith("admin_editcat_name_"):
        cat_id = int(data.split("_")[3])
        cat = await db.get_category(cat_id)
        await db.set_session(user_id, {"awaiting": "edit_cat_name", "edit_cat_id": cat_id})
        await query.answer()
        await query.message.reply_text(
            f"✏️ Enter a new name for <b>{cat['emoji']} {cat['name']}</b>:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data.startswith("admin_editcat_emoji_"):
        cat_id = int(data.split("_")[3])
        cat = await db.get_category(cat_id)
        await db.set_session(user_id, {"edit_cat_id": cat_id})
        await query.answer()
        await query.message.reply_text(
            f"🎨 Pick a new emoji for <b>{cat['emoji']} {cat['name']}</b>:",
            parse_mode="HTML",
            reply_markup=build_emoji_picker(),
        )
        return

    if data.startswith("admin_delcat_"):
        cat_id = int(data.split("_")[2])
        cat = await db.get_category(cat_id)
        if cat:
            await db.delete_category(cat_id)
        kb = await admin_categories_keyboard()
        await query.answer("✅ Category deleted.")
        await query.message.edit_text(
            "✅ Category deleted.\n\n📂 <b>Categories</b>:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data.startswith("admin_delprod_"):
        prod_id = int(data.split("_")[2])
        prod = await db.get_product(prod_id)
        if prod:
            cat_id = prod["category_id"]
            await db.delete_product(prod_id)
            kb, cat_name = await admin_products_keyboard(cat_id)
            await query.answer("✅ Product deleted.")
            await query.message.edit_text(
                f"✅ Product deleted.\n\n📦 <b>Products — {cat_name}</b>:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await query.answer("Product not found.", show_alert=True)
        return

    if data == "admin_addcat":
        await db.set_session(user_id, {"awaiting": "cat_name"})
        await query.answer()
        await query.message.reply_text(
            "📂 Enter the <b>category name</b>:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data.startswith("admin_addprod_"):
        cat_id = int(data.split("_")[2])
        await db.set_session(user_id, {"awaiting": "prod_name", "new_prod_cat_id": cat_id})
        await query.answer()
        await query.message.reply_text(
            "📦 Enter the <b>product name</b>:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data.startswith("admin_approve_gcash_"):
        parts = data.split("_")
        # format: admin_approve_gcash_{user_id}_{amount}
        target_user_id = int(parts[3])
        amount = float(parts[4])
        await db.credit_balance(target_user_id, amount)  # wire to your existing credit function
        await query.answer("✅ Balance credited!", show_alert=True)
        try:
            await query.message.edit_text(
                query.message.text + "\n\n✅ <b>APPROVED</b> — balance credited.",
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"✅ <b>Deposit confirmed!</b>\n\n₱{amount:.2f} has been credited to your balance.",
            parse_mode="HTML",
        )
        return

    if data.startswith("admin_reject_gcash_"):
        target_user_id = int(data.split("_")[3])
        await query.answer("❌ Claim rejected.", show_alert=True)
        try:
            await query.message.edit_text(
                query.message.text + "\n\n❌ <b>REJECTED</b> — no balance credited.",
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=target_user_id,
            text="❌ <b>Deposit not verified.</b>\n\nWe could not verify your GCash payment. Please contact support if you believe this is an error.",
            parse_mode="HTML",
        )
        return

    # Unhandled callback
    await query.answer()


# ─── ERROR HANDLER ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning("Conflict error — another bot instance may still be shutting down.")
    elif isinstance(context.error, NetworkError):
        logger.warning(f"Network error: {context.error}")
    else:
        logger.error(f"Unhandled error: {context.error}", exc_info=context.error)


# ─── STARTUP ─────────────────────────────────────────────────────────────────

async def post_init(application: Application) -> None:
    await application.bot.delete_webhook(drop_pending_updates=True)
    for attempt in range(20):
        try:
            await application.bot.get_updates(offset=-1, timeout=1)
            break
        except Conflict:
            wait = min(3 * (attempt + 1), 15)
            logger.warning(f"409 Conflict on startup — waiting {wait}s… (attempt {attempt + 1}/20)")
            await asyncio.sleep(wait)
        except Exception:
            break
    logger.info(f"Bot ready — admins: {ADMIN_IDS}")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    persistence = PicklePersistence(filepath="bot_data.pkl")
    app = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("contactadmin", contactadmin_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()