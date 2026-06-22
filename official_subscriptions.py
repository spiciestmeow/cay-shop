"""
official_subscriptions.py
─────────────────────────
Handles the ✅ Official Subscriptions section of the bot.

HOW TO WIRE INTO main.py
────────────────────────
1.  Import at the top of main.py:
        import official_subscriptions

2.  Change the "Official Subscriptions" button callback_data from "noop" to
    "official_subs":
        InlineKeyboardButton("✅ Official Subscriptions",
                             callback_data="official_subs")

3.  Register the handlers inside your `main()` / ApplicationBuilder block:
        app.add_handler(CallbackQueryHandler(
            official_subscriptions.handle_official_subs,
            pattern="^official_subs$"
        ))
        app.add_handler(CallbackQueryHandler(
            official_subscriptions.handle_bot_detail,
            pattern="^osub_detail_"
        ))
        app.add_handler(CallbackQueryHandler(
            official_subscriptions.handle_subscribe,
            pattern="^osub_buy_"
        ))
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

# ─── OFFICIAL SUBSCRIPTION BOTS ──────────────────────────────────────────────
#
# Fill in:
#   • "bot_link"  → the t.me/… URL users should be redirected to
#   • "price"     → displayed price (string, e.g. "$15/mo" or "$99/yr")
#   • "duration"  → subscription length shown on the detail card
#   • "description" → shown on the detail card before the Open button
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
        "bot_link": "https://t.me/ManusBot",  # ← replace with real link
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
        "bot_link": "https://t.me/CursorBot",  # ← replace with real link
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
        "bot_link": "https://t.me/ChatPRDBot",  # ← replace with real link
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
        "bot_link": "https://t.me/ReplitBot",  # ← replace with real link
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
        "bot_link": "https://t.me/FactoryBot",  # ← replace with real link
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
        "bot_link": "https://t.me/FramerBot",  # ← replace with real link
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
        "bot_link": "https://t.me/GranolaBot",  # ← replace with real link
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
        "bot_link": "https://t.me/GumloopBot",  # ← replace with real link
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
        "bot_link": "https://t.me/LovableBot",  # ← replace with real link
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
        "bot_link": "https://t.me/n8nBot",  # ← replace with real link
    },
]

# Build a lookup dict for fast access by id
_BOT_BY_ID = {b["id"]: b for b in OFFICIAL_BOTS}


# ─── KEYBOARDS ───────────────────────────────────────────────────────────────

def build_official_subs_list_keyboard() -> InlineKeyboardMarkup:
    """Main list: one button per bot."""
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
    """Detail view: Open Bot link + Subscribe + Back."""
    bot = _BOT_BY_ID.get(bot_id)
    if not bot:
        return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open Bot", url=bot["bot_link"])],
        [InlineKeyboardButton("💳 Subscribe via Shop", callback_data=f"osub_buy_{bot_id}")],
        [InlineKeyboardButton("⬅️ Back to list", callback_data="official_subs")],
    ])


# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def handle_official_subs(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Triggered by callback_data='official_subs'.
    Shows the full list of official subscription bots."""
    query = update.callback_query
    await query.answer()

    text = (
        "✅ <b>Official Subscriptions</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Choose a subscription to see its description and open the bot:"
    )
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=build_official_subs_list_keyboard(),
    )


async def handle_bot_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Triggered by callback_data='osub_detail_<id>'.
    Shows the bot description, an Open Bot button, and a Subscribe button."""
    query = update.callback_query
    await query.answer()

    bot_id = query.data.replace("osub_detail_", "")
    bot = _BOT_BY_ID.get(bot_id)
    if not bot:
        await query.answer("Bot not found.", show_alert=True)
        return

    text = (
        f"{bot['emoji']} <b>{bot['name']}</b>\n"
        f"⏳ <b>Duration:</b> {bot['duration']}\n"
        f"💰 <b>Price:</b> {bot['price']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{bot['description']}"
    )
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=build_bot_detail_keyboard(bot_id),
    )


async def handle_subscribe(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Triggered by callback_data='osub_buy_<id>'.
    Redirects user to the Products section to complete the purchase
    (you can replace this with a direct purchase flow if preferred)."""
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
