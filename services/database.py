import random
import string
from datetime import datetime, timedelta

from supabase import acreate_client, AsyncClient

from config import SUPABASE_URL, SUPABASE_KEY, PAYMENT_EXPIRY_MINUTES

_client: AsyncClient | None = None


# ------------------------------------------------------------------ init --

async def init_db() -> None:
    """Khởi tạo Supabase client (kết nối qua HTTPS)."""
    global _client
    _client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)


def _db() -> AsyncClient:
    if _client is None:
        raise RuntimeError("Database chưa được khởi tạo. Gọi init_db() trước.")
    return _client


# ----------------------------------------------------------------- users --

async def get_or_create_user(discord_id: str, avatar_url: str | None = None) -> dict:
    res = await _db().table("users").select("*").eq("discord_id", discord_id).execute()
    if res.data:
        user = res.data[0]
        if avatar_url and user.get("avatar_url") != avatar_url:
            await _db().table("users").update({
                "avatar_url": avatar_url,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("discord_id", discord_id).execute()
        return user

    res = await _db().table("users").insert({
        "discord_id": discord_id,
        "avatar_url": avatar_url,
    }).execute()
    return res.data[0]


async def get_user(discord_id: str) -> dict | None:
    res = await _db().table("users").select("*").eq("discord_id", discord_id).execute()
    return res.data[0] if res.data else None


async def add_balance(discord_id: str, amount_usd: float) -> None:
    user = await get_user(discord_id)
    if user is None:
        return
    new_balance = (user.get("balance") or 0.0) + amount_usd
    await _db().table("users").update({
        "balance": new_balance,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("discord_id", discord_id).execute()


# ------------------------------------------------------------- TFA codes --

def generate_tfa_code() -> str:
    digits = "".join(random.choices(string.digits, k=5))
    return f"TFA{digits}"


# --------------------------------------------------------- transactions --

async def create_transaction(
    *,
    discord_id: str,
    user_id: int,
    type: str,
    provider: str,
    amount_usd: float,
    amount_vnd: int = 0,
    currency: str | None = None,
    coin: str | None = None,
    tfa_code: str | None = None,
    provider_ref: str | None = None,
    invoice_url: str | None = None,
    qr_url: str | None = None,
    discord_channel_id: str | None = None,
    discord_message_id: str | None = None,
) -> dict:
    expires_at = (datetime.utcnow() + timedelta(minutes=PAYMENT_EXPIRY_MINUTES)).isoformat()
    res = await _db().table("transactions").insert({
        "discord_id": discord_id,
        "user_id": user_id,
        "type": type,
        "provider": provider,
        "amount_usd": amount_usd,
        "amount_vnd": amount_vnd,
        "currency": currency,
        "coin": coin,
        "tfa_code": tfa_code,
        "provider_ref": provider_ref,
        "invoice_url": invoice_url,
        "qr_url": qr_url,
        "discord_channel_id": discord_channel_id,
        "discord_message_id": discord_message_id,
        "expires_at": expires_at,
    }).execute()
    return res.data[0]


async def update_transaction(tx_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    await _db().table("transactions").update(fields).eq("id", tx_id).execute()


async def get_transaction(tx_id: int) -> dict | None:
    res = await _db().table("transactions").select("*").eq("id", tx_id).execute()
    return res.data[0] if res.data else None


async def get_transaction_by_tfa(tfa_code: str) -> dict | None:
    res = await (
        _db().table("transactions")
        .select("*")
        .eq("tfa_code", tfa_code)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_transaction_by_provider_ref(provider_ref: str) -> dict | None:
    res = await (
        _db().table("transactions")
        .select("*")
        .eq("provider_ref", provider_ref)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


async def get_user_transactions(discord_id: str, limit: int = 10) -> list[dict]:
    res = await (
        _db().table("transactions")
        .select("*")
        .eq("discord_id", discord_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []
