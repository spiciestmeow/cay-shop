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
# All strings are English only. Tagalog is produced by translate_text() above.
# Keep HTML tags on their own — Google Translate preserves them correctly.

STRINGS: dict[str, str] = {

    # Language picker
    "lang_prompt": "🌐 Please choose your language:",

    # Common UI
    "btn_close":            "✕ Close",
    "btn_back":             "⬅️ Back",
    "btn_back_to_services": "⬅️ Back to Services",
    "btn_change_language":  "🌐 Change Language",

    # Welcome
    "welcome": (
        "<blockquote><b>👋 Welcome to CayShop Bot!</b></blockquote>\n"
        "I'm here to help you purchase subscriptions and digital "
        "services easily and securely."
    ),

    # Help
    "help_text": (
        "💬 <b>Support &amp; Assistance</b>\n\n"
        "✉️ If you need help, please contact\n"
        "<b>Customer Support:</b> @caydigitals\n\n"
        "⏳ You will receive a response once your request has been reviewed"
    ),

    # Bot Policy
    "default_policy": (
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
        "• Or if the user does not wish to replace, the amount will be returned as balance in the bot and "
        "can be used to purchase any other product.\n\n"
        "3️⃣ <b>Free Credits:</b>\n"
        "Funds received by the user through redeem codes or referral rewards cannot be refunded.\n\n"
        "4️⃣ <b>Our Commitment:</b>\n"
        "We are fully responsible for our services and strive to ensure that no customer is annoyed or harmed.\n\n"
        "5️⃣ <b>Our Promise:</b>\n"
        "We promise to always be honest and faithful with you, and strive to be the best in providing these services."
    ),

    # Payment Methods
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

    # Official Subscriptions
    "official_subs_empty": (
        "✅ <b>Official Subscriptions</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📭 No subscriptions available yet.\n"
        "Check back soon!"
    ),

    # Products
    "btn_official_subs":  "✅ Official Subscriptions",
    "btn_whats_available": "🟢 What's Available",
    "products_title":     "📋 Choose a category:",

    # Top up
    "topup_title": "💰 <b>Top Up Balance</b>\n\nChoose your preferred payment method:",

    # Redeem
    "redeem_prompt":  "🎫 Please enter your redeem code:",
    "redeem_success": "✅ Code redeemed successfully! Your balance has been updated.",
    "redeem_invalid": "❌ Invalid or already used code. Please try again.",

    # Errors
    "out_of_stock":    "❌ This item is currently out of stock.",
    "contact_support": "Need help? Contact @caydigitals",

    "choose_service": "📋 <b>Choose a service:</b>",
    "choose_option":  "Please choose an option from the menu below:",
}
