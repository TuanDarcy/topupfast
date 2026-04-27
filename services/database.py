import random
import string
from datetime import datetime, timedelta

import aiohttp

from config import SUPABASE_URL, SUPABASE_KEY, PAYMENT_EXPIRY_MINUTES

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
_REST = f"{SUPABASE_URL}/rest/v1"

_session: aiohttp.ClientSession | None = None


# ------------------------------------------------------------------ init --

async def init_db() -> None:
    global _session
    _session = aiohttp.ClientSession(headers=_HEADERS)


def _sess() -> aiohttp.ClientSession:
    if _session is None:
        raise RuntimeError("Database chua duoc khoi tao. Goi init_db() truoc.")
    return _session


async def _get(table: str, params: dict) -> list:
    async with _sess().get(f"{_REST}/{table}", params=params) as r:
        r.raise_for_status()
        return await r.json()


async def _post(table: str, data: dict) -> dict:
    async with _sess().post(f"{_REST}/{table}", json=data) as r:
        r.raise_for_status()
        rows = await r.json()
        return rows[0] if isinstance(rows, list) else rows


async def _patch(table: str, match: dict, data: dict) -> None:
    params = {k: f"eq.{v}" for k, v in match.items()}
    async with _sess().patch(f"{_REST}/{table}", params=params, json=data) as r:
        r.raise_for_status()


async def get_or_create_user(discord_id: str, avatar_url=None) -> dict:
    rows = await _get("users", {"discord_id": f"eq.{discord_id}"})
    if rows:
        user = rows[0]
        if avatar_url and user.get("avatar_url") != avatar_url:
            await _patch("users", {"discord_id": discord_id}, {
                "avatar_url": avatar_url,
                "updated_at": datetime.utcnow().isoformat(),
            })
        return user
    return await _post("users", {"discord_id": discord_id, "avatar_url": avatar_url})


async def get_user(discord_id: str):
    rows = await _get("users", {"discord_id": f"eq.{discord_id}"})
    return rows[0] if rows else None


async def add_balance(discord_id: str, amount_usd: float) -> None:
    user = await get_user(discord_id)
    if user is None:
        return
    new_balance = (user.get("balance") or 0.0) + amount_usd
    await _patch("users", {"discord_id": discord_id}, {
        "balance": new_balance,
        "updated_at": datetime.utcnow().isoformat(),
    })


def generate_tfa_code() -> str:
    digits = "".join(__import__("random").choices(__import__("string").digits, k=5))
    return f"TFA{digits}"


async def create_transaction(*, discord_id, user_id, type, provider, amount_usd,
    amount_vnd=0, currency=None, coin=None, tfa_code=None, provider_ref=None,
    invoice_url=None, qr_url=None, discord_channel_id=None, discord_message_id=None):
    from datetime import timedelta
    expires_at = (datetime.utcnow() + timedelta(minutes=PAYMENT_EXPIRY_MINUTES)).isoformat()
    return await _post("transactions", {
        "discord_id": discord_id, "user_id": user_id, "type": type,
        "provider": provider, "amount_usd": amount_usd, "amount_vnd": amount_vnd,
        "currency": currency, "coin": coin, "tfa_code": tfa_code,
        "provider_ref": provider_ref, "invoice_url": invoice_url, "qr_url": qr_url,
        "discord_channel_id": discord_channel_id, "discord_message_id": discord_message_id,
        "expires_at": expires_at,
    })


async def update_transaction(tx_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow().isoformat()
    await _patch("transactions", {"id": tx_id}, fields)


async def get_transaction(tx_id: int):
    rows = await _get("transactions", {"id": f"eq.{tx_id}"})
    return rows[0] if rows else None


async def get_transaction_by_tfa(tfa_code: str):
    rows = await _get("transactions", {"tfa_code": f"eq.{tfa_code}", "status": "eq.pending", "order": "created_at.desc", "limit": "1"})
    return rows[0] if rows else None


async def get_transaction_by_provider_ref(provider_ref: str):
    rows = await _get("transactions", {"provider_ref": f"eq.{provider_ref}", "order": "created_at.desc", "limit": "1"})
    return rows[0] if rows else None


async def get_user_transactions(discord_id: str, limit: int = 10) -> list:
    rows = await _get("transactions", {"discord_id": f"eq.{discord_id}", "order": "created_at.desc", "limit": str(limit)})
    return rows or []
