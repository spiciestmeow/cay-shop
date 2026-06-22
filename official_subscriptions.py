"""
official_subscriptions.py
─────────────────────────
Handles the ✅ Official Subscriptions section of the bot.

HOW TO WIRE INTO main.py  ← READ THIS OR IT WON'T WORK
────────────────────────────────────────────────────────
The easiest, safest way is to call route_callback() at the TOP of your
existing handle_callback function, before any other if/elif blocks:

    async def handle_callback(update, context):
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data

        # ── Official Subscriptions (must be first) ──
        if await official_subscriptions.route_callback(update, context):
            return

        # ... rest of your existing handler ...
        if data == "close":
            ...

WHY this is needed
──────────────────
In python-telegram-bot, handlers are checked in registration order.
Your app registers:
    app.add_handler(CallbackQueryHandler(handle_callback))   ← no pattern → catches ALL
    app.add_handler(CallbackQueryHandler(..., pattern="^official_subs$"))  ← never reached

The catch-all fires first, so the specific handlers below it are never called.
route_callback() solves this without touching your handler registration order.

ALTERNATIVE (also works)
────────────────────────
Move the 3 specific handlers BEFORE the catch-all in main():

    # specific patterns first:
    app.add_handler(CallbackQueryHandler(official_subscriptions.handle_official_subs, pattern="^official_subs$"))
    app.add_handler(CallbackQueryHandler(official_subscriptions.handle_bot_detail, pattern="^osub_detail_"))
    app.add_handler(CallbackQueryHandler(official_subscriptions.handle_subscribe, pattern="^osub_buy_"))
    # catch-all last:
    app.add_handler(CallbackQueryHandler(handle_callback))
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# ─── OFFICIAL SUBSCRIPTION BOTS ──────────────────────────────────────────────
#
# Edit each entry:
#   • "bot_link"    → real t.me/… URL to open the bot
#   • "price"       → price shown on the detail card
#   • "description" → shown before the Open Bot button
#
OFFICIAL_BOTS = [
    {
        "id": "manus",
        "emoji": "🤖",
        "name": "Manus Pro",
        "duration": "12 Months",
        "price": "$99/year",
        "description": (
            "Manus is an AI agent that can autonomously handle complex tasks — "
            "research, coding, data analysis, and more — entirely on its own.\n\n"
            "✅ Full autonomy for long tasks\n"
            "✅ Web browsing, code execution & file handling\n"
            "✅ 12-month access, all Pro features included"
        ),
        "bot_link": "https://t.me/ManusBot",
    },
    {
        "id": "cursor",
        "emoji": "💻",
        "name": "Cursor Pro",
        "duration": "12 Months",
        "price": "$192/year",
        "description": (
            "Cursor is the AI-powered code editor built for speed. "
            "Write, edit, and debug code with an assistant that understands your entire codebase.\n\n"
            "✅ GPT-4o & Claude Sonnet included\n"
            "✅ Unlimited AI completions\n"
            "✅ Codebase-aware chat & edits"
        ),
        "bot_link": "https://t.me/CursorBot",
    },
    {
        "id": "chatprd",
        "emoji": "📋",
        "name": "ChatPRD Pro",
        "duration": "12 Months",
        "price": "$120/year",
        "description": (
            "ChatPRD is the AI copilot for product managers. "
            "It writes PRDs, user stories, OKRs, and more — instantly.\n\n"
            "✅ PRD & spec generation\n"
            "✅ Product strategy coaching\n"
            "✅ Integrated with Notion, Jira & Linear"
        ),
        "bot_link": "https://t.me/ChatPRDBot",
    },
    {
        "id": "replit",
        "emoji": "🔁",
        "name": "Replit Core",
        "duration": "12 Months",
        "price": "$96/year",
        "description": (
            "Replit Core lets you build, run, and deploy apps in the browser "
            "with AI assistance. Perfect for solo devs and teams.\n\n"
            "✅ Replit AI (Agent + Assistant)\n"
            "✅ Always-on repls & deployments\n"
            "✅ Extra compute & storage"
        ),
        "bot_link": "https://t.me/ReplitBot",
    },
    {
        "id": "factory",
        "emoji": "⚙️",
        "name": "Factory Pro",
        "duration": "12 Months",
        "price": "$120/year",
        "description": (
            "Factory is the AI dev tool that automates the boring parts of engineering — "
            "code review, PR triage, refactoring, and test writing.\n\n"
            "✅ Automated PR reviews\n"
            "✅ AI-powered refactoring\n"
            "✅ GitHub & GitLab integration"
        ),
        "bot_link": "https://t.me/FactoryBot",
    },
    {
        "id": "framer",
        "emoji": "🎨",
        "name": "Framer Pro",
        "duration": "12 Months",
        "price": "$144/year",
        "description": (
            "Framer is the AI website builder that turns ideas into stunning, "
            "production-ready sites in minutes — no code required.\n\n"
            "✅ AI page generation\n"
            "✅ Custom domain & SEO tools\n"
            "✅ CMS, forms & analytics included"
        ),
        "bot_link": "https://t.me/FramerBot",
    },
    {
        "id": "granola",
        "emoji": "🥗",
        "name": "Granola Business",
        "duration": "12 Months",
        "price": "$228/year",
        "description": (
            "Granola is your AI meeting notepad. It captures everything said "
            "in meetings and turns it into clean, structured notes automatically.\n\n"
            "✅ Auto-transcription of all meetings\n"
            "✅ AI-generated summaries & action items\n"
            "✅ Integrates with Google Meet, Zoom & Teams"
        ),
        "bot_link": "https://t.me/GranolaBot",
    },
    {
        "id": "gumloop",
        "emoji": "🔗",
        "name": "Gumloop Pro",
        "duration": "12 Months",
        "price": "$120/year",
        "description": (
            "Gumloop is a no-code AI automation platform. "
            "Build powerful workflows by dragging and dropping AI nodes together.\n\n"
            "✅ Visual AI workflow builder\n"
            "✅ Connect any API or app\n"
            "✅ Run automations on a schedule or trigger"
        ),
        "bot_link": "https://t.me/GumloopBot",
    },
    {
        "id": "lovable",
        "emoji": "💖",
        "name": "Lovable Lite",
        "duration": "12 Months",
        "price": "$60/year",
        "description": (
            "Lovable is the AI full-stack engineer. "
            "Describe your app and it builds it — frontend, backend, and database.\n\n"
            "✅ Build full-stack apps in minutes\n"
            "✅ React + Supabase powered\n"
            "✅ One-click deploy to the web"
        ),
        "bot_link": "https://t.me/LovableBot",
    },
    {
        "id": "n8n",
        "emoji": "⚡",
        "name": "N8N Starter",
        "duration": "12 Months",
        "price": "$120/year",
        "description": (
            "n8n is the powerful open-source workflow automation tool. "
            "Connect 400+ apps and build complex automations with full control.\n\n"
            "✅ 400+ app integrations\n"
            "✅ Code nodes for custom logic\n"
            "✅ Self-hostable or cloud-hosted"
        ),
        "bot_link": "https://t.me/n8nBot",
    },
]

_BOT_BY_ID = {b["id"]: b for b in OFFICIAL_BOTS}


# ─── KEYBOARDS ───────────────────────────────────────────────────────────────

def build_official_subs_list_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for bot in OFFICIAL_BOTS:
        rows.append([
            InlineKeyboardButton(
                f"{bot['emoji']} {bot['name']} — {bot['duration']}",
                callback_data=f"osub_detail_{bot['id']}"
            )
        ])
    rows.append([InlineKeyboardButton("✕ Close", callback_data="close")])
    return InlineKeyboardMarkup(rows)


def build_bot_detail_keyboard(bot_id: str) -> InlineKeyboardMarkup:
    bot = _BOT_BY_ID.get(bot_id)
    if not bot:
        return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open Bot", url=bot["bot_link"])],
        [InlineKeyboardButton("💳 Subscribe via Shop", callback_data=f"osub_buy_{bot_id}")],
        [InlineKeyboardButton("⬅️ Back to list", callback_data="official_subs")],
    ])


# ─── ROUTE HELPER (call this from inside handle_callback) ────────────────────

async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Call at the very top of your existing handle_callback():

        if await official_subscriptions.route_callback(update, context):
            return

    Returns True if the callback was handled here (so handle_callback can return early).
    Returns False if it's not an official-subs callback (handle_callback continues normally).
    """
    query = update.callback_query
    data = query.data or ""

    if data == "official_subs":
        await handle_official_subs(update, context)
        return True

    if data.startswith("osub_detail_"):
        await handle_bot_detail(update, context)
        return True

    if data.startswith("osub_buy_"):
        await handle_subscribe(update, context)
        return True

    return False


# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def handle_official_subs(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📋 Choose a product:",
        parse_mode="HTML",
        reply_markup=build_official_subs_list_keyboard(),
    )


async def handle_bot_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    bot_id = query.data.replace("osub_detail_", "")
    bot = _BOT_BY_ID.get(bot_id)
    if not bot:
        await query.answer("Bot not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"{bot['emoji']} <b>{bot['name']}</b>\n"
        f"⏳ <b>Duration:</b> {bot['duration']}\n"
        f"💰 <b>Price:</b> {bot['price']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{bot['description']}",
        parse_mode="HTML",
        reply_markup=build_bot_detail_keyboard(bot_id),
    )


async def handle_subscribe(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    bot_id = query.data.replace("osub_buy_", "")
    bot = _BOT_BY_ID.get(bot_id)
    if not bot:
        await query.answer("Bot not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"🛒 <b>Purchase {bot['name']}</b>\n\n"
        f"To subscribe, head to <b>🛒 Products</b> from the main menu "
        f"and look for <b>{bot['name']} — {bot['duration']}</b>.\n\n"
        f"Need help? Contact @caydigitals",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"osub_detail_{bot_id}")],
            [InlineKeyboardButton("✕ Close", callback_data="close")],
        ]),
    )
