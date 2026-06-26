import os
import asyncio
import official_subscriptions
import membership_gate
import invite_center
import lang
import logging
import ban_manager
import pending_gcash
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

CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004441073113")  # e.g. "@yourchannel" or "-1001234567890"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🛒 Products")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🎁 Invite Center")],
        [KeyboardButton("💰 Top up balance"), KeyboardButton("🎫 Redeem Code")],
        [KeyboardButton("📋 Bot Policy"), KeyboardButton("❓ Help")],
    ],
    resize_keyboard=True,
)

DEFAULT_BOT_POLICY = (
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

POLICY_SETTING_KEY = "bot_policy"
_policy_cache: dict[str, str] = {}

async def get_bot_policy() -> str:
    saved = await db.get_setting(POLICY_SETTING_KEY)
    return saved if saved else DEFAULT_BOT_POLICY

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

def mask_user_id(user_id: int) -> str:
    s = str(user_id)
    if len(s) <= 5:
        return s[:2] + "***" + s[-1:]
    return s[:3] + "***" + s[-2:]

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
        [InlineKeyboardButton("🇵🇭 GCash (PHP)", callback_data="payment_gcash")],
        [InlineKeyboardButton("✕ Close", callback_data="close")],
    ])  

# ─── USER-FACING KEYBOARDS ───────────────────────────────────────────────────

async def build_products_keyboard() -> InlineKeyboardMarkup:
    categories = await db.get_categories()
    rows = [[InlineKeyboardButton("✅ Official Subscriptions", callback_data="official_subs")]]
    pairs = []
    for cat in categories:
        if cat.get("type", "regular") == "regular":
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
        f"⭐ <b>Level:</b> {db.get_status_tier(total_spent)['name']}\n"
        f"🏷️ <b>Product discount:</b> {db.get_status_tier(total_spent)['discount']}%\n"
        f"🛒 <b>Total purchases:</b> {total_purchases}\n"
        f"💸 <b>Spent (net):</b> ${total_spent:.2f}\n"
        # f"🤝 <b>Reseller discount:</b> ❌\n"
        f"📅 <b>Registration date:</b> {reg_date}"
    )


PROFILE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🏅 My Status", callback_data="profile_status"),
        InlineKeyboardButton("📋 My Orders", callback_data="profile_orders"),
    ],
    [
        # InlineKeyboardButton("💸 Withdraw", callback_data="profile_withdraw"),
        InlineKeyboardButton("🏦 Wallet statement", callback_data="profile_wallet"),
    ],
    # [
    #     InlineKeyboardButton("📝 Withdraw requests", callback_data="profile_withdraw_req"),
    #     InlineKeyboardButton("📄 Withdraw profile", callback_data="profile_withdraw_pro"),
    # ],
    [InlineKeyboardButton("✕ Close", callback_data="close")],
])


# ─── ADMIN PANEL BUILDERS ────────────────────────────────────────────────────

def admin_main_keyboard():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 Manage Categories",    callback_data="admin_categories")],
        [InlineKeyboardButton("📦 Manage Products",      callback_data="admin_products")],
        [InlineKeyboardButton("🎫 Generate Redeem Code", callback_data="admin_gen_redeem")],
        [InlineKeyboardButton("➕ Add Balance",          callback_data="admin_add_balance")],
        [InlineKeyboardButton("⚙️ Bot Settings",         callback_data="admin_settings")],
        [InlineKeyboardButton("📋 Edit Bot Policy",       callback_data="admin_edit_policy")],
        [InlineKeyboardButton("🚫 Ban / Unban User",      callback_data="ban_start")],
        [InlineKeyboardButton("💳 Pending GCash",          callback_data="pending_gcash_list")],
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
        products = await db.get_products(cat["id"])
        total = len(products)
        in_stock = sum(1 for p in products if p["stock"] > 0)
        stock_icon = "✅" if in_stock > 0 else "❌"
        rows.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}  {stock_icon} {in_stock}/{total}",
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
    delivery_url = prod.get("delivery_url") or "—"
    desc = (prod.get("description") or "—").strip()
    return (
        f"📦 <b>#{prod['id']} {prod['name']}</b>\n\n"
        f"💲 <b>Price:</b> ${prod['price']:.2f}\n"
        f"📦 <b>Stock:</b> {stock_icon} {prod['stock']}x\n"
        f"⏳ <b>Duration:</b> {prod.get('duration') or '—'}\n"
        f"🛡 <b>Warranty:</b> {prod.get('warranty') or 'No warranty'}\n"
        f"📬 <b>Delivery:</b> {prod.get('delivery') or 'LINK'}\n"
        f"🎮 <b>Demo URL:</b> {demo}\n"
        f"🔗 <b>Delivery URL:</b> {delivery_url}\n\n"
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
        [
            InlineKeyboardButton("🔗 Delivery URL", callback_data=f"admin_editprod_deliveryurl_{prod_id}"),
        ],
        [InlineKeyboardButton("🔗 Bot Link", callback_data=f"admin_editprod_botlink_{prod_id}")],
        [InlineKeyboardButton("🗑 Delete Product",  callback_data=f"admin_delprod_{prod_id}")],
        [InlineKeyboardButton("⬅️ Back",            callback_data=f"admin_prodcat_{cat_id}")],
    ])

# ─── USER COMMAND HANDLERS ───────────────────────────────────────────────────

# NEW
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    await db.get_or_create_user(
        user_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )

    # ── Auto-update username / full_name if changed ──
    db_user = await db.get_user(tg_user.id)
    if db_user:
        updates = {}
        if db_user.get("username") != tg_user.username:
            updates["username"] = tg_user.username
        if db_user.get("full_name") != tg_user.full_name:
            updates["full_name"] = tg_user.full_name
        if updates:
            db._client().table(db.USERS_TABLE).update(updates).eq("user_id", tg_user.id).execute()
            logger.info(f"Updated profile for user {tg_user.id}: {updates}")

    # Show language picker the very first time
    if not context.user_data.get("lang"):
        await update.message.reply_text(
            "🌐 Please choose your language:",
            reply_markup=lang.LANG_PICKER_KEYBOARD,
        )
        return

    args = context.args  # python-telegram-bot populates this from
                        # "/start ref_XXXX"
    if args and args[0].startswith("ref_"):
        ref_code = args[0][len("ref_"):]
        handled = await invite_center.handle_start_with_ref(update, context, ref_code)
        if handled:
            return  # CAPTCHA prompt was sent; stop here

    if not await membership_gate.check_membership(context, tg_user.id):
        await membership_gate.send_gate_message(update, context)
        return

    # Clear any stale GCash deposit flow if user runs /start mid-flow
    ud = await db.get_session(tg_user.id)
    stale_keys = {"awaiting", "gcash_pending", "awaiting_receipt"}
    if any(k in ud for k in stale_keys):
        for k in stale_keys:
            ud.pop(k, None)
        await db.set_session(tg_user.id, ud)

    user_lang = await lang.get_lang_db(tg_user.id, context)
    welcome_text = await lang.t("welcome", user_lang)
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=lang.build_main_menu(user_lang),
    )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌐 Please choose your language:",
        reply_markup=lang.LANG_PICKER_KEYBOARD,
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
    canonical = lang.normalize_menu(text)
    user_id = update.effective_user.id

    membership_ok, is_banned, ud, user_lang = await asyncio.gather(
        membership_gate.check_membership(context, user_id),
        ban_manager.is_user_banned(user_id),
        db.get_session(user_id),
        lang.get_lang_db(user_id, context),
    )

    if not membership_ok:
        await membership_gate.send_gate_message(update, context)
        return

    if is_banned:
        await update.message.reply_text(ban_manager.BANNED_MESSAGE, parse_mode="HTML")
        return

    await invite_center.mark_interaction_and_maybe_qualify(context, user_id)

    # ── GCash amount entry (any user, not just admins) ──
    if ud.get("awaiting") == "gcash_amount":
        result = await gcash_topup.handle_gcash_amount_input(update, context, ud)
        if result != "fallthrough":
            return
        # else: fall through below so the menu button still does its thing

    # ── Custom quantity input (any user) ──
    if ud.get("awaiting") == "custom_qty":
        if canonical in lang.ALL_MENU_BUTTONS:
            await db.clear_session(user_id)
            # falls through to menu handling
        else:
            prod_id = ud.get("qty_prod_id")
            await db.clear_session(user_id)
            try:
                qty = int(text.strip())
                if qty < 1:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid whole number (e.g. 3):")
                await db.set_session(user_id, ud)   # restore session so they can retry
                return
            prod = await db.get_product(prod_id)
            if not prod or prod["stock"] < qty:
                await update.message.reply_text(
                    f"❌ Only <b>{prod['stock'] if prod else 0}</b> in stock.",
                    parse_mode="HTML",
                    reply_markup=MAIN_MENU,
                )
                return
            db_user = await db.get_user(user_id)
            balance = float(db_user.get("balance", 0)) if db_user else 0.0
            price = prod["price"]
            total = round(price * qty, 2)
            tier = db.get_status_tier(float(db_user.get("total_spent", 0)))
            discount_pct = tier["discount"]
            discounted_unit = round(price * (1 - discount_pct / 100), 2)
            discounted_total = round(discounted_unit * qty, 2)

            await update.message.reply_text(
                f"🛒 <b>Confirm Purchase</b>\n\n"
                f"📦 Product: <b>{prod['name']}</b>\n"
                f"🔢 Quantity: <b>{qty}x</b>\n"
                f"💰 Unit price: <b>${price:.2f}</b>\n"
                + (f"🏷️ Your discount: <b>{discount_pct}%</b> → <b>${discounted_unit:.2f}</b>/each\n" if discount_pct > 0 else "")
                + f"💵 Total: <b>${discounted_total:.2f}</b>\n"
                f"👛 Your balance: <b>${balance:.2f}</b>\n"
                f"💳 Balance after: <b>${round(balance - discounted_total, 2):.2f}</b>\n\n"
                f"Tap <b>Confirm</b> to complete your purchase.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_buy_{prod_id}_{qty}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"buy_{prod_id}")],
                ]),
            )
            return

    # ── GCash receipt awaiting (any user) ──
    if ud.get("awaiting_receipt"):
        await update.message.reply_text(
            "📸 Please send your GCash receipt as a <b>photo</b>, not text.",
            parse_mode="HTML",
        )
        return

    # ── Redeem code entry (any user) ──
    if ud.get("awaiting") == "redeem_code":
        if canonical in lang.ALL_MENU_BUTTONS:
            await db.clear_session(user_id)
            # falls through to menu handling below
        else:
            await db.clear_session(user_id)
            code = text.strip().upper()
            redeem = await db.get_redeem_code(code)

            if not redeem:
                await update.message.reply_text(
                    "❌ <b>Invalid redeem code.</b>\n\nPlease check the code and try again, "
                    "or contact support if you believe this is an error.",
                    parse_mode="HTML",
                    reply_markup=MAIN_MENU,
                )
                return

            if redeem["is_used"]:
                await update.message.reply_text(
                    "❌ <b>This redeem code has already been used.</b>",
                    parse_mode="HTML",
                    reply_markup=MAIN_MENU,
                )
                return

            amount = float(redeem["amount_usd"])
            await db.mark_redeem_code_used(code, user_id)
            await db.credit_balance_usd(user_id, amount, description=f"Redeem code: {code}")

            await update.message.reply_text(
                f"✅ <b>Redeem successful!</b>\n\n"
                f"💰 <b>${amount:.2f}</b> has been added to your balance.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )

            if CHANNEL_ID:
                try:
                    await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=(
                            f"🤑 <b>New Credits Added!</b>\n\n"
                            f"<blockquote>"
                            f"👤 <b>User:</b> <code>{mask_user_id(user_id)}</code>\n"
                            f"💵 <b>Amount:</b> 🤑\n"
                            f"💳 <b>Method:</b> Redeem Code 💳"
                            f"</blockquote>"
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            return

    if is_admin(user_id) and canonical not in MENU_BUTTONS:
        ud = await db.get_session(user_id)
        if ud.get("awaiting"):
            await _process_admin_input(update, context, user_id, ud)
            return

    if canonical == "🛒 Products":
        kb = await build_products_keyboard()
        title = await lang.t("choose_service", user_lang)
        await update.message.reply_text(title, parse_mode="HTML", reply_markup=kb)

    elif canonical == "👤 Profile":
        db_user = await db.get_user(update.effective_user.id)
        await update.message.reply_text(
            build_profile_text(update.effective_user, db_user),
            parse_mode="HTML",
            reply_markup=PROFILE_KEYBOARD,
        )

    elif canonical == "🎁 Invite Center":
        await invite_center.show_invite_center(update, context)

    elif canonical == "💰 Top up balance":
        topup_text = await lang.t("payment_methods_text", user_lang)
        await update.message.reply_text(
            topup_text,
            parse_mode="HTML",
            reply_markup=build_payment_methods_keyboard(),
        )

    elif canonical == "🎫 Redeem Code":
        await db.set_session(user_id, {"awaiting": "redeem_code"})
        prompt = await lang.t("redeem_prompt", user_lang)
        await update.message.reply_text(
            prompt,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Request Redeem Code", url="https://t.me/caydigitals")],
                [InlineKeyboardButton("✕ Close", callback_data="close")],
            ]),
        )

    elif canonical == "📋 Bot Policy":
        policy_text = await get_bot_policy()

        if user_lang != "en":
            cache_key = f"policy:{user_lang}"
            if cache_key not in _policy_cache:
                from lang import _translate_one
                _policy_cache[cache_key] = await _translate_one(policy_text, user_lang)
            policy_text = _policy_cache[cache_key]

        await update.message.reply_text(
            policy_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✕ Close", callback_data="close")]
            ]),
        )

    elif canonical == "❓ Help":
        help_text = await lang.t("help_text", user_lang)
        await update.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✕ Close", callback_data="close")]
            ]),
        )

    else:
        fallback = await lang.t("choose_option", user_lang)
        await update.message.reply_text(
            fallback,
            reply_markup=lang.build_main_menu(user_lang),
        )

async def handle_gcash_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not await membership_gate.check_membership(context, update.effective_user.id):
        await membership_gate.send_gate_message(update, context)
        return

    ud = await db.get_session(user_id)
    if ud.get("awaiting_receipt"):
        await gcash_topup.handle_gcash_receipt_photo(update, context)

# ─── ADMIN TEXT INPUT LOGIC ──────────────────────────────────────────────────

async def _process_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, ud: dict) -> None:
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

    elif awaiting == "ban_user_id":
        await ban_manager.handle_ban_input(update, context, ud)
        return

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

    elif awaiting == "redeem_amount":
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount. Please enter a positive number like 5.00:"
            )
            return
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        code = await db.create_redeem_code(amount, created_by=user_id)
        await update.message.reply_text(
            f"✅ <b>Redeem code created!</b>\n\n"
            f"🎫 Code: <code>{code}</code>\n"
            f"💰 Amount: <b>${amount:.2f}</b>\n\n"
            f"<i>Send this code to the customer. It can only be used once.</i>",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
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
                    "prod_edit_delivery", "prod_edit_demo", "prod_edit_deliveryurl"):
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
            "prod_edit_deliveryurl": ("delivery_url", lambda v: "" if v == "-" else v),  # ← new
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

    elif awaiting == "gcash_rate":
        try:
            rate = float(text.strip())
            if rate <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid rate. Enter a positive number like <code>57.50</code>:",
                parse_mode="HTML",
            )
            return
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        await db.set_setting("php_usd_rate", str(rate))
        await update.message.reply_text(
            f"✅ <b>GCash rate updated!</b>\n\n"
            f"💱 New rate: <b>₱{rate:.2f} = $1.00</b>\n\n"
            f"All new GCash deposits will use this rate.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )
 

    elif awaiting == "bot_policy_text":
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)

        if text.strip().lower() == "/cancel":
            await update.message.reply_text(
                "❌ Cancelled. The policy was not changed.",
                reply_markup=MAIN_MENU,
            )
            return

        if text.strip().lower() == "/reset":
            await db.set_setting(POLICY_SETTING_KEY, "")
            await update.message.reply_text(
                "♻️ Policy reset to the original built-in text.\n\n"
                f"{DEFAULT_BOT_POLICY}",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
            return

        new_policy = update.message.text or ""
        try:
            await update.message.reply_text(
                f"🔍 <b>Preview:</b>\n\n{new_policy}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✕ Close", callback_data="close")]]),
            )
        except Exception:
            await update.message.reply_text(
                "❌ That text has invalid HTML formatting (an unclosed or mismatched tag), so it wasn't saved.\n\n"
                "Stick to simple tags like <code>&lt;b&gt;bold&lt;/b&gt;</code> and <code>&lt;i&gt;italic&lt;/i&gt;</code>, "
                "and make sure every tag you open is closed. Send the corrected text again, or /cancel.",
                parse_mode="HTML",
            )
            await db.set_session(user_id, {"awaiting": "bot_policy_text"})
            return

        await db.set_setting(POLICY_SETTING_KEY, new_policy)
        _policy_cache.clear() 
        await update.message.reply_text(
            "✅ <b>Bot Policy updated!</b>\n\nEvery user will now see this new version immediately — no restart needed.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

    elif awaiting == "add_balance_user_id":
        try:
            target_user_id = int(text.strip())
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid ID. Please send a numeric Telegram user ID:"
            )
            return
        target_user = await db.get_user(target_user_id)
        if not target_user:
            await update.message.reply_text(
                "❌ No user found with that ID. Make sure they've started the bot at least once, then try again.\n\n"
                "Send the user ID again, or /admin to cancel."
            )
            return
        ud["add_balance_target"] = target_user_id
        ud["awaiting"] = "add_balance_amount"
        await db.set_session(user_id, ud)
        await update.message.reply_text(
            f"👤 User found: <b>{target_user.get('full_name', 'Unknown')}</b>\n"
            f"💰 Current balance: <b>${float(target_user.get('balance', 0)):.2f}</b>\n\n"
            f"Enter the <b>amount in USD</b> to add (e.g. <code>5.00</code>):",
            parse_mode="HTML",
        )

    elif awaiting == "add_balance_amount":
        try:
            amount = float(text.strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid amount. Enter a positive number like <code>5.00</code>:",
                parse_mode="HTML",
            )
            return
        target_user_id = ud.pop("add_balance_target", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)

        if not target_user_id:
            await update.message.reply_text("❌ Session expired. Please start again from the Admin Panel.")
            return

        await db.credit_balance_usd(
            target_user_id, amount, description=f"Admin Panel credit by {user_id}"
        )

        await update.message.reply_text(
            f"✅ <b>Balance added!</b>\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n"
            f"💰 Amount: <b>${amount:.2f}</b>",
            parse_mode="HTML",
            reply_markup=MAIN_MENU,
        )

        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🤑 <b>New Credits Added!</b>\n\n"
                    f"<blockquote>"
                    f"👤 <b>User:</b> <code>{mask_user_id(target_user_id)}</code>\n"
                    f"💵 <b>Amount:</b> ${amount:.2f}\n"
                    f"💳 <b>Method:</b> Admin Panel ⚙️"
                    f"</blockquote>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")

        # Notify channel (masked amount, same style as redeem/GCash)
        if CHANNEL_ID:
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=(
                        f"🤑 <b>New Credits Added!</b>\n\n"
                        f"<blockquote>"
                        f"👤 <b>User:</b> <code>{mask_user_id(target_user_id)}</code>\n"
                        f"💵 <b>Amount:</b> 🤑\n"
                        f"💳 <b>Method:</b> Admin Panel ⚙️"
                        f"</blockquote>"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify channel: {e}")

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

    ban_routed, gcash_routed, subs_routed = await asyncio.gather(
        ban_manager.route_callback(update, context),
        pending_gcash.route_callback(update, context),
        official_subscriptions.route_callback(update, context),
    )
    if ban_routed or gcash_routed or subs_routed:
        return

    if data.startswith(invite_center.CAPTCHA_CB_PREFIX):
        await invite_center.handle_captcha_answer(update, context)
        return

    if data == invite_center.CAPTCHA_CB_RETRY:
        await invite_center.handle_captcha_retry(update, context)
        return

    # ── Membership gate ──
    if data == "gate_check":
        await membership_gate.handle_gate_check(update, context)
        if await membership_gate.check_membership(context, user_id, use_cache=False):
            await invite_center.advance_after_gate_pass(user_id, context)
            await invite_center.mark_interaction_and_maybe_qualify(context, user_id)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="<blockquote><b>👋 Welcome to CayShop Bot!</b></blockquote>\n"
                    "I'm here to help you purchase subscriptions and digital "
                    "services easily and securely.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
        return

    if await ban_manager.is_user_banned(user_id):
        await query.answer("🚫 Your account has been suspended.", show_alert=True)
        return

    if data in ("admin_cattype_regular", "admin_cattype_official"):
        if not is_admin(user_id):
            await query.answer("⛔ Admins only.", show_alert=True)
            return
        ud = await db.get_session(user_id)
        name  = ud.get("new_cat_name")
        emoji = ud.get("new_cat_emoji")
        if not name or not emoji:
            await query.answer("Session expired — please start /admin again.", show_alert=True)
            return
        cat_type = "official" if data == "admin_cattype_official" else "regular"
        try:
            await db.add_category(name, emoji, type=cat_type)
        except Exception as e:
            logger.error(f"Failed to add category: {e}", exc_info=e)
            await query.answer("❌ Failed to save category. Please try again.", show_alert=True)
            return
        ud.pop("new_cat_name", None)
        ud.pop("new_cat_emoji", None)
        ud.pop("awaiting", None)
        await db.set_session(user_id, ud)
        kb = await admin_categories_keyboard()
        label = "Official Subscription" if cat_type == "official" else "Regular Product"
        await query.answer(f"✅ Category added!")
        await query.message.edit_text(
            f"✅ Category <b>{emoji} {name}</b> added as <b>{label}</b>!\n\n📂 <b>Categories</b>:",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return

    if data == "lang_en":
        context.user_data["lang"] = "en"
        await db.save_user_lang(user_id, "en")
        await query.answer("Language set to English ✅")
        await query.message.delete()
        welcome_text = await lang.t("welcome", "en")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=lang.build_main_menu("en"),
        )
        return

    if data == "lang_tl":
        context.user_data["lang"] = "tl"
        await db.save_user_lang(user_id, "tl")
        await query.answer("Wika itinakda sa Tagalog ✅")
        await query.message.delete()
        welcome_text = await lang.t("welcome", "tl")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=lang.build_main_menu("tl"),
        )
        return

    if not await membership_gate.check_membership(context, user_id):
        await membership_gate.send_gate_message(update, context)
        return

    await invite_center.mark_interaction_and_maybe_qualify(context, user_id)

    if data == "invite_stats":
        await invite_center.show_invite_stats(update, context)
        return
    
    if data == "invite_link":
        await invite_center.show_invite_link(update, context)
        return
    
    if data == "invite_back":
        await invite_center.show_invite_back(update, context)
        return

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

        # Save emoji to session, then ask for category type
        ud["new_cat_emoji"] = emoji
        await db.set_session(user_id, ud)

        await query.answer()
        await query.message.edit_text(
            f"📂 Category: <b>{emoji} {name}</b>\n\nWhat type is this category?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Regular Product",        callback_data="admin_cattype_regular")],
                [InlineKeyboardButton("✅ Official Subscription",  callback_data="admin_cattype_official")],
            ]),
        )
        return

    # ── Profile ──
    if data == "profile_status":
        db_user = await db.get_user(user_id)
        total_spent = float(db_user.get("total_spent", 0.0)) if db_user else 0.0
        current = db.get_status_tier(total_spent)
        next_tier = db.get_next_tier(total_spent)

        # Progress bar (10 blocks)
        if next_tier:
            progress_ratio = (total_spent - current["min"]) / (next_tier["min"] - current["min"])
            filled = int(progress_ratio * 10)
            bar = "🟩" * filled + "⬜" * (10 - filled)
            pct = int(progress_ratio * 100)
            remaining = next_tier["min"] - total_spent
            progress_text = (
                f"{bar} {pct}%\n"
                f"<b>${total_spent:.2f} / ${next_tier['min']:.2f}</b>\n"
                f"Remaining: <b>${remaining:.2f}</b>\n\n"
                f"Next status: <b>{next_tier['name']}</b> • discount <b>{next_tier['discount']}%</b>"
            )
        else:
            progress_text = "🏆 You've reached the highest status!"

        text = (
            f"🏅 <b>Statuses</b>\n\n"
            f"Current status: <b>{current['name']}</b> • discount <b>{current['discount']}%</b>\n\n"
            f"Progress to the next level:\n"
            f"{progress_text}"
        )
        await query.answer()
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🗂 All levels", callback_data="status_all_levels"),
                    InlineKeyboardButton("⬅️ Profile", callback_data="profile_back"),
                ],
                [InlineKeyboardButton("✕ Close", callback_data="close")],
            ]),
        )
        return

    if data == "status_all_levels":
        lines = ["🗂 <b>All statuses</b>\n\n"
                 "Statuses are based on your net purchase turnover excluding "
                 "refunds.\n"]
        db_user = await db.get_user(user_id)
        total_spent = float(db_user.get("total_spent", 0.0)) if db_user else 0.0
        for tier in db.STATUS_TIERS:
            is_current = db.get_status_tier(total_spent)["name"] == tier["name"]
            icon = "✅" if is_current else "•"
            lines.append(
                f"{icon} <b>{tier['name']}</b> — from <b>${tier['min']:.2f}</b>\n"
                f"  Bonus: <b>{tier['discount']}%</b> product discount\n"
            )
        await query.answer()
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🏅 My Status", callback_data="profile_status"),
                    InlineKeyboardButton("⬅️ Profile", callback_data="profile_back"),
                ],
                [InlineKeyboardButton("✕ Close", callback_data="close")],
            ]),
        )
        return

    if data == "profile_back":
        db_user = await db.get_user(user_id)
        await query.answer()
        await query.message.edit_text(
            build_profile_text(update.effective_user, db_user),
            parse_mode="HTML",
            reply_markup=PROFILE_KEYBOARD,
        )
        return

    if data == "profile_wallet":
        db_user = await db.get_user(user_id)
        balance = float(db_user.get("balance", 0.0)) if db_user else 0.0
        transactions = await db.get_transactions(user_id, limit=10)

        lines = [f"🏦 <b>Wallet Statement</b>\n\n💰 Current balance: <b>${balance:.2f}</b>\n\n"]

        if not transactions:
            lines.append("No wallet transactions yet.")
        else:
            for tx in transactions:
                try:
                    dt = datetime.fromisoformat(tx["created_at"].replace("Z", "+00:00"))
                    date_str = dt.strftime("%m/%d %H:%M")
                except Exception:
                    date_str = "—"

                if tx["type"] == "deposit":
                    php_part = f" (₱{tx['amount_php']:.2f})" if tx.get("amount_php") else ""
                    lines.append(
                        f"✅ <b>+${tx['amount_usd']:.2f}</b>{php_part}\n"
                        f"   🏦 {tx.get('description', 'Deposit')} • {date_str}\n"
                    )
                elif tx["type"] == "purchase":
                    lines.append(
                        f"🛒 <b>-${tx['amount_usd']:.2f}</b>\n"
                        f"   📦 {tx.get('description', 'Purchase')} • {date_str}\n"
                    )

        lines.append("\n<i>Showing last 10 transactions.</i>")

        await query.answer()
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Profile", callback_data="profile_back")],
            ]),
        )
        return

    if data == "profile_orders":
        transactions = await db.get_transactions(user_id, limit=20)
        purchases = [tx for tx in transactions if tx["type"] == "purchase"]

        if not purchases:
            await query.answer()
            await query.message.edit_text(
                "📭 <b>You have no orders yet.</b>\n\nPurchase from the Services section ⬇️",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Back", callback_data="profile_back")],
                ]),
            )
            return

        lines = ["📋 <b>My Orders</b>\n"]
        for tx in purchases:
            try:
                dt = datetime.fromisoformat(tx["created_at"].replace("Z", "+00:00"))
                date_str = dt.strftime("%m/%d/%Y %H:%M")
            except Exception:
                date_str = "—"
            desc = tx.get("description", "Purchase").replace("Purchase: ", "")
            lines.append(
                f"🛒 <b>{desc}</b>\n"
                f"   💰 ${tx['amount_usd']:.2f} • 📅 {date_str}\n"
            )
        lines.append("<i>Showing last 20 orders.</i>")

        await query.answer()
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Profile", callback_data="profile_back")],
            ]),
        )
        return

    if data in ("profile_withdraw", "profile_withdraw_req", "profile_withdraw_pro"):
        labels = {
            "profile_withdraw": "💸 Withdraw",
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
                    [InlineKeyboardButton("⬅️ Back to services", callback_data="back_to_products")]
                ]),
            )
            return
        product_buttons = [
            [InlineKeyboardButton(f"{cat_emoji} {p['name']}", callback_data=f"user_prod_{p['id']}")]
            for p in products
        ]
        product_buttons.append([InlineKeyboardButton("⬅️ Back to services", callback_data="back_to_products")])
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
        if prod["stock"] < qty:
            await query.answer(f"❌ Only {prod['stock']} in stock.", show_alert=True)
            return
        db_user = await db.get_user(user_id)
        balance = float(db_user.get("balance", 0)) if db_user else 0.0
        price = prod["price"]

        # ── Show quantity picker ──
        max_qty = min(prod["stock"], 25)
        preset_qtys = [q for q in [1, 2, 3, 5, 10, 15, 20, 25] if q <= max_qty]

        rows = []
        row = []
        for qty in preset_qtys:
            row.append(InlineKeyboardButton(str(qty), callback_data=f"qty_{prod_id}_{qty}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("✏️ Custom qty", callback_data=f"qty_custom_{prod_id}")])
        rows.append([
            InlineKeyboardButton("⬅️ Back to Product", callback_data=f"user_prod_{prod_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="close"),
        ])

        await query.answer()
        await query.message.edit_text(
            f"📦 <b>{prod['name']}</b>\n\n"
            f"Choose quantity (1–{max_qty}):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    # ── Quantity selected (preset) ──
    if data.startswith("qty_") and not data.startswith("qty_custom_"):
        parts = data.split("_")   # ["qty", prod_id, qty]
        prod_id = int(parts[1])
        qty = int(parts[2])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        if prod["stock"] < qty:
            await query.answer(f"❌ Only {prod['stock']} in stock.", show_alert=True)
            return
        db_user = await db.get_user(user_id)
        balance = float(db_user.get("balance", 0)) if db_user else 0.0
        price = prod["price"]
        total = round(price * qty, 2)

        if balance < total:
            await query.answer()
            await query.message.edit_text(
                f"❌ <b>Insufficient balance.</b>\n\n"
                f"Required: <b>${total:.2f}</b> ({qty}x)\n"
                f"Your balance: <b>${balance:.2f}</b>\n\n"
                f"Please top up your balance to continue.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Top up balance", callback_data="topup_from_buy")],
                    [InlineKeyboardButton("⬅️ Back", callback_data=f"buy_{prod_id}")],
                ]),
            )
            return

        delivery_url = (prod.get("delivery_url") or "").strip()
        if not delivery_url:
            await query.answer("⚠️ No delivery URL set. Please contact support.", show_alert=True)
            return

        tier = db.get_status_tier(float(db_user.get("total_spent", 0)))
        discount_pct = tier["discount"]
        discounted_unit = round(price * (1 - discount_pct / 100), 2)
        discounted_total = round(discounted_unit * qty, 2)

        await query.answer()
        await query.message.edit_text(
            f"🛒 <b>Confirm Purchase</b>\n\n"
            f"📦 Product: <b>{prod['name']}</b>\n"
            f"🔢 Quantity: <b>{qty}x</b>\n"
            f"💰 Unit price: <b>${price:.2f}</b>\n"
            + (f"🏷️ Your discount: <b>{discount_pct}%</b> → <b>${discounted_unit:.2f}</b>/each\n" if discount_pct > 0 else "")
            + f"💵 Total: <b>${discounted_total:.2f}</b>\n"
            f"👛 Your balance: <b>${balance:.2f}</b>\n"
            f"💳 Balance after: <b>${round(balance - discounted_total, 2):.2f}</b>\n\n"
            f"Tap <b>Confirm</b> to complete your purchase.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_buy_{prod_id}_{qty}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"buy_{prod_id}")],
            ]),
        )
        return

    # ── Custom quantity input ──
    if data.startswith("qty_custom_"):
        prod_id = int(data.split("_")[2])
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        await db.set_session(user_id, {"awaiting": "custom_qty", "qty_prod_id": prod_id})
        await query.answer()
        await query.message.reply_text(
            f"✏️ Enter the quantity you want (1–{prod['stock']}):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data.startswith("confirm_buy_"):
        parts = data.split("_")   # ["confirm", "buy", prod_id, qty]
        prod_id = int(parts[2])
        qty = int(parts[3]) if len(parts) > 3 else 1
        prod = await db.get_product(prod_id)
        if not prod:
            await query.answer("Product not found.", show_alert=True)
            return
        if prod["stock"] <= 0:
            await query.answer("❌ Out of stock.", show_alert=True)
            return
        db_user = await db.get_user(user_id)
        balance = float(db_user.get("balance", 0)) if db_user else 0.0
        price = prod["price"]
        if balance < final_price:
            await query.answer("❌ Insufficient balance.", show_alert=True)
            return

        delivery_url = (prod.get("delivery_url") or "").strip()
        if not delivery_url:
            await query.answer("⚠️ No delivery URL. Contact support.", show_alert=True)
            return

        # Apply tier discount
        tier = db.get_status_tier(float(db_user.get("total_spent", 0)))
        discount_pct = tier["discount"]
        final_unit = round(price * (1 - discount_pct / 100), 2)
        final_price = round(final_unit * qty, 2)   # ← was just final_unit * 1

        if balance < final_price:
            await query.answer("❌ Insufficient balance.", show_alert=True)
            return

        if prod["stock"] < qty:
            await query.answer(f"❌ Only {prod['stock']} in stock.", show_alert=True)
            return

        # ── Process the purchase ──
        await db.record_purchase(user_id, final_price, product_name=prod['name'], is_admin_purchase=is_admin(user_id))
        await db.update_product_stock(prod_id, prod["stock"] - qty)   # ← deduct qty not 1

        await query.answer("✅ Purchase successful!", show_alert=True)
        import random, string
        order_no = 'LNK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=11))

        await query.message.edit_text(
            f"✅ <b>Purchase Successful!</b>\n\n"
            f"📦 <b>{prod['name']}</b> × {qty}\n"
            f"💰 <b>${final_price:.2f}</b> deducted from your balance"
            + (f" <i>(discount applied: {discount_pct}%)</i>" if discount_pct > 0 else "")
            + "\n\n"
            f"🔗 <b>Your delivery link:</b>\n"
            f"{delivery_url}\n\n"
            f"⏳ Duration: {prod.get('duration') or '—'}\n"
            f"🛡 Warranty: {prod.get('warranty') or 'No warranty'}\n\n"
            f"🧾 <b>Order No.:</b> <code>{order_no}</code>\n\n"
            f"<i>Save this link — it won't be shown again.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Shop more", callback_data="back_to_products")],
                [InlineKeyboardButton("👤 My Profile", callback_data="profile_back")],
            ]),
        )

        # ── Process order number and total purchases ──
        cat = await db.get_category(prod["category_id"])
 
        db_user_fresh = await db.get_user(user_id)
 
        if is_admin(user_id):
            admin_total = int(db_user_fresh.get("admin_total_purchases", 0)) if db_user_fresh else 0
            admin_msg = (
                f"<blockquote>"
                f"🧪 <b>Admin Test Purchase</b>\n\n"
                f"📧 <b>Service:</b> {cat['name'] if cat else '—'}\n"
                f"👤 <b>By:</b> <code>ADMIN</code>\n"
                f"🎁 <b>Plan:</b> {prod['name']}\n"
                f"🧾 <b>Order No.:</b> <code>{order_no}</code>\n"
                f"🔢 <b>QTY:</b> {qty}\n"
                f"📊 <b>Admin Total:</b> {admin_total}"
                f"</blockquote>"
            )
        else:
            # Real user purchase — use user's total_purchases
            total_purchases = int(db_user_fresh.get("total_purchases", 1)) if db_user_fresh else 1
            admin_msg = (
                f"<blockquote>"
                f"🎉 <b>New Purchase!</b>\n\n"
                f"📧 <b>Service:</b> {cat['name'] if cat else '—'}\n"
                f"👤 <b>By:</b> <code>{mask_user_id(user_id)}</code>\n"
                f"🎁 <b>Plan:</b> {prod['name']}\n"
                f"🧾 <b>Order No.:</b> <code>{order_no}</code>\n"
                f"🔢 <b>QTY:</b> {qty}\n"
                f"📊 <b>Total Purchase!:</b> {total_purchases}"
                f"</blockquote>"
            )

        # Always notify admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            except Exception:
                pass

        # Always notify channel
        if CHANNEL_ID:
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=admin_msg,
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    if data == "topup_from_buy":
        await query.answer()
        await query.message.edit_text(
            PAYMENT_METHODS_TEXT,
            parse_mode="HTML",
            reply_markup=build_payment_methods_keyboard(),
        )
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

    if data == "admin_gen_redeem":
        await db.set_session(user_id, {"awaiting": "redeem_amount"})
        await query.answer()
        await query.message.reply_text(
            "🎫 Enter the <b>amount in USD</b> for this redeem code (e.g. <code>5.00</code>):",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data == "admin_add_balance":
        await db.set_session(user_id, {"awaiting": "add_balance_user_id"})
        await query.answer()
        await query.message.reply_text(
            "➕ <b>Add Balance</b>\n\n"
            "Enter the <b>Telegram user ID</b> of the customer:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data == "admin_settings":
        rate = await db.get_php_usd_rate()
        await query.answer()
        await query.message.edit_text(
            f"⚙️ <b>Bot Settings</b>\n\n"
            f"💱 <b>GCash Exchange Rate</b>\n"
            f"Current rate: <b>₱{rate:.2f} = $1.00</b>\n\n"
            f"<i>Update this whenever the PHP/USD rate changes.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💱 Set GCash Rate", callback_data="admin_set_gcash_rate")],
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_main")],
            ]),
        )
        return

    if data == "admin_set_gcash_rate":
        rate = await db.get_php_usd_rate()
        await db.set_session(user_id, {"awaiting": "gcash_rate"})
        await query.answer()
        await query.message.reply_text(
            f"💱 Enter the new <b>PHP → USD exchange rate</b>.\n\n"
            f"Current rate: <b>₱{rate:.2f} = $1.00</b>\n\n"
            f"Example: if $1 = ₱57.50, send <code>57.50</code>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if data == "admin_edit_policy":
        current = await get_bot_policy()
        await query.answer()
        await query.message.reply_text(
            f"📋 <b>Current Bot Policy</b>\n\n{current}",
            parse_mode="HTML",
        )
        await query.message.reply_text(
            "✏️ Send the <b>new policy text</b> now and it will replace the message above for every user "
            "— no restart needed.\n\n"
            "• HTML formatting is supported: <code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, <code>&lt;code&gt;</code>, "
            "line breaks just by pressing Enter.\n"
            "• Send <code>/cancel</code> to leave it as is.\n"
            "• Send <code>/reset</code> to restore the original built-in policy.",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        await db.set_session(user_id, {"awaiting": "bot_policy_text"})
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
            "deliveryurl": ("prod_edit_deliveryurl", "🔗 Enter the <b>delivery URL</b> users receive after purchase. Send <code>-</code> to clear:"),
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
        target_user_id = int(parts[3])
        amount_php = float(parts[4])

        rate = await db.get_php_usd_rate()
        amount_usd = round(amount_php / rate, 2)

        await db.credit_balance(target_user_id, amount_php, rate=rate)
        await pending_gcash.clear_pending(target_user_id)
        await query.answer("✅ Balance credited!", show_alert=True)

        # Get existing plain-text caption and replace the status line
        try:
            original = query.message.caption or ""
            # Replace the plain text status line (no HTML tags in caption property)
            updated_caption = original.replace(
                "Status: PENDING VERIFICATION",
                "Status: ✅ APPROVED"
            )
            await query.message.edit_caption(
                caption=updated_caption,
                parse_mode=None,  # ← plain text, no HTML since caption is already plain
                reply_markup=None,
            )
        except Exception as e:
            logger.warning(f"Could not edit admin message: {e}")

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"🤑 <b>New Credits Added!</b>\n\n"
                    f"<blockquote>"
                    f"👤 <b>User:</b> <code>{mask_user_id(target_user_id)}</code>\n"
                    f"💵 <b>Amount:</b> ${amount_usd:.2f} (₱{amount_php:.2f})\n"
                    f"💳 <b>Method:</b> GCash Deposit 🇵🇭"
                    f"</blockquote>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")

        # Notify channel
        if CHANNEL_ID:
            try:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=(
                        f"🤑 <b>New Credits Added!</b>\n\n"
                        f"<blockquote>"
                        f"👤 <b>User:</b> <code>{mask_user_id(target_user_id)}</code>\n"
                        f"💵 <b>Amount:</b> 🤑\n"
                        f"💳 <b>Method:</b> GCash Deposit 🇵🇭"
                        f"</blockquote>"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify channel: {e}")
        return

    if data.startswith("admin_reject_gcash_"):
        target_user_id = int(data.split("_")[3])
        await pending_gcash.clear_pending(target_user_id)
        await query.answer("❌ Claim rejected.", show_alert=True)

        # Rebuild caption with updated status line, remove all buttons
        try:
            original = query.message.caption or ""
            updated_caption = original.replace(
                "Status: PENDING VERIFICATION",
                "Status: ❌ REJECTED"
            )
            await query.message.edit_caption(
                caption=updated_caption,
                parse_mode=None,  # ← plain text
                reply_markup=None,
            )
        except Exception as e:
            logger.warning(f"Could not edit admin message: {e}")

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ <b>Deposit not verified.</b>\n\nWe could not verify your GCash payment. Please contact support if you believe this is an error.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
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

    await lang.preload_translations("tl")

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
    app.add_handler(CallbackQueryHandler(official_subscriptions.handle_official_subs, pattern="^official_subs$"))
    app.add_handler(MessageHandler(
        filters.PHOTO & ~filters.COMMAND,
        handle_gcash_receipt,
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()