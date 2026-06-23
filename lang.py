bash

cat > /home/claude/bot/lang.py << 'LANGEOF'
# ─── TRANSLATION ENGINE ───────────────────────────────────────────────────────

import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

logger = logging.getLogger(__name__)

# Flat cache: { "tl:welcome": "Maligayang pagdating..." }
_cache: dict[str, str] = {}
_preloaded: bool = False


async def _translate_one(text: str, dest: str) -> str:
    """Translate a single string. Returns original on failure."""
    if not text.strip():
        return text
    cache_key = f"{dest}:{text}"
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        from deep_translator import GoogleTranslator
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source="en", target=dest).translate(text)
        )
        _cache[cache_key] = result or text
        return _cache[cache_key]
    except Exception as e:
        logger.warning(f"[lang] translate failed ({dest}): {e}")
        return text


async def preload_translations(dest: str = "tl") -> None:
    """
    Translate every string in STRINGS into `dest` language at startup.
    Call this once from post_init. After this, t() is instant — no network.
    """
    global _preloaded
    if _preloaded:
        return
    logger.info(f"[lang] Pre-loading all translations → {dest} ...")
    for key, english in STRINGS.items():
        cache_key = f"{dest}:{english}"
        if cache_key not in _cache:
            translated = await _translate_one(english, dest)
            _cache[cache_key] = translated
    _preloaded = True
    logger.info(f"[lang] Done — {len(STRINGS)} strings ready.")


async def t(key: str, language: str = "en") -> str:
    """
    Return the string for `key` in `language`.
    - English: instant dict lookup, no network.
    - Other: instant cache lookup after preload. Falls back to English.
    """
    english = STRINGS.get(key, f"[{key}]")
    if language == "en":
        return english
    cache_key = f"{language}:{english}"
    if cache_key in _cache:
        return _cache[cache_key]
    # Not preloaded yet — translate on the fly and cache it
    return await _translate_one(english, language)


async def tf(key: str, language: str = "en", **kwargs) -> str:
    """
    Translate key and format with kwargs.
    Falls back gracefully if placeholders got mangled by translation.
    Example: await lang.tf("buy_insufficient", user_lang, REQUIRED="$5.00", BALANCE="$1.00")
    """
    text = await t(key, language)
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        # Placeholder got mangled by translation; fall back to English version
        english = STRINGS.get(key, f"[{key}]")
        try:
            return english.format(**kwargs)
        except Exception:
            return english


# ─── LANGUAGE PICKER ─────────────────────────────────────────────────────────

LANG_PICKER_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        InlineKeyboardButton("🇵🇭 Tagalog", callback_data="lang_tl"),
    ]
])


async def get_lang_db(user_id: int, context) -> str:
    """
    Get language — checks context.user_data first (fast),
    then falls back to DB if missing (e.g. after bot restart).
    """
    if context.user_data.get("lang"):
        return context.user_data["lang"]
    # Fallback: load from DB
    import db
    user = await db.get_user(user_id)
    if user and user.get("lang"):
        context.user_data["lang"] = user["lang"]  # cache it
        return user["lang"]
    return "en"


async def get_lang_from_db_only(user_id: int) -> str:
    """Get language for a specific user without context (e.g. for notifications)."""
    import db
    user = await db.get_user(user_id)
    if user and user.get("lang"):
        return user["lang"]
    return "en"


# ─── MAIN MENU ────────────────────────────────────────────────────────────────
# Menu button labels are hardcoded (not live-translated) so they stay consistent
# as callback anchors. Only 7 short labels — easy to maintain.

MENU_LABELS = {
    "en": {
        "products": "🛒 Products",
        "profile":  "👤 Profile",
        "invite":   "🎁 Invite Center",
        "topup":    "💰 Top up balance",
        "redeem":   "🎫 Redeem Code",
        "policy":   "📋 Bot Policy",
        "help":     "❓ Help",
    },
    "tl": {
        "products": "🛒 Mga Produkto",
        "profile":  "👤 Profile",
        "invite":   "🎁 Invite Center",
        "topup":    "💰 Mag-top up",
        "redeem":   "🎫 I-redeem ang Code",
        "policy":   "📋 Patakaran ng Bot",
        "help":     "❓ Tulong",
    },
}

ALL_MENU_BUTTONS: set[str] = {
    label
    for labels in MENU_LABELS.values()
    for label in labels.values()
}

_REVERSE_MENU: dict[str, str] = {
    label: MENU_LABELS["en"][key]
    for lang_code, labels in MENU_LABELS.items()
    for key, label in labels.items()
}


def normalize_menu(text: str) -> str:
    """Any language menu button text → canonical English label."""
    return _REVERSE_MENU.get(text, text)


def build_main_menu(lang: str = "en") -> ReplyKeyboardMarkup:
    """Return the main ReplyKeyboardMarkup in the user's language."""
    m = MENU_LABELS.get(lang, MENU_LABELS["en"])
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(m["products"])],
            [KeyboardButton(m["profile"]),  KeyboardButton(m["invite"])],
            [KeyboardButton(m["topup"]),    KeyboardButton(m["redeem"])],
            [KeyboardButton(m["policy"]),   KeyboardButton(m["help"])],
        ],
        resize_keyboard=True,
    )


# ─── ENGLISH STRINGS (source of truth) ───────────────────────────────────────
# All strings are English only. Tagalog is produced by _translate_one() above.
# Keep HTML tags on their own — Google Translate preserves them correctly.
# For templates with dynamic values use {CAPS_PLACEHOLDER} — these are
# generally preserved by Google Translate when they look like variables.

STRINGS: dict[str, str] = {

    # ── Language picker ───────────────────────────────────────────────────────
    "lang_prompt": "🌐 Please choose your language:",

    # ── Common UI ─────────────────────────────────────────────────────────────
    "btn_close":            "✕ Close",
    "btn_back":             "⬅️ Back",
    "btn_back_to_services": "⬅️ Back to Services",
    "btn_change_language":  "🌐 Change Language",
    "btn_confirm":          "✅ Confirm",
    "btn_cancel":           "❌ Cancel",
    "btn_check_membership": "✅ Check Membership",
    "btn_join_channel":     "📢 Join Channel",
    "btn_shop_more":        "🛒 Shop more",
    "btn_my_profile":       "👤 My Profile",
    "btn_top_up_balance":   "💰 Top up balance",
    "btn_send_gift":        "🎁 Send as Gift",
    "btn_new_question":     "🔄 New question",
    "btn_invite_stats":     "📊 Invite Stats",
    "btn_invite_link":      "🔗 Invite Link",
    "btn_request_redeem":   "💬 Request Redeem Code",
    "btn_ive_paid":         "✅ I've Paid",
    "btn_cancel_request":   "❌ Cancel request",
    "btn_back_to_plans":    "⬅️ Back to plans",

    # ── Profile keyboard buttons ───────────────────────────────────────────────
    "btn_my_status":        "🏅 My Status",
    "btn_my_orders":        "📋 My Orders",
    "btn_wallet":           "🏦 Wallet statement",
    "btn_all_levels":       "🗂 All levels",
    "btn_back_to_profile":  "⬅️ Profile",

    # ── Welcome ───────────────────────────────────────────────────────────────
    "welcome": (
        "<blockquote><b>👋 Welcome to CayShop Bot!</b></blockquote>\n"
        "I'm here to help you purchase subscriptions and digital "
        "services easily and securely."
    ),

    # ── Help ──────────────────────────────────────────────────────────────────
    "help_text": (
        "💬 <b>Support &amp; Assistance</b>\n\n"
        "✉️ If you need help, please contact\n"
        "<b>Customer Support:</b> @caydigitals\n\n"
        "⏳ You will receive a response once your request has been reviewed"
    ),

    # ── Membership gate ───────────────────────────────────────────────────────
    "gate_text": (
        "Hello there! 👋\n"
        "To use this bot and access our services, you must first join our "
        "Telegram channel.\n\n"
        "👇 Click the button below to join, then click \"Check Now\"."
    ),
    "gate_verified": "✅ Verified successfully. Welcome!",
    "gate_not_joined": "❌ You are not subscribed yet. Join first, then click verify again.",

    # ── Payment Methods ───────────────────────────────────────────────────────
    "payment_methods_text": (
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
    ),

    "binance_info": (
        "💳 <b>Binance Pay / Crypto Transfer</b>\n\n"
        "Supported networks:\n"
        "• <code>BEP20 (USDT)</code> — BNB Smart Chain\n"
        "• <code>Polygon (USDT)</code> — Polygon Network\n"
        "• <code>TRC20 (USDT)</code> — Tron Network\n\n"
        "🚨 <b>Steps:</b>\n"
        "1️⃣ Open Binance → Wallets → Withdraw\n"
        "2️⃣ Select USDT\n"
        "3️⃣ Paste the wallet address provided\n"
        "4️⃣ Choose the <b>matching network</b>\n"
        "5️⃣ Enter the amount and confirm\n\n"
        "✅ <b>Auto Pay</b> — completed within a few minutes.\n\n"
        "⚠️ <b>Warning:</b> Wrong network = loss of funds."
    ),

    "polygon_info": (
        "🔗 <b>Polygon (USDT)</b>\n\n"
        "<b>Network:</b> Polygon Network\n\n"
        "<b>How to send:</b>\n"
        "1️⃣ Open your wallet\n"
        "2️⃣ Select Polygon Network\n"
        "3️⃣ Paste the wallet address provided\n"
        "4️⃣ Enter the amount\n"
        "5️⃣ Confirm and send\n\n"
        "✅ <b>Auto Pay:</b> Your order is completed within a few minutes."
    ),

    "trc20_info": (
        "🔗 <b>TRC20 (USDT)</b>\n\n"
        "<b>Network:</b> Tron Network\n\n"
        "<b>How to send:</b>\n"
        "1️⃣ Open your wallet\n"
        "2️⃣ Select Tron Network\n"
        "3️⃣ Paste the wallet address provided\n"
        "4️⃣ Enter the amount\n"
        "5️⃣ Confirm and send\n\n"
        "✅ <b>Auto Pay:</b> Your order is completed within a few minutes."
    ),

    "stars_info": (
        "We would like to inform you that if you are unable to make a payment via Binance, "
        "you can complete the payment using Telegram Stars.\n\n"
        "📌 <b>Payment Method:</b>\n"
        "You can send Stars as a gift to the following username:\n"
        "@caydigitals\n\n"
        "💰 <b>Available Packages:</b>\n\n"
        "- 300 Stars = $3\n"
        "- 500 Stars = $6\n"
        "- 1200 Stars = $16\n\n"
        "📩 After completing the payment, you will receive a Redeem Code in the same chat from the support team.\n\n"
        "Thank you for your cooperation 🌟"
    ),

    # ── Official Subscriptions ─────────────────────────────────────────────────
    "official_subs_empty": (
        "✅ <b>Official Subscriptions</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📭 No subscriptions available yet.\n"
        "Check back soon!"
    ),
    "official_subs_choose": "Choose a product:",

    # ── Products ──────────────────────────────────────────────────────────────
    "btn_official_subs":   "✅ Official Subscriptions",
    "btn_whats_available": "🟢 What's Available",
    "products_title":      "📋 Choose a category:",

    # ── Top up ────────────────────────────────────────────────────────────────
    "topup_title": "💰 <b>Top Up Balance</b>\n\nChoose your preferred payment method:",

    # ── Redeem ────────────────────────────────────────────────────────────────
    "redeem_prompt":       "🎫 Please enter your redeem code:",
    "redeem_success":      "✅ Code redeemed successfully! Your balance has been updated.",
    "redeem_invalid":      "❌ Invalid or already used code. Please try again.",
    "redeem_invalid_code": (
        "❌ <b>Invalid redeem code.</b>\n\nPlease check the code and try again, "
        "or contact support if you believe this is an error."
    ),
    "redeem_used_code":    "❌ <b>This redeem code has already been used.</b>",
    "redeem_success_user": "✅ <b>Redeem successful!</b>\n\n💰 <b>{AMOUNT}</b> has been added to your balance.",

    # ── Profile ───────────────────────────────────────────────────────────────
    "profile_header":        "👤 <b>Profile</b>",
    "profile_lbl_user_id":   "🆔 <b>User ID:</b>",
    "profile_lbl_name":      "👤 <b>Name:</b>",
    "profile_lbl_balance":   "💰 <b>Balance:</b>",
    "profile_lbl_level":     "⭐ <b>Level:</b>",
    "profile_lbl_discount":  "🏷️ <b>Product discount:</b>",
    "profile_lbl_purchases": "🛒 <b>Total purchases:</b>",
    "profile_lbl_spent":     "💸 <b>Spent (net):</b>",
    "profile_lbl_regdate":   "📅 <b>Registration date:</b>",

    # ── Status ────────────────────────────────────────────────────────────────
    "status_title":          "🏅 <b>Statuses</b>",
    "status_current_lbl":    "Current status:",
    "status_progress_lbl":   "Progress to the next level:",
    "status_remaining_lbl":  "Remaining:",
    "status_next_lbl":       "Next status:",
    "status_discount_lbl":   "discount",
    "status_max_reached":    "🏆 You've reached the highest status!",
    "status_all_title":      "🗂 <b>All statuses</b>",
    "status_all_header":     (
        "Statuses are based on your net purchase turnover excluding refunds."
    ),
    "status_from_lbl":       "from",
    "status_bonus_lbl":      "Bonus:",
    "status_product_discount": "product discount",

    # ── Wallet ────────────────────────────────────────────────────────────────
    "wallet_title":           "🏦 <b>Wallet Statement</b>",
    "wallet_balance_lbl":     "💰 Current balance:",
    "wallet_no_txn":          "No wallet transactions yet.",
    "wallet_last_10":         "Showing last 10 transactions.",
    "wallet_deposit_lbl":     "Deposit",
    "wallet_purchase_lbl":    "Purchase",

    # ── Orders ────────────────────────────────────────────────────────────────
    "orders_title":    "📋 <b>My Orders</b>",
    "orders_none":     "📭 <b>You have no orders yet.</b>\n\nPurchase from the Services section ⬇️",
    "orders_last_20":  "Showing last 20 orders.",

    # ── Product browsing ──────────────────────────────────────────────────────
    "cat_no_products":    "🚫 No products available in this category yet.",
    "choose_plan_label":  "Choose your {NAME} plan:",
    "back_to_products_title": "<b>Choose a service:</b>",
    "product_lbl_duration":   "⏳ Duration:",
    "product_lbl_warranty":   "🛡 Warranty:",
    "product_lbl_delivery":   "📦 Delivery:",

    # ── Buy flow ──────────────────────────────────────────────────────────────
    "buy_insufficient": (
        "❌ <b>Insufficient balance.</b>\n\n"
        "Required: <b>{REQUIRED}</b>\n"
        "Your balance: <b>{BALANCE}</b>\n\n"
        "Please top up your balance to continue."
    ),
    "buy_confirm_title":      "🛒 <b>Confirm Purchase</b>",
    "buy_lbl_product":        "📦 Product:",
    "buy_lbl_orig_price":     "💰 Original price:",
    "buy_lbl_discount":       "🏷️ Your discount: <b>{PCT}%</b> → <b>{PRICE}</b>",
    "buy_lbl_your_balance":   "👛 Your balance:",
    "buy_lbl_balance_after":  "💳 Balance after:",
    "buy_confirm_cta":        "Tap <b>Confirm</b> to complete your purchase.",
    "buy_success_title":      "✅ <b>Purchase Successful!</b>",
    "buy_deducted_msg":       "💰 <b>{AMOUNT}</b> deducted from your balance",
    "buy_discount_applied":   "<i>(discount applied: {PCT}%)</i>",
    "buy_lbl_delivery_link":  "🔗 <b>Your delivery link:</b>",
    "buy_lbl_order_no":       "🧾 <b>Order No.:</b>",
    "buy_lbl_duration":       "⏳ Duration:",
    "buy_lbl_warranty":       "🛡 Warranty:",
    "buy_save_link_hint":     "<i>Save this link — it won't be shown again.</i>",

    # ── GCash topup flow ──────────────────────────────────────────────────────
    "gcash_enter_amount": (
        "<blockquote>🇵🇭 <b>Enter deposit amount</b></blockquote>\n\n"
        "Network: <b>GCash</b>\n"
        "Minimum: <b>₱{MIN_PHP}</b> (≈ <b>{MIN_USD}</b>)\n"
        "Maximum: <b>₱{MAX_PHP}</b> (≈ <b>{MAX_USD}</b>)\n"
        "<i>Rate: ₱{RATE} = $1.00</i>\n\n"
        "<i>Send numbers only, e.g. <b>500</b></i>"
    ),
    "gcash_invalid_amount": (
        "⚠️ Invalid amount.\nSend numbers only (e.g. <b>500</b> or <b>500.5</b>)."
    ),
    "gcash_amount_range": "⚠️ Amount must be between ₱{MIN} and ₱{MAX}.",
    "gcash_cancelled_notice": "❌ GCash deposit request cancelled.",
    "gcash_payment_caption": (
        "<blockquote>📱 <b>PHP Payment Request (GCash)</b></blockquote>\n\n"
        "✅ Scan the QR code or send payment to the number below.\n"
        "⏳ <b>Expires in:</b> {EXPIRES}\n\n"
        "🪙 <b>Currency:</b> PHP (₱)\n"
        "💰 <b>Amount to send (PHP):</b>\n"
        "<pre><code>{UNIQUE_AMOUNT}</code></pre>\n"
        "💵 <b>Equivalent in USD:</b>\n"
        "<pre><code>≈ {USD_EQUIV}</code></pre>\n"
        "<i>(Rate: ₱{RATE} = $1.00)</i>\n\n"
        "📛 <b>Account name:</b>\n"
        "<pre><code>{ACCOUNT_NAME}</code></pre>\n"
        "📞 <b>GCash number:</b>\n"
        "<pre><code>{GCASH_NUM}</code></pre>\n\n"
        "⚠️ <i>Transfer fees may apply depending on your bank/e-wallet.</i>\n\n"
        "<blockquote>🔔 <b>Transfer Fee Notice</b></blockquote>\n\n"
        "• Some banks/e-wallets deduct a small fee when sending via InstaPay.\n"
        "• The amount received must be exactly <code>{UNIQUE_AMOUNT2}</code>.\n"
        "• If your platform deducts fees, add them on top.\n\n"
        "<blockquote>📌 <b>Important</b></blockquote>\n\n"
        "• All deposits are <b>non-refundable</b>.\n"
        "• Send the <b>exact amount</b> — centavos matter; they identify your payment.\n"
        "• Only send via <b>GCash</b>.\n\n"
        "<blockquote>🕓 <b>Manual Confirmation</b></blockquote>\n"
        "<i>Once you've paid, tap <b>\"I've Paid\"</b> below.\n"
        "You'll be asked to send your <b>payment receipt screenshot</b>.\n"
        "Your balance will be credited after verification — usually within a few minutes.</i>"
    ),
    "gcash_expired":       "⌛️ Deposit request expired. Please create a new one.",
    "gcash_expired_msg":   "⌛ <b>Request expired.</b>\n\nPlease start a new GCash deposit.",
    "gcash_send_receipt": (
        "📸 <b>Send your payment receipt</b>\n\n"
        "Please send a <b>screenshot</b> of your GCash transaction as a photo.\n\n"
        "<i>This helps our team verify your payment faster.</i>"
    ),
    "gcash_receipt_received": (
        "✅ <b>Receipt received!</b>\n\n"
        "💰 PHP: <b>₱{UNIQUE_PHP}</b>\n"
        "💵 USD equivalent: <b>≈ {USD_EQ}</b>\n\n"
        "Our team will verify your payment and credit your balance shortly. "
        "You'll be notified once confirmed. 🙏"
    ),
    "gcash_cancelled": "❌ <b>GCash deposit request cancelled.</b>",
    "gcash_approved_notification": (
        "🤑 <b>New Credits Added!</b>\n\n"
        "<blockquote>"
        "👤 <b>User:</b> <code>{USER_ID}</code>\n"
        "💵 <b>Amount:</b> {AMOUNT_USD} (₱{AMOUNT_PHP})\n"
        "💳 <b>Method:</b> GCash Deposit 🇵🇭"
        "</blockquote>"
    ),
    "gcash_rejected_notification": (
        "❌ <b>Deposit not verified.</b>\n\n"
        "We could not verify your GCash payment. "
        "Please contact support if you believe this is an error."
    ),

    # ── Credits added notification (admin balance / redeem) ───────────────────
    "credits_added_notification": (
        "🤑 <b>New Credits Added!</b>\n\n"
        "<blockquote>"
        "👤 <b>User:</b> <code>{USER_ID}</code>\n"
        "💵 <b>Amount:</b> {AMOUNT}\n"
        "💳 <b>Method:</b> {METHOD}"
        "</blockquote>"
    ),
    "method_admin_panel":  "Admin Panel ⚙️",
    "method_redeem_code":  "Redeem Code 💳",

    # ── Invite center ─────────────────────────────────────────────────────────
    "invite_center_prompt": "Choose an invite option below.",
    "invite_stats_text": (
        "<blockquote>📊 <b>Your invite stats:</b>\n\n"
        "🔑 Total sign-ups: <b>{TOTAL}</b>\n"
        "⏳ Awaiting join (group+channel): <b>{AWAITING_JOIN}</b>\n"
        "🧩 Awaiting human verify: <b>{AWAITING_HUMAN}</b>\n"
        "🎮 Awaiting bot interaction: <b>{AWAITING_INTER}</b>\n"
        "✅ Qualified for reward batch: <b>{QUALIFIED}</b>\n"
        "🏅 Invites already rewarded: <b>{REWARDED}</b>\n\n"
        "💰 <b>Total balance earned:</b> {TOTAL_EARNED}</blockquote>\n\n"
        "📌 <i><b>Every {PER_REWARD} qualified invites = {REWARD_USD}.</b></i>"
    ),
    "invite_link_text": (
        "<blockquote>🔗 <b>Your exclusive invite link:</b></blockquote>"
        "<pre>{LINK}</pre>\n\n"
        "<i><b>Share this link with friends and earn {REWARD_USD} for every "
        "{PER_REWARD} people who join and activate the bot! 🎉</b></i>"
    ),
    "invite_welcome_referral": (
        "👋 Welcome! You joined through {NAME}'s invitation.\n"
        "Thanks for joining! Enjoy the service. 🎉"
    ),
    "invite_referrer_qualified": (
        "<blockquote>✅ <b>Your invitation for {NAME} was counted successfully!\n"
        "📊 Your successful invites: {COUNT}/{PER_REWARD}</b></blockquote>\n\n"
        "<blockquote>🎉 <b>You earned a reward batch! {AMOUNT} added to your balance.</b></blockquote>"
    ),
    "invite_referrer_remaining": (
        "<blockquote>✅ <b>Your invitation for {NAME} was counted successfully!\n"
        "📊 Your successful invites: {COUNT}/{PER_REWARD}</b></blockquote>\n\n"
        "<blockquote><b><i>{REMAINING} invite(s) left to earn a reward.</i></b></blockquote>"
    ),
    "invite_reward_notification": (
        "🎉 <b>Referral reward!</b>\n\n"
        "You just hit <b>{COUNT}</b> qualified invites.\n"
        "💰 <b>{AMOUNT}</b> has been added to your balance."
    ),

    # ── Math CAPTCHA ──────────────────────────────────────────────────────────
    "captcha_text": (
        "👋 <b>Welcome!</b>\n\n"
        "🧠 <b>Solve this to prove you're human:</b>\n\n"
        "<blockquote>❓  <b>{QUESTION} = ?</b></blockquote>\n\n"
        "👇 Tap the correct answer below:"
    ),
    "captcha_wrong": "❌ Wrong answer! Try a new question.",

    # ── Errors ────────────────────────────────────────────────────────────────
    "out_of_stock":    "❌ This item is currently out of stock.",
    "contact_support": "Need help? Contact @caydigitals",

    "choose_service": "📋 <b>Choose a service:</b>",
    "choose_option":  "Please choose an option from the menu below:",
}