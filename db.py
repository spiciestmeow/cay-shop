import os
from supabase import create_client, Client

from dotenv import load_dotenv

load_dotenv()


SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CATEGORIES_TABLE = "cay_shop_categories"
PRODUCTS_TABLE = "cay_shop_products"
USERS_TABLE = "cay_shop_users"
STATES_TABLE = "cay_shop_states"


def _client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── CATEGORIES ──────────────────────────────────────────────────────────────

async def get_categories() -> list[dict]:
    c = _client()
    res = c.table(CATEGORIES_TABLE).select("*").order("position", desc=False).order("id", desc=False).execute()
    return res.data or []


async def get_category(cat_id: int) -> dict | None:
    c = _client()
    res = c.table(CATEGORIES_TABLE).select("*").eq("id", cat_id).limit(1).execute()
    return res.data[0] if res.data else None


async def add_category(name: str, emoji: str) -> int:
    c = _client()
    pos_res = c.table(CATEGORIES_TABLE).select("position").order("position", desc=True).limit(1).execute()
    next_pos = (pos_res.data[0]["position"] + 1) if pos_res.data else 1
    res = c.table(CATEGORIES_TABLE).insert({"name": name, "emoji": emoji, "position": next_pos}).execute()
    return res.data[0]["id"]


async def delete_category(cat_id: int) -> None:
    c = _client()
    c.table(CATEGORIES_TABLE).delete().eq("id", cat_id).execute()


async def update_category(cat_id: int, name: str | None = None, emoji: str | None = None) -> None:
    c = _client()
    updates = {}
    if name is not None:
        updates["name"] = name
    if emoji is not None:
        updates["emoji"] = emoji
    if updates:
        c.table(CATEGORIES_TABLE).update(updates).eq("id", cat_id).execute()


# ─── PRODUCTS ────────────────────────────────────────────────────────────────

async def get_products(cat_id: int) -> list[dict]:
    c = _client()
    res = c.table(PRODUCTS_TABLE).select("*").eq("category_id", cat_id).order("id").execute()
    return res.data or []


async def get_product(prod_id: int) -> dict | None:
    c = _client()
    res = c.table(PRODUCTS_TABLE).select("*").eq("id", prod_id).limit(1).execute()
    return res.data[0] if res.data else None


async def add_product(
    cat_id: int,
    name: str,
    description: str,
    price: float,
    stock: int,
    duration: str = "",
    warranty: str = "No warranty",
    delivery: str = "LINK",
    demo_url: str = "",  
    delivery_url: str = "",
) -> int:
    c = _client()
    res = c.table(PRODUCTS_TABLE).insert({
        "category_id": cat_id,
        "name": name,
        "description": description,
        "price": price,
        "stock": stock,
        "duration": duration,
        "warranty": warranty,
        "delivery": delivery,
        "demo_url": demo_url, 
        "delivery_url": delivery_url,
    }).execute()
    return res.data[0]["id"]


async def update_product_stock(prod_id: int, stock: int) -> None:
    c = _client()
    c.table(PRODUCTS_TABLE).update({"stock": stock}).eq("id", prod_id).execute()

async def update_product(prod_id: int, **fields) -> None:
    c = _client()
    if fields:
        c.table(PRODUCTS_TABLE).update(fields).eq("id", prod_id).execute()

async def delete_product(prod_id: int) -> None:
    c = _client()
    c.table(PRODUCTS_TABLE).delete().eq("id", prod_id).execute()


async def get_all_products_availability() -> str:
    categories = await get_categories()
    if not categories:
        return "🗒 <b>What's Available</b>\n\nNo products added yet."
    lines = ["🗒 <b>What's Available</b>\n━━━━━━━━━━━━━━━━━━━━━━━━"]
    for cat in categories:
        products = await get_products(cat["id"])
        if not products:
            continue
        lines.append(f"\n{cat['emoji']} <b>{cat['name']}</b>")
        for p in products:
            stock_icon = "✅" if p["stock"] > 0 else "❌"
            stock_text = f"Available • {p['stock']}x" if p["stock"] > 0 else "Out of Stock"
            lines.append(
                f"<blockquote><b>#{p['id']} {cat['emoji']} {p['name']}</b>\n"
                f"{stock_icon} {stock_text}</blockquote>"
            )
    if len(lines) == 1:
        lines.append("\nNo products added yet.")
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


# ─── USERS ───────────────────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str | None, full_name: str | None) -> dict:
    c = _client()
    res = c.table(USERS_TABLE).select("*").eq("user_id", user_id).limit(1).execute()
    if res.data:
        return res.data[0]
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    ins = c.table(USERS_TABLE).insert({
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "joined_at": now,
    }).execute()
    return ins.data[0] if ins.data else {}

async def get_user(user_id: int) -> dict | None:
    c = _client()
    res = c.table(USERS_TABLE).select("*").eq("user_id", user_id).limit(1).execute()
    return res.data[0] if res.data else None

async def credit_balance(user_id: int, amount_php: float) -> None:
    PHP_TO_USD_RATE = 56.0  # update this to current rate
    amount_usd = round(amount_php / PHP_TO_USD_RATE, 2)
    
    c = _client()
    res = c.table(USERS_TABLE).select("balance").eq("user_id", user_id).limit(1).execute()
    if not res.data:
        return
    current_balance = float(res.data[0].get("balance") or 0)
    new_balance = round(current_balance + amount_usd, 2)
    c.table(USERS_TABLE).update({"balance": new_balance}).eq("user_id", user_id).execute()

# ─── SESSION STATE ────────────────────────────────────────────────────────────

async def get_session(user_id: int) -> dict:
    c = _client()
    res = c.table(STATES_TABLE).select("state").eq("user_id", user_id).limit(1).execute()
    if res.data:
        data = res.data[0].get("state")
        return data if isinstance(data, dict) else {}
    return {}


async def set_session(user_id: int, state: dict) -> None:
    c = _client()
    c.table(STATES_TABLE).upsert({"user_id": user_id, "state": state}).execute()


async def clear_session(user_id: int) -> None:
    c = _client()
    c.table(STATES_TABLE).delete().eq("user_id", user_id).execute()

# ─── STATUS TIERS ────────────────────────────────────────────────────────────

STATUS_TIERS = [
    {"name": "Newbie",    "min": 0.0,    "discount": 0},
    {"name": "Bronze",    "min": 200.0,  "discount": 1},
    {"name": "Silver",    "min": 400.0,  "discount": 2},
    {"name": "Gold",      "min": 500.0,  "discount": 3},
    {"name": "Platinum",  "min": 1000.0, "discount": 4},
    {"name": "Diamond",   "min": 2100.0, "discount": 5},
    {"name": "Brilliant", "min": 5000.0, "discount": 6},
]

def get_status_tier(total_spent: float) -> dict:
    """Return the current tier dict for a given total_spent."""
    current = STATUS_TIERS[0]
    for tier in STATUS_TIERS:
        if total_spent >= tier["min"]:
            current = tier
    return current

def get_next_tier(total_spent: float) -> dict | None:
    """Return the next tier, or None if already at max."""
    for tier in STATUS_TIERS:
        if tier["min"] > total_spent:
            return tier
    return None

async def record_purchase(user_id: int, amount_usd: float) -> None:
    """Deduct balance and increment total_spent + total_purchases."""
    c = _client()
    res = c.table(USERS_TABLE).select("balance, total_spent, total_purchases").eq("user_id", user_id).limit(1).execute()
    if not res.data:
        return
    row = res.data[0]
    new_balance = round(float(row.get("balance") or 0) - amount_usd, 2)
    new_spent = round(float(row.get("total_spent") or 0) + amount_usd, 2)
    new_purchases = int(row.get("total_purchases") or 0) + 1
    c.table(USERS_TABLE).update({
        "balance": new_balance,
        "total_spent": new_spent,
        "total_purchases": new_purchases,
    }).eq("user_id", user_id).execute()