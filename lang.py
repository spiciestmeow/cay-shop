"""
lang.py
───────
Multi-language support for CayShop Bot — English (en) + Tagalog (tl).

All message strings are written in English only. When a user picks Tagalog,
strings are translated via Google Translate (free, no API key) and cached in
memory so each unique string is only translated once per bot session.

INSTALL (add to your requirements.txt / Dockerfile):
    pip install deep-translator

HOW TO USE IN main.py
──────────────────────
1.  import lang

2.  Get user's language:
        user_lang = lang.get_lang(context)

3.  Get a translated string (async — must be awaited):
        text = await lang.t("help_text", user_lang)

4.  Build a translated main menu:
        reply_markup=lang.build_main_menu(user_lang)
    (sync — menu labels are pre-defined, not translated on the fly)

5.  Detect menu button presses across both languages:
        if text in lang.ALL_MENU_BUTTONS:
            canonical = lang.normalize_menu(text)   # → always English label
            if canonical == "🛒 Products": ...

6.  On /start, show language picker if not set yet:
        if not context.user_data.get("lang"):
            await update.message.reply_text(
                "🌐 Please choose your language / Piliin ang iyong wika:",
                reply_markup=lang.LANG_PICKER_KEYBOARD,
            )
            return

7.  Handle lang_en / lang_tl callbacks (inside handle_callback):
        if data == "lang_en":
            context.user_data["lang"] = "en"
            await query.answer("Language set to English ✅")
            ...
        elif data == "lang_tl":
            context.user_data["lang"] = "tl"
            await query.answer("Wika itinakda sa Tagalog ✅")
            ...
"""

import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

logger = logging.getLogger(__name__)

# ─── TRANSLATION ENGINE ───────────────────────────────────────────────────────

_cache: dict[str, str] = {}  # "tl:<text>" → translated text


async def translate_text(text: str, dest: str = "tl") -> str:
    """
    Translate text to dest language using Google Translate (free, no API key).
    Results are cached in memory for the lifetime of the bot process.
    Falls back to the original English text if translation fails.
    """
    if dest == "en" or not text.strip():
        return text

    cache_key = f"{dest}:{text}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        from deep_translator import GoogleTranslator
        loop = asyncio.get_event_loop()
        translated = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source="en", target=dest).translate(text)
        )
        _cache[cache_key] = translated or text
        return _cache[cache_key]
    except Exception as e:
        logger.warning(f"[lang] Translation failed ({dest}): {e} — falling back to English")
        return text


async def t(key: str, lang: str = "en") -> str:
    """
    Return the translated string for the given key.
    If lang is 'en', returns the English string immediately (no network call).
    If lang is 'tl', translates via Google Translate and caches the result.
    """
    english = STRINGS.get(key, f"[{key}]")
    if lang == "en":
        return english
    return await translate_text(english, dest=lang)


# ─── LANGUAGE PICKER ─────────────────────────────────────────────────────────

LANG_PICKER_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        InlineKeyboardButton("🇵🇭 Tagalog", callback_data="lang_tl"),
    ]
])


def get_lang(context) -> str:
    """Returns the user's chosen language ('en' or 'tl'). Defaults to 'en'."""
    return context.user_data.get("lang", "en")


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
        "👋 <b>Welcome to CayShop!</b>\n\n"
        "Browse products, top up your balance, and manage your account — all from here.\n\n"
        "Use the menu below to get started."
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
}
