import os
import requests
import json
from datetime import datetime
from io import BytesIO
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import telebot
import time

# ── Put your bot token here ──────────────────────────────────────────
BOT_TOKEN = ""
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


def format_info_text(user, data, formatted_time, photo, status_obj):
    thumb = photo.get("strippedThumb") if photo else None

    text = f"""
- Status: {data.get('status')}
- Constructor ID: {user.get('CONSTRUCTOR_ID')}
- Subclass ID: {user.get('SUBCLASS_OF_ID')}
- Class Name: {user.get('className')}
- Class Type: {user.get('classType')}
- ID: {user.get('id')}
- Access Hash: {user.get('accessHash')}
- First Name: {user.get('firstName') or 'None'}
- Last Name: {user.get('lastName') or 'None'}
- Full Name: {user.get('fullname') or 'None'}
- Username: @{user.get('username')}
- Phone: {user.get('phone') or 'Hidden'}
- Bio: {user.get('bio') or 'Empty'}
- Flags: {user.get('flags')}
- Flags2: {user.get('flags2')}
- Is Self: {'Yes' if user.get('self') else 'No'}
- Is Contact: {'Yes' if user.get('contact') else 'No'}
- Mutual Contact: {'Yes' if user.get('mutualContact') else 'No'}
- Deleted: {'Yes' if user.get('deleted') else 'No'}
- Is Bot: {'Yes' if user.get('bot') else 'No'}
- Bot Chat History: {'Yes' if user.get('botChatHistory') else 'No'}
- Bot No Chats: {'Yes' if user.get('botNochats') else 'No'}
- Verified: {'Yes' if user.get('verified') else 'No'}
- Restricted: {'Yes' if user.get('restricted') else 'No'}
- Min: {'Yes' if user.get('min') else 'No'}
- Bot Inline Geo: {'Yes' if user.get('botInlineGeo') else 'No'}
- Support: {'Yes' if user.get('support') else 'No'}
- Scam: {'Yes' if user.get('scam') else 'No'}
- Apply Min Photo: {'Yes' if user.get('applyMinPhoto') else 'No'}
- Fake: {'Yes' if user.get('fake') else 'No'}
- Bot Attach Menu: {'Yes' if user.get('botAttachMenu') else 'No'}
- Premium: {'Yes' if user.get('premium') else 'No'}
- Attach Menu Enabled: {'Yes' if user.get('attachMenuEnabled') else 'No'}
- Bot Can Edit: {'Yes' if user.get('botCanEdit') else 'No'}
- Close Friend: {'Yes' if user.get('closeFriend') else 'No'}
- Stories Hidden: {'Yes' if user.get('storiesHidden') else 'No'}
- Stories Unavailable: {'Yes' if user.get('storiesUnavailable') else 'No'}
- Contact Require Premium: {'Yes' if user.get('contactRequirePremium') else 'No'}
- Bot Business: {'Yes' if user.get('botBusiness') else 'No'}
- Bot Has Main App: {'Yes' if user.get('botHasMainApp') else 'No'}
- Photo Flags: {photo.get('flags') if photo else 'None'}
- Has Video: {'Yes' if photo.get('hasVideo') else 'No' if photo else 'None'}
- Personal Photo: {'Yes' if photo.get('personal') else 'No' if photo else 'None'}
- Photo ID: {photo.get('photoId') if photo else 'None'}
- DC ID: {photo.get('dcId') if photo else 'None'}
- Photo Class: {photo.get('className') if photo else 'None'}
- Thumb Type: {thumb.get('type') if thumb else 'None'}
- Status Class: {status_obj.get('className') if status_obj else 'Unknown'}
- Last Seen: {formatted_time or 'Unknown'}
- Bot Info Version: {user.get('botInfoVersion') or 'Empty'}
- Restriction Reason: {user.get('restrictionReason') or 'Empty'}
- Bot Inline Placeholder: {user.get('botInlinePlaceholder') or 'Empty'}
- Language Code: {user.get('langCode') or 'Empty'}
- Emoji Status: {user.get('emojiStatus') or 'Empty'}
- Usernames: {user.get('usernames') or 'Empty'}
- Stories Max ID: {user.get('storiesMaxId') or 'Empty'}
- Account Color: {user.get('color') or 'Empty'}
- Profile Color: {user.get('profileColor') or 'Empty'}
- Active Users: {user.get('botActiveUsers') or 'Empty'}
- Bot Verification Icon: {user.get('botVerificationIcon') or 'Empty'}
    """
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
                        caption=info_text[:1020],
                        reply_markup=keyboard
                    )
                    if len(info_text) > 1020:
                        remaining = info_text[1020:]
                        parts = split_text(remaining)
                        for part in parts:
                            bot.send_message(message.chat.id, part)
                    return
            except Exception:
                pass

        parts = split_text(info_text)
        for i, part in enumerate(parts):
            if i == 0:
                bot.send_message(message.chat.id, part, reply_markup=keyboard)
            else:
                bot.send_message(message.chat.id, part)

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
                            caption=info_text[:1020],
                            reply_markup=keyboard
                        )
                        if len(info_text) > 1020:
                            remaining = info_text[1020:]
                            parts = split_text(remaining)
                            for part in parts:
                                bot.send_message(call.message.chat.id, part)
                        return
                except Exception:
                    pass

            parts = split_text(info_text)
            for i, part in enumerate(parts):
                if i == 0:
                    bot.send_message(call.message.chat.id, part, reply_markup=keyboard)
                else:
                    bot.send_message(call.message.chat.id, part)

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