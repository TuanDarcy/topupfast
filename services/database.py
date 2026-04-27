import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, unquote

import asyncpg

from config import DATABASE_URL, PAYMENT_EXPIRY_MINUTES

_pool: asyncpg.Pool | None = None
_SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


# ------------------------------------------------------------------ init --

async def init_db() -> None:
    """Tạo connection pool và các bảng nếu chưa có."""
    global _pool
    parsed = urlparse(DATABASE_URL)
    _pool = await asyncpg.create_pool(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=unquote(parsed.password or ""),
        database=parsed.path.lstrip("/"),
        min_size=2,
        max_size=10,
        ssl="require",
        statement_cache_size=0,
    )
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with _pool.acquire() as conn:
        await conn.execute(schema_sql)


def _pool_conn():
    if _pool is None:
        raise RuntimeError("Database chưa được khởi tạo. Gọi init_db() trước.")
    return _pool.acquire()


# ----------------------------------------------------------------- users --

async def get_or_create_user(discord_id: str, avatar_url: str | None = None) -> dict:
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE discord_id = $1", discord_id
        )
        if row:
            user = dict(row)
            if avatar_url and user.get("avatar_url") != avatar_url:
                await conn.execute(
                    "UPDATE users SET avatar_url = $1, updated_at = NOW() WHERE discord_id = $2",
                    avatar_url, discord_id,
                )
            return user

        row = await conn.fetchrow(
            "INSERT INTO users (discord_id, avatar_url) VALUES ($1, $2) RETURNING *",
            discord_id, avatar_url,
        )
        return dict(row)


async def get_user(discord_id: str) -> dict | None:
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE discord_id = $1", discord_id
        )
        return dict(row) if row else None


async def add_balance(discord_id: str, amount_usd: float) -> None:
    async with _pool_conn() as conn:
        await conn.execute(
            "UPDATE users SET balance = balance + $1, updated_at = NOW() WHERE discord_id = $2",
            amount_usd, discord_id,
        )


# ------------------------------------------------------------- TFA codes --

def generate_tfa_code() -> str:
    digits = "".join(random.choices(string.digits, k=5))
    return f"TFA{digits}"


# --------------------------------------------------------- transactions --

async def create_transaction(
    *,
    discord_id: str,
    user_id: int,
    type: str,           # 'bank' | 'crypto'
    provider: str,       # 'sepay' | 'coinremitter'
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
    expires_at = datetime.utcnow() + timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            """INSERT INTO transactions
               (discord_id, user_id, type, provider, amount_usd, amount_vnd, currency,
                coin, tfa_code, provider_ref, invoice_url, qr_url,
                discord_channel_id, discord_message_id, expires_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
               RETURNING *""",
            discord_id, user_id, type, provider, amount_usd, amount_vnd, currency,
            coin, tfa_code, provider_ref, invoice_url, qr_url,
            discord_channel_id, discord_message_id, expires_at,
        )
        return dict(row)


async def update_transaction(tx_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow()
    keys = list(fields.keys())
    values = list(fields.values())
    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(keys))
    values.append(tx_id)
    async with _pool_conn() as conn:
        await conn.execute(
            f"UPDATE transactions SET {set_clause} WHERE id = ${len(values)}",
            *values,
        )


async def get_transaction(tx_id: int) -> dict | None:
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM transactions WHERE id = $1", tx_id
        )
        return dict(row) if row else None


async def get_transaction_by_tfa(tfa_code: str) -> dict | None:
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM transactions
               WHERE tfa_code = $1 AND status = 'pending'
               ORDER BY created_at DESC LIMIT 1""",
            tfa_code,
        )
        return dict(row) if row else None


async def get_transaction_by_provider_ref(provider_ref: str) -> dict | None:
    async with _pool_conn() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM transactions
               WHERE provider_ref = $1
               ORDER BY created_at DESC LIMIT 1""",
            provider_ref,
        )
        return dict(row) if row else None


async def get_user_transactions(discord_id: str, limit: int = 10) -> list[dict]:
    async with _pool_conn() as conn:
        rows = await conn.fetch(
            "SELECT * FROM transactions WHERE discord_id = $1 ORDER BY created_at DESC LIMIT $2",
            discord_id, limit,
        )
        return [dict(r) for r in rows]
