-- ============================================================
-- TopUpFast Bot - Database Schema (PostgreSQL / Supabase)
-- Chạy file này trong Supabase SQL Editor
-- ============================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    discord_id  TEXT      UNIQUE NOT NULL,
    avatar_url  TEXT,
    balance     FLOAT     NOT NULL DEFAULT 0.0,
    language    TEXT      NOT NULL DEFAULT 'vi',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id          BIGSERIAL PRIMARY KEY,
    discord_id  TEXT    NOT NULL,
    user_id     BIGINT  NOT NULL REFERENCES users(id),

    type        TEXT    NOT NULL CHECK(type IN ('bank', 'crypto')),
    provider    TEXT    NOT NULL CHECK(provider IN ('sepay', 'coinremitter')),
    status      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'completed', 'failed', 'expired')),

    amount_usd  FLOAT   NOT NULL DEFAULT 0.0,
    amount_vnd  BIGINT           DEFAULT 0,
    currency    TEXT,

    coin        TEXT,
    provider_ref TEXT,
    invoice_url  TEXT,
    tfa_code    TEXT,
    qr_url      TEXT,

    discord_channel_id  TEXT,
    discord_message_id  TEXT,

    expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_tfa          ON transactions(tfa_code);
CREATE INDEX IF NOT EXISTS idx_transactions_provider_ref ON transactions(provider_ref);
CREATE INDEX IF NOT EXISTS idx_transactions_discord_id   ON transactions(discord_id);
CREATE INDEX IF NOT EXISTS idx_transactions_status       ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_users_discord_id          ON users(discord_id);
