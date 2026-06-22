import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import db

logger = logging.getLogger(__name__)

# ─── CALLBACK PREFIX ─────────────────────────────────────────────────────────
CB_BAN_START    = "ban_start"
CB_BAN_CONFIRM  = "ban_confirm_"       # ban_confirm_{user_id}
CB_UNBAN_CONFIRM = "unban_confirm_"    # unban_confirm_{user_id}
CB_BAN_BACK     = "ban_back"


# ─── ENTRY POINT (called from admin panel button) ────────────────────────────

async def show_ban_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the ban/unban input prompt."""
    query = update.callback_query
    user_id = update.effective_user.id

    await db.set_session(user_id, {"awaiting": "ban_user_id"})
    await query.answer()
    await query.message.reply_text(
        "🚫 <b>Ban / Unban User</b>\n\n"
        "Send the <b>Telegram user ID</b> of the user you want to ban or unban.\n\n"
        "<i>You can find a user's ID from their profile in the bot or from the orders log.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✕ Cancel", callback_data=CB_BAN_BACK)],
        ]),
    )


# ─── HANDLE TEXT INPUT (user_id entry) ───────────────────────────────────────

async def handle_ban_input(update: Update, context: ContextTypes.DEFAULT_TYPE, ud: dict) -> bool:
    """
    Called from main._process_admin_input when awaiting == 'ban_user_id'.
    Returns True if handled, False to fall through.
    """
    text = update.message.text.strip() if update.message.text else ""

    try:
        target_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid ID. Please send a numeric Telegram user ID:"
        )
        return True

    target_user = await db.get_user(target_id)
    if not target_user:
        await update.message.reply_text(
            "❌ No user found with that ID. Make sure they've started the bot at least once.\n\n"
            "Send the user ID again, or tap Cancel.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✕ Cancel", callback_data=CB_BAN_BACK)],
            ]),
        )
        return True

    await db.clear_session(update.effective_user.id)

    is_banned = bool(target_user.get("is_banned", False))
    name = target_user.get("full_name") or "Unknown"
    username = f"@{target_user['username']}" if target_user.get("username") else "no username"

    if is_banned:
        action_text  = "✅ <b>Unban</b> this user?"
        action_label = "✅ Yes, unban"
        action_cb    = f"{CB_UNBAN_CONFIRM}{target_id}"
        status_line  = "⛔ Status: <b>Currently BANNED</b>"
    else:
        action_text  = "🚫 <b>Ban</b> this user?"
        action_label = "🚫 Yes, ban"
        action_cb    = f"{CB_BAN_CONFIRM}{target_id}"
        status_line  = "✅ Status: <b>Currently active</b>"

    await update.message.reply_text(
        f"👤 <b>User found</b>\n\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"👤 Name: {name}\n"
        f"🔗 Username: {username}\n"
        f"💰 Balance: ${float(target_user.get('balance', 0)):.2f}\n"
        f"{status_line}\n\n"
        f"{action_text}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(action_label, callback_data=action_cb)],
            [InlineKeyboardButton("✕ Cancel", callback_data=CB_BAN_BACK)],
        ]),
    )
    return True


# ─── CALLBACK HANDLER ────────────────────────────────────────────────────────

async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Route ban-related callbacks. Returns True if handled.
    Call this near the top of main.handle_callback.
    """
    query = update.callback_query
    data  = query.data

    if data == CB_BAN_BACK:
        await db.clear_session(update.effective_user.id)
        await query.answer("Cancelled.")
        await query.message.delete()
        return True

    if data.startswith(CB_BAN_CONFIRM):
        target_id = int(data[len(CB_BAN_CONFIRM):])
        await _do_ban(update, context, target_id, ban=True)
        return True

    if data.startswith(CB_UNBAN_CONFIRM):
        target_id = int(data[len(CB_UNBAN_CONFIRM):])
        await _do_ban(update, context, target_id, ban=False)
        return True

    if data == CB_BAN_START:
        await show_ban_panel(update, context)
        return True

    return False


# ─── INTERNAL HELPERS ─────────────────────────────────────────────────────────

async def _do_ban(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_id: int,
    ban: bool,
) -> None:
    query = update.callback_query

    try:
        db._client().table(db.USERS_TABLE).update({"is_banned": ban}).eq("user_id", target_id).execute()
    except Exception as e:
        logger.error(f"Failed to {'ban' if ban else 'unban'} user {target_id}: {e}", exc_info=e)
        await query.answer("❌ Database error. Please try again.", show_alert=True)
        return

    action_word = "banned" if ban else "unbanned"
    icon        = "🚫" if ban else "✅"

    await query.answer(f"{icon} User {action_word}!", show_alert=True)
    await query.message.edit_text(
        f"{icon} <b>User {action_word}.</b>\n\n"
        f"🆔 User ID: <code>{target_id}</code>\n\n"
        + (
            "<i>They will now receive a blocked message when they try to use the bot.</i>"
            if ban else
            "<i>They can now use the bot again.</i>"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Ban/Unban another", callback_data=CB_BAN_START)],
            [InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_main")],
        ]),
    )

    # Notify the affected user
    try:
        if ban:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "🚫 <b>Your account has been suspended.</b>\n\n"
                    "You are no longer able to use this bot.\n"
                    "If you believe this is a mistake, please contact support."
                ),
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "✅ <b>Your account has been reinstated.</b>\n\n"
                    "You can now use the bot again. Welcome back!"
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        logger.warning(f"Could not notify user {target_id} of ban status change: {e}")


# ─── GATE CHECK (call this inside handle_message & handle_callback) ───────────

async def is_user_banned(user_id: int) -> bool:
    """Returns True if the user is banned. Use this as a gate in main.py."""
    user = await db.get_user(user_id)
    if not user:
        return False
    return bool(user.get("is_banned", False))


BANNED_MESSAGE = (
    "🚫 <b>Your account has been suspended.</b>\n\n"
    "You are no longer able to use this bot.\n"
    "If you believe this is a mistake, please contact support."
)