import os
import requests
import json
from datetime import datetime
from io import BytesIO
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import telebot
import time
import re

# ── Put your bot token here ──────────────────────────────────────────
BOT_TOKEN = "8542796779:AAHfiUbwpcJzxizbt2QbY_GAXcA9ePCDlZI"
# ─────────────────────────────────────────────────────────────────────

bot = telebot.TeleBot(BOT_TOKEN)

url = "https://www.telegram-finder.io/api/telegram/username/check"
headers = {
    'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    'Accept': "application/json",
    'Content-Type': "application/json",
    'sec-ch-ua-platform': "\"Android\"",
    'sec-ch-ua': "\"Google Chrome\";v=\"149\", \"Chromium\";v=\"149\", \"Not)A;Brand\";v=\"24\"",
    'sec-ch-ua-mobile': "?1",
    'origin': "https://www.telegram-finder.io",
    'sec-fetch-site': "same-origin",
    'sec-fetch-mode': "cors",
    'sec-fetch-dest': "empty",
    'accept-language': "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    'priority': "u=1, i",
}


def get_user_data(username):
    payload = {"username": username}
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        return response.json()
    except Exception:
        return None


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text)


def split_text(text, limit=4000):
    parts = []
    while len(text) > limit:
        split_point = text.rfind('\n', 0, limit)
        if split_point == -1:
            split_point = limit
        parts.append(text[:split_point])
        text = text[split_point:]
    parts.append(text)
    return parts


def esc(val):
    if val is None:
        return '—'
    return str(val).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def yesno(val):
    return '✅ Yes' if val else '❌ No'


def format_info_text(user, data, formatted_time, photo, status_obj):
    thumb = photo.get("strippedThumb") if photo else None

    name = f"{user.get('firstName') or ''} {user.get('lastName') or ''}".strip() or "Unknown"

    dc_id = photo.get('dcId') if photo else None
    dc_map = {1: "DC1 · Miami", 2: "DC2 · Amsterdam", 3: "DC3 · Miami",
              4: "DC4 · Amsterdam", 5: "DC5 · Singapore"}
    dc_label = dc_map.get(dc_id, f"DC{dc_id}") if dc_id else "—"

    status_class = esc(status_obj.get('className') if status_obj else 'Unknown')

    # Handle emoji status (can be a dict)
    emoji_status = user.get('emojiStatus')
    if isinstance(emoji_status, dict):
        emoji_doc = esc(emoji_status.get('documentId'))
    else:
        emoji_doc = '—'

    # Handle profile color (can be a dict)
    profile_color = user.get('profileColor')
    if isinstance(profile_color, dict):
        profile_color_val = esc(str(profile_color.get('color', '—')))
        profile_bg = esc(profile_color.get('backgroundEmojiId'))
    else:
        profile_color_val = '—'
        profile_bg = '—'

    text = (
        f"👤 <b>{esc(name)}</b>\n\n"

        f"<b>━━ General ━━</b>\n"
        f"<b>Status:</b> {esc(data.get('status'))}\n"
        f"<b>Constructor ID:</b> <code>{esc(user.get('CONSTRUCTOR_ID'))}</code>\n"
        f"<b>Subclass ID:</b> <code>{esc(user.get('SUBCLASS_OF_ID'))}</code>\n"
        f"<b>Class name:</b> {esc(user.get('className'))}\n"
        f"<b>Class type:</b> {esc(user.get('classType'))}\n\n"

        f"<b>━━ Identity ━━</b>\n"
        f"<b>ID:</b> <code>{esc(user.get('id'))}</code>\n"
        f"<b>Access hash:</b> <code>{esc(user.get('accessHash'))}</code>\n"
        f"<b>First name:</b> {esc(user.get('firstName'))}\n"
        f"<b>Last name:</b> {esc(user.get('lastName'))}\n"
        f"<b>Full name:</b> {esc(user.get('fullname'))}\n"
        f"<b>Username:</b> @{esc(user.get('username'))}\n"
        f"<b>Phone:</b> {esc(user.get('phone')) if user.get('phone') else 'Hidden'}\n"
        f"<b>Bio:</b> {esc(user.get('bio')) if user.get('bio') else 'Empty'}\n"
        f"<b>Language:</b> {esc(user.get('langCode'))}\n"
        f"<b>Usernames:</b> {esc(user.get('usernames'))}\n\n"

        f"<b>━━ Status ━━</b>\n"
        f"<b>Last seen:</b> {esc(formatted_time) if formatted_time else 'Unknown'}\n"
        f"<b>Status class:</b> {status_class}\n"
        f"<b>Data center:</b> {dc_label}\n\n"

        f"<b>━━ Flags ━━</b>\n"
        f"<b>Flags:</b> <code>{esc(user.get('flags'))}</code>  <b>Flags2:</b> <code>{esc(user.get('flags2'))}</code>\n"
        f"{yesno(user.get('self'))} Self   {yesno(user.get('contact'))} Contact\n"
        f"{yesno(user.get('mutualContact'))} Mutual contact   {yesno(user.get('min'))} Min\n"
        f"{yesno(user.get('deleted'))} Deleted   {yesno(user.get('verified'))} Verified\n"
        f"{yesno(user.get('premium'))} Premium   {yesno(user.get('support'))} Support\n"
        f"{yesno(user.get('scam'))} Scam   {yesno(user.get('fake'))} Fake\n"
        f"{yesno(user.get('restricted'))} Restricted   {yesno(user.get('applyMinPhoto'))} Apply min photo\n"
        f"{yesno(user.get('closeFriend'))} Close friend   {yesno(user.get('contactRequirePremium'))} Req. premium\n"
        f"{yesno(user.get('storiesHidden'))} Stories hidden   {yesno(user.get('storiesUnavailable'))} Stories unavail.\n"
        f"<b>Stories max ID:</b> {esc(user.get('storiesMaxId'))}\n\n"

        f"<b>━━ Bot flags ━━</b>\n"
        f"{yesno(user.get('bot'))} Bot   {yesno(user.get('botChatHistory'))} Chat history\n"
        f"{yesno(user.get('botNochats'))} No chats   {yesno(user.get('botInlineGeo'))} Inline geo\n"
        f"{yesno(user.get('botAttachMenu'))} Attach menu   {yesno(user.get('attachMenuEnabled'))} Menu enabled\n"
        f"{yesno(user.get('botCanEdit'))} Can edit   {yesno(user.get('botBusiness'))} Business\n"
        f"{yesno(user.get('botHasMainApp'))} Has main app\n"
        f"<b>Bot info version:</b> {esc(user.get('botInfoVersion'))}\n"
        f"<b>Inline placeholder:</b> {esc(user.get('botInlinePlaceholder'))}\n"
        f"<b>Active users:</b> {esc(user.get('botActiveUsers'))}\n"
        f"<b>Verification icon:</b> {esc(user.get('botVerificationIcon'))}\n\n"

        f"<b>━━ Photo ━━</b>\n"
        f"<b>Photo ID:</b> <code>{esc(photo.get('photoId') if photo else None)}</code>\n"
        f"<b>Photo class:</b> {esc(photo.get('className') if photo else None)}\n"
        f"<b>Photo flags:</b> {esc(photo.get('flags') if photo else None)}\n"
        f"<b>DC:</b> {dc_label}\n"
        f"<b>Thumb type:</b> {esc(thumb.get('type') if thumb else None)}\n"
        f"{yesno(photo.get('hasVideo') if photo else False)} Has video   "
        f"{yesno(photo.get('personal') if photo else False)} Personal photo\n\n"

        f"<b>━━ Extra ━━</b>\n"
        f"<b>Emoji status ID:</b> <code>{emoji_doc}</code>\n"
        f"<b>Account color:</b> {esc(user.get('color'))}\n"
        f"<b>Profile color:</b> {profile_color_val}  <b>BG emoji:</b> <code>{profile_bg}</code>\n"
        f"<b>Restriction reason:</b> {esc(user.get('restrictionReason'))}\n"
    )
    return text


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn1 = InlineKeyboardButton("🔍 Search User", callback_data="search")
    btn2 = InlineKeyboardButton("❓ Help", callback_data="help")
    btn3 = InlineKeyboardButton("❌ Close", callback_data="close")
    keyboard.add(btn1, btn2, btn3)

    bot.reply_to(
        message,
        "Welcome to the Telegram User Info Bot!\n\n"
        "Send a username (example: @username)\n"
        "or click the Search button.",
        reply_markup=keyboard
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    btn1 = InlineKeyboardButton("🔍 Search", callback_data="search")
    btn2 = InlineKeyboardButton("❌ Close", callback_data="close")
    keyboard.add(btn1, btn2)

    bot.reply_to(
        message,
        "📚 Help Menu\n\n"
        "How to use:\n"
        "1- Send a username (e.g. @username)\n"
        "2- Wait for the data to load\n"
        "3- Interact using the buttons\n\n"
        "Buttons:\n"
        "- Refresh: Update the info\n"
        "- Share: Share the user\n"
        "- Detail: Extra info\n"
        "- Close: Delete the message\n\n"
        "Notes:\n"
        "- The bot does not store data\n"
        "- All info is from a public API\n"
        "- Some fields may not exist for all users",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    username = message.text.strip()
    if username.startswith('@'):
        username = username[1:]

    msg = bot.reply_to(message, "🔍 Searching for user...")

    try:
        data = get_user_data(username)

        if not data or not data.get('user'):
            bot.edit_message_text(
                f"❌ @{username} not found!\n\nCheck the username and try again.",
                message.chat.id,
                msg.message_id
            )
            return

        user = data.get('user')
        photo = user.get("photo")
        status_obj = user.get("status")
        timestamp = status_obj.get("wasOnline") if status_obj else None
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else None

        info_text = format_info_text(user, data, formatted_time, photo, status_obj)

        keyboard = InlineKeyboardMarkup(row_width=2)
        btn1 = InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{username}")
        btn2 = InlineKeyboardButton("📤 Share", callback_data=f"share_{username}")
        btn3 = InlineKeyboardButton("ℹ️ Detail", callback_data=f"more_{username}")
        btn4 = InlineKeyboardButton("❌ Close", callback_data="close")
        keyboard.add(btn1, btn2)
        keyboard.add(btn3, btn4)

        bot.delete_message(message.chat.id, msg.message_id)

        img_url = user.get('imgUrl')
        if img_url:
            try:
                response = requests.get(img_url, timeout=15)
                if response.status_code == 200:
                    photo_file = BytesIO(response.content)
                    bot.send_photo(
                        message.chat.id,
                        photo=photo_file,
                        caption=strip_html(info_text)[:1020],
                        reply_markup=keyboard
                    )
                    parts = split_text(info_text)
                    for part in parts:
                        bot.send_message(message.chat.id, part, parse_mode='HTML')
                    return
            except Exception:
                pass

        parts = split_text(info_text)
        for i, part in enumerate(parts):
            if i == 0:
                bot.send_message(message.chat.id, part, reply_markup=keyboard, parse_mode='HTML')
            else:
                bot.send_message(message.chat.id, part, parse_mode='HTML')

    except Exception as e:
        try:
            bot.edit_message_text(
                f"❌ Error: {str(e)[:100]}\n\nPlease try again.",
                message.chat.id,
                msg.message_id
            )
        except Exception:
            bot.reply_to(message, "❌ An unexpected error occurred, please try again.")


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    if data == "search":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(
            call.message.chat.id,
            "🔍 Send a username\n\nExample: @username"
        )

    elif data == "help":
        keyboard = InlineKeyboardMarkup(row_width=2)
        btn1 = InlineKeyboardButton("🔍 Search", callback_data="search")
        btn2 = InlineKeyboardButton("❌ Close", callback_data="close")
        keyboard.add(btn1, btn2)

        bot.edit_message_text(
            "📚 Help Menu\n\n"
            "How to use:\n"
            "1- Send a username (e.g. @username)\n"
            "2- Wait for the data to load\n"
            "3- Interact using the buttons\n\n"
            "Buttons:\n"
            "- Refresh: Update the info\n"
            "- Share: Share the user\n"
            "- Detail: Extra info\n"
            "- Close: Delete the message\n\n"
            "Notes:\n"
            "- The bot does not store data\n"
            "- All info is from a public API",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )

    elif data == "close":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif data.startswith("more_"):
        username = data.replace("more_", "")
        keyboard = InlineKeyboardMarkup(row_width=1)
        btn1 = InlineKeyboardButton("❌ Close", callback_data="close")
        keyboard.add(btn1)

        detail_text = (
            f"ℹ️ About @{username}\n\n"
            "• This bot shows all available public info.\n"
            "• Use 'Refresh' to update the data.\n"
            "• All data is fetched from a public API.\n\n"
            "Note: Some fields may not be available for all users."
        )

        try:
            bot.edit_message_text(
                detail_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
        except Exception:
            try:
                bot.edit_message_caption(
                    caption=detail_text,
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=keyboard
                )
            except Exception:
                bot.send_message(
                    call.message.chat.id,
                    detail_text,
                    reply_markup=keyboard
                )

    elif data.startswith("refresh_"):
        username = data.replace("refresh_", "")

        try:
            bot.edit_message_text(
                f"🔄 Refreshing @{username}...",
                call.message.chat.id,
                call.message.message_id
            )
        except Exception:
            bot.send_message(call.message.chat.id, f"🔄 Refreshing @{username}...")

        try:
            new_data = get_user_data(username)

            if not new_data or not new_data.get('user'):
                bot.send_message(
                    call.message.chat.id,
                    f"❌ Could not refresh @{username}!\n\nUser may have been deleted or does not exist."
                )
                return

            user = new_data.get('user')
            photo = user.get("photo")
            status_obj = user.get("status")
            timestamp = status_obj.get("wasOnline") if status_obj else None
            formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else None

            info_text = format_info_text(user, new_data, formatted_time, photo, status_obj)

            keyboard = InlineKeyboardMarkup(row_width=2)
            btn1 = InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{username}")
            btn2 = InlineKeyboardButton("📤 Share", callback_data=f"share_{username}")
            btn3 = InlineKeyboardButton("ℹ️ Detail", callback_data=f"more_{username}")
            btn4 = InlineKeyboardButton("❌ Close", callback_data="close")
            keyboard.add(btn1, btn2)
            keyboard.add(btn3, btn4)

            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass

            img_url = user.get('imgUrl')
            if img_url:
                try:
                    response = requests.get(img_url, timeout=15)
                    if response.status_code == 200:
                        photo_file = BytesIO(response.content)
                        bot.send_photo(
                            call.message.chat.id,
                            photo=photo_file,
                            caption=strip_html(info_text)[:1020],
                            reply_markup=keyboard
                        )
                        parts = split_text(info_text)
                        for part in parts:
                            bot.send_message(call.message.chat.id, part, parse_mode='HTML')
                        return
                except Exception:
                    pass

            parts = split_text(info_text)
            for i, part in enumerate(parts):
                if i == 0:
                    bot.send_message(call.message.chat.id, part, reply_markup=keyboard, parse_mode='HTML')
                else:
                    bot.send_message(call.message.chat.id, part, parse_mode='HTML')

        except Exception as e:
            bot.send_message(
                call.message.chat.id,
                f"❌ Refresh error: {str(e)[:100]}"
            )

    elif data.startswith("share_"):
        username = data.replace("share_", "")
        share_text = f"📤 Telegram User: @{username}\n\nGet detailed info using this bot."

        keyboard = InlineKeyboardMarkup(row_width=1)
        btn1 = InlineKeyboardButton("❌ Close", callback_data="close")
        keyboard.add(btn1)

        try:
            bot.edit_message_text(
                f"📤 Share\n\nCopy this text and share it:\n\n{share_text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
        except Exception:
            try:
                bot.edit_message_caption(
                    caption=f"📤 Share\n\nCopy this text and share it:\n\n{share_text}",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=keyboard
                )
            except Exception:
                bot.send_message(
                    call.message.chat.id,
                    f"📤 Share\n\n{share_text}",
                    reply_markup=keyboard
                )


print("Bot is running...")

while True:
    try:
        bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
    except Exception:
        time.sleep(5)