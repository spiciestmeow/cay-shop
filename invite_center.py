"""
invite_center.py — Referral program: unique invite links, a funnel of
qualification stages, and an automatic $1-per-10-qualified-invites reward.

FUNNEL (per referred user):
    sign_up              → they /start'd via someone's ref_XXXX link
    awaiting_captcha      → must solve a math CAPTCHA (5 choices)
    awaiting_join          → must pass the membership gate (group+channel)
    awaiting_interaction   → must send 1 message / tap 1 button after joining
    qualified               → counts toward the referrer's reward batch

REWARD: every 10th qualified invite (per referrer) auto-credits $1 to the
referrer's balance. Guarded so a batch can only be rewarded once.

DB TABLE REQUIRED (Supabase):

    create table cay_shop_invites (
        id              bigserial primary key,
        referrer_id     bigint not null,
        referred_id     bigint not null unique,
        ref_code        text not null,
        stage           text not null default 'awaiting_captcha',
        qualified_at    timestamptz,
        created_at      timestamptz not null default now()
    );
    create index on cay_shop_invites (referrer_id);
    create index on cay_shop_invites (referred_id);

WIRING REQUIRED in main.py — see the bottom of this file.
"""

import logging
import random
import string
import os

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import db
import membership_gate

CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004441073113")

logger = logging.getLogger(__name__)

# ─── CONFIG ─────────────────────────────────────────────────────────────────

QUALIFIED_PER_REWARD = 10
REWARD_USD           = 1.00

STAGE_SIGNED_UP            = "awaiting_captcha"
STAGE_AWAITING_JOIN        = "awaiting_join"
STAGE_AWAITING_INTERACTION = "awaiting_interaction"
STAGE_QUALIFIED            = "qualified"

INVITES_TABLE = "cay_shop_invites"

# ─── MATH CAPTCHA CONFIG ────────────────────────────────────────────────────

# Operators available for CAPTCHA questions
CAPTCHA_OPERATORS = ["+", "-", "×"]

# Number ranges per operator  (a OP b, answer always stays positive)
CAPTCHA_NUM_RANGE = (1, 12)

# How many answer choices to show (including the correct one)
CAPTCHA_NUM_CHOICES = 5

# Callback prefix for captcha answers
CAPTCHA_CB_PREFIX = "captcha_ans_"
CAPTCHA_CB_RETRY  = "captcha_retry"


def _client():
    return db._client()


# ─── REF CODE / LINK HELPERS ──────────────────────────────────────────────

def generate_ref_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


async def get_or_create_ref_code(user_id: int) -> str:
    """Each user gets one persistent ref code, stored on their user row."""
    user = await db.get_user(user_id)
    existing = (user or {}).get("ref_code")
    if existing:
        return existing

    code = generate_ref_code()
    c = _client()
    # Guard against (extremely unlikely) collisions.
    while c.table(db.USERS_TABLE).select("user_id").eq("ref_code", code).execute().data:
        code = generate_ref_code()

    c.table(db.USERS_TABLE).update({"ref_code": code}).eq("user_id", user_id).execute()
    return code


async def get_invite_link(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    code = await get_or_create_ref_code(user_id)
    bot_username = (await context.bot.get_me()).username
    return f"https://t.me/{bot_username}?start=ref_{code}"


async def get_referrer_id_by_code(ref_code: str) -> int | None:
    c = _client()
    res = c.table(db.USERS_TABLE).select("user_id").eq("ref_code", ref_code).limit(1).execute()
    return res.data[0]["user_id"] if res.data else None


# ─── INVITE RECORD HELPERS ──────────────────────────────────────────────────

async def get_invite(referred_id: int) -> dict | None:
    c = _client()
    res = c.table(INVITES_TABLE).select("*").eq("referred_id", referred_id).limit(1).execute()
    return res.data[0] if res.data else None


async def create_invite(referrer_id: int, referred_id: int, ref_code: str) -> None:
    c = _client()
    c.table(INVITES_TABLE).insert({
        "referrer_id":  referrer_id,
        "referred_id":  referred_id,
        "ref_code":     ref_code,
        "stage":        STAGE_SIGNED_UP,
    }).execute()


async def set_invite_stage(referred_id: int, stage: str) -> None:
    c = _client()
    updates = {"stage": stage}
    if stage == STAGE_QUALIFIED:
        from datetime import datetime
        updates["qualified_at"] = datetime.utcnow().isoformat()
    c.table(INVITES_TABLE).update(updates).eq("referred_id", referred_id).execute()


async def get_invites_for_referrer(referrer_id: int) -> list[dict]:
    c = _client()
    res = c.table(INVITES_TABLE).select("*").eq("referrer_id", referrer_id).execute()
    return res.data or []


# ─── MATH CAPTCHA HELPERS ────────────────────────────────────────────────────

def _generate_captcha() -> dict:
    """
    Returns a dict with:
        question  : str  e.g. "7 + 5"
        answer    : int  e.g. 12
        choices   : list[int]  5 shuffled options including the correct answer
    """
    op = random.choice(CAPTCHA_OPERATORS)
    lo, hi = CAPTCHA_NUM_RANGE
    a = random.randint(lo, hi)
    b = random.randint(lo, hi)

    if op == "+":
        answer = a + b
    elif op == "-":
        # Keep answer positive: ensure a >= b
        if a < b:
            a, b = b, a
        answer = a - b
    else:  # ×
        # Keep numbers small for multiplication so it stays reasonable
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        answer = a * b

    question = f"{a} {op} {b}"

    # Build 4 unique wrong answers near the correct one
    wrong = set()
    attempts = 0
    while len(wrong) < CAPTCHA_NUM_CHOICES - 1 and attempts < 100:
        attempts += 1
        delta = random.randint(1, 5) * random.choice([-1, 1])
        candidate = answer + delta
        if candidate != answer and candidate >= 0:
            wrong.add(candidate)

    choices = list(wrong)[:CAPTCHA_NUM_CHOICES - 1] + [answer]
    random.shuffle(choices)

    return {"question": question, "answer": answer, "choices": choices}


def _captcha_keyboard(captcha: dict) -> InlineKeyboardMarkup:
    """
    Builds a keyboard with CAPTCHA_NUM_CHOICES answer buttons (in a row of 5)
    plus a '🔄 New question' button below.
    """
    answer_buttons = [
        InlineKeyboardButton(
            str(c),
            callback_data=f"{CAPTCHA_CB_PREFIX}{c}_{captcha['answer']}"
        )
        for c in captcha["choices"]
    ]
    return InlineKeyboardMarkup([
        answer_buttons,
        [InlineKeyboardButton("🔄 New question", callback_data=CAPTCHA_CB_RETRY)],
    ])


def _captcha_text(captcha: dict) -> str:
    return (
        "👋 <b>Welcome!</b>\n\n"
        "🧠 <b>Solve this to prove you're human:</b>\n\n"
        f"<blockquote>❓  <b>{captcha['question']} = ?</b></blockquote>\n\n"
        "👇 Tap the correct answer below:"
    )


# ─── /start ref_XXXX HANDLING ───────────────────────────────────────────────

async def handle_start_with_ref(update: Update, context: ContextTypes.DEFAULT_TYPE, ref_code: str) -> bool:
    """
    Called from start() when /start ref_XXXX is used. Creates the invite
    record (first-touch only) and sends the math CAPTCHA prompt.
    Returns True if it fully handled the response (caller should return),
    False if there's nothing to do (e.g. invalid/self code) and normal
    /start flow should continue.
    """
    user_id = update.effective_user.id

    referrer_id = await get_referrer_id_by_code(ref_code)
    if not referrer_id or referrer_id == user_id:
        return False  # invalid or self-referral — fall through to normal /start

    existing = await get_invite(user_id)
    if existing:
        # Already referred before (by this or another code) — don't override.
        return False

    await create_invite(referrer_id, user_id, ref_code)
    await send_captcha(update, context)
    return True


# ─── CAPTCHA STAGE ──────────────────────────────────────────────────────────

async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a fresh math CAPTCHA question via a new message."""
    captcha = _generate_captcha()
    # Store answer in bot_data keyed by user_id so we can validate the callback
    user_id = update.effective_user.id
    context.bot_data[f"captcha_{user_id}"] = captcha["answer"]

    await update.message.reply_text(
        _captcha_text(captcha),
        parse_mode="HTML",
        reply_markup=_captcha_keyboard(captcha),
    )


async def _send_captcha_edit(query, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Send a fresh math CAPTCHA by editing the existing message (for retry/wrong answer)."""
    captcha = _generate_captcha()
    context.bot_data[f"captcha_{user_id}"] = captcha["answer"]

    await query.message.edit_text(
        _captcha_text(captcha),
        parse_mode="HTML",
        reply_markup=_captcha_keyboard(captcha),
    )


async def handle_captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Callback handler for answer buttons:  captcha_ans_{chosen}_{correct}
    Validates the answer. On correct → advances funnel.
    On wrong → shows new question (retry).
    """
    query = update.callback_query
    user_id = update.effective_user.id

    # Parse callback: captcha_ans_{chosen}_{correct}
    # Format: CAPTCHA_CB_PREFIX + chosen + "_" + correct
    raw = query.data[len(CAPTCHA_CB_PREFIX):]          # e.g. "12_12" or "7_12"
    parts = raw.split("_")
    try:
        chosen  = int(parts[0])
        correct = int(parts[1])
    except (ValueError, IndexError):
        await query.answer("❌ Invalid answer data.", show_alert=True)
        return

    # Double-check against stored answer (tamper guard)
    stored_answer = context.bot_data.get(f"captcha_{user_id}")

    if chosen == correct and (stored_answer is None or chosen == stored_answer):
        # ── CORRECT ──
        await query.answer("✅ Correct!")
        # Clean up stored answer
        context.bot_data.pop(f"captcha_{user_id}", None)

        invite = await get_invite(user_id)
        if invite and invite["stage"] == STAGE_SIGNED_UP:
            await set_invite_stage(user_id, STAGE_AWAITING_JOIN)

        try:
            await query.message.delete()
        except Exception:
            pass

        # Continue into the normal membership-gate flow.
        if not await membership_gate.check_membership(context, user_id):
            await membership_gate.send_gate_message(update, context)
        else:
            # Already a member — advance straight to awaiting_interaction.
            if invite:
                await set_invite_stage(user_id, STAGE_AWAITING_INTERACTION)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="<blockquote><b>👋 Welcome to CayShop Bot!</b></blockquote>\n"
                     "I'm here to help you purchase subscriptions and digital "
                     "services easily and securely.",
                parse_mode="HTML",
            )
    else:
        # ── WRONG ──
        await query.answer("❌ Wrong answer! Try a new question.", show_alert=True)
        await _send_captcha_edit(query, context, user_id)


async def handle_captcha_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback handler for the '🔄 New question' button."""
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer("🔄 New question!")
    await _send_captcha_edit(query, context, user_id)


# ─── PROGRESSION HOOKS (call these from main.py's handlers) ─────────────────

async def advance_after_gate_pass(user_id: int, context: ContextTypes.DEFAULT_TYPE = None) -> None:
    invite = await get_invite(user_id)
    if invite and invite["stage"] == STAGE_AWAITING_JOIN:
        await set_invite_stage(user_id, STAGE_AWAITING_INTERACTION)

        if context:
            referrer_id = invite["referrer_id"]
            referrer_user = await db.get_user(referrer_id)
            referrer_name = (referrer_user or {}).get("full_name", "someone") if referrer_user else "someone"
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"👋 Welcome! You joined through {referrer_name}'s invitation.\n"
                        f"Thanks for joining! Enjoy the service. 🎉"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Failed to notify referred user {user_id}: {e}")


async def mark_interaction_and_maybe_qualify(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    invite = await get_invite(user_id)
    if not invite or invite["stage"] != STAGE_AWAITING_INTERACTION:
        return

    await set_invite_stage(user_id, STAGE_QUALIFIED)

    referrer_id = invite["referrer_id"]

    # ── Fetch referrer info for display ──
    referrer_user = await db.get_user(referrer_id)
    referrer_name = (referrer_user or {}).get("full_name", "Someone") if referrer_user else "Someone"

    # ── Fetch referred user info ──
    referred_user = await db.get_user(user_id)
    referred_name = (referred_user or {}).get("full_name", "User") if referred_user else "User"

    # ── Count this referrer's qualified invites ──
    invites = await get_invites_for_referrer(referrer_id)
    qualified_count = sum(1 for i in invites if i["stage"] == STAGE_QUALIFIED)

    mod = qualified_count % QUALIFIED_PER_REWARD
    just_hit_batch = mod == 0
    remaining = 0 if just_hit_batch else (QUALIFIED_PER_REWARD - mod)

    # ── Notify REFERRER ──
    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=(
                f"<blockquote>✅ <b>Your invitation for {referred_name} was counted successfully!\n"
                f"📊 Your successful invites: {qualified_count}/{QUALIFIED_PER_REWARD}</b></blockquote>\n\n"
                + (
                    f"<blockquote>🎉 <b>You earned a reward batch! ${REWARD_USD:.2f} added to your balance.</b></blockquote>"
                    if just_hit_batch else
                    f"<blockquote><b><i>{remaining} invite(s) left to earn a reward.</i></b></blockquote>"
                )
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Failed to notify referrer {referrer_id} of new invite: {e}")

    # ── Notify CHANNEL ──
    if CHANNEL_ID:
        raw = await db.get_setting(f"invite_rewarded_batches:{referrer_id}")
        already_rewarded_batches = int(raw) if raw else 0
        total_earned = round(already_rewarded_batches * REWARD_USD, 2)

        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=(
                    f"<blockquote>🎁 <b>Active Referral!</b>\n\n"
                    f"👤 <b>Referrer:</b> <a href='tg://user?id={referrer_id}'>{referrer_name}</a>\n"
                    f"🔗 <b>Active Referrals:</b> {qualified_count}\n"
                    f"💰 <b>Total earned from invites:</b> ${total_earned:.2f}\n"
                    f"⏳ <b>{remaining}</b> more to earn <b>${REWARD_USD:.2f}</b></blockquote>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to send referral channel notification: {e}")

    await _maybe_reward_referrer(context, referrer_id)


async def _maybe_reward_referrer(context: ContextTypes.DEFAULT_TYPE, referrer_id: int) -> None:
    invites = await get_invites_for_referrer(referrer_id)
    qualified = [i for i in invites if i["stage"] == STAGE_QUALIFIED]
    qualified_count = len(qualified)

    if qualified_count == 0 or qualified_count % QUALIFIED_PER_REWARD != 0:
        return

    # Guard against double-rewarding the same batch.
    key = f"invite_rewarded_batches:{referrer_id}"
    raw = await db.get_setting(key)
    already_rewarded_batches = int(raw) if raw else 0
    earned_batches = qualified_count // QUALIFIED_PER_REWARD

    if earned_batches <= already_rewarded_batches:
        return  # this batch was already paid

    new_batches = earned_batches - already_rewarded_batches
    reward_amount = round(new_batches * REWARD_USD, 2)

    await db.credit_balance_usd(
        referrer_id, reward_amount,
        description=f"Referral reward ({new_batches} batch(es) of {QUALIFIED_PER_REWARD})",
    )
    await db.set_setting(key, str(earned_batches))

    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=(
                f"🎉 <b>Referral reward!</b>\n\n"
                f"You just hit <b>{qualified_count}</b> qualified invites.\n"
                f"💰 <b>${reward_amount:.2f}</b> has been added to your balance."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Failed to notify referrer {referrer_id} of reward: {e}")


# ─── INVITE CENTER MENU ──────────────────────────────────────────────────────

def _invite_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Invite Stats", callback_data="invite_stats"),
            InlineKeyboardButton("🔗 Invite Link", callback_data="invite_link"),
        ],
        [InlineKeyboardButton("✕ Close", callback_data="close")],
    ])


async def show_invite_center(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Choose an invite option below.",
        reply_markup=_invite_center_keyboard(),
    )


async def show_invite_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    invites = await get_invites_for_referrer(user_id)

    total          = len(invites)
    awaiting_join  = sum(1 for i in invites if i["stage"] == STAGE_AWAITING_JOIN)
    awaiting_human = sum(1 for i in invites if i["stage"] == STAGE_SIGNED_UP)
    awaiting_inter = sum(1 for i in invites if i["stage"] == STAGE_AWAITING_INTERACTION)
    qualified      = sum(1 for i in invites if i["stage"] == STAGE_QUALIFIED)

    raw = await db.get_setting(f"invite_rewarded_batches:{user_id}")
    rewarded_batches = int(raw) if raw else 0
    total_earned = round(rewarded_batches * REWARD_USD, 2)

    text = (
        "<blockquote>📊 <b>Your invite stats:</b>\n\n"
        f"🔑 Total sign-ups: <b>{total}</b>\n"
        f"⏳ Awaiting join (group+channel): <b>{awaiting_join}</b>\n"
        f"🧩 Awaiting human verify: <b>{awaiting_human}</b>\n"
        f"🎮 Awaiting bot interaction: <b>{awaiting_inter}</b>\n"
        f"✅ Qualified for reward batch: <b>{qualified}</b>\n"
        f"🏅 Invites already rewarded: <b>{rewarded_batches * QUALIFIED_PER_REWARD}</b>\n\n"
        f"💰 <b>Total balance earned:</b> ${total_earned:.2f}</blockquote>\n\n"
        f"📌 <i><b>Every {QUALIFIED_PER_REWARD} qualified invites = ${REWARD_USD:.0f}.</b></i>"
    )

    await query.answer()
    await query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="invite_back")],
        ]),
    )


async def show_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    link = await get_invite_link(context, user_id)

    await query.answer()
    await query.message.edit_text(
        f"<blockquote>🔗 <b>Your exclusive invite link:</b></blockquote>"
        f"<pre>{link}</pre>\n\n"
        f"<i><b>Share this link with friends and earn ${REWARD_USD:.0f} for every "
        f"{QUALIFIED_PER_REWARD} people who join and activate the bot! 🎉</b></i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="invite_back")],
        ]),
    )


async def show_invite_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "Choose an invite option below.",
        reply_markup=_invite_center_keyboard(),
    )