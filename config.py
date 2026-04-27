import os
from dotenv import load_dotenv

load_dotenv()

# ---- Discord ----
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID", 0) or 0)
WELCOME_CHANNEL_ID: int = int(os.getenv("WELCOME_CHANNEL_ID", 0) or 0)

# ---- SePay ----
SEPAY_API_TOKEN: str = os.getenv("SEPAY_API_TOKEN", "")
SEPAY_BANK_CODE: str = os.getenv("SEPAY_BANK_CODE", "BIDV")
SEPAY_ACCOUNT_NUMBER: str = os.getenv("SEPAY_ACCOUNT_NUMBER", "")
SEPAY_ACCOUNT_NAME: str = os.getenv("SEPAY_ACCOUNT_NAME", "")

# ---- CoinRemitter ----
COINREMITTER_API_KEY: str = os.getenv("COINREMITTER_API_KEY", "")
COINREMITTER_PASSWORD: str = os.getenv("COINREMITTER_PASSWORD", "")
COINREMITTER_WALLETS: dict[str, str] = {
    "LTC":  os.getenv("COINREMITTER_WALLET_LTC", ""),
    "BTC":  os.getenv("COINREMITTER_WALLET_BTC", ""),
    "ETH":  os.getenv("COINREMITTER_WALLET_ETH", ""),
    "USDT": os.getenv("COINREMITTER_WALLET_USDT", ""),
}

# ---- Webhook ----
WEBHOOK_HOST: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", 8080))
WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8080").rstrip("/")

# ---- Supabase ----
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ---- Cài đặt chung ----
EXCHANGE_RATE: float = float(os.getenv("EXCHANGE_RATE", 26000))   # VND per 1 USD
MIN_DEPOSIT_VND: int = int(os.getenv("MIN_DEPOSIT_VND", 10000))
MIN_DEPOSIT_USD: float = float(os.getenv("MIN_DEPOSIT_USD", 1.0))
PAYMENT_EXPIRY_MINUTES: int = int(os.getenv("PAYMENT_EXPIRY_MINUTES", 30))
