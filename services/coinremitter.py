"""
CoinRemitter integration - Crypto payment

Docs: https://coinremitter.com/docs/api

Flow:
  1. Bot gọi create_invoice() với coin và số USD
  2. CoinRemitter trả về địa chỉ ví + URL invoice
  3. User gửi coin đến địa chỉ đó
  4. CoinRemitter gửi webhook đến /webhook/coinremitter khi nhận được thanh toán
  5. Bot tìm giao dịch theo invoice_id, cộng tiền cho user

Setup:
  - Tạo tài khoản tại https://coinremitter.com
  - Tạo wallet cho từng coin muốn dùng
  - Lấy API Key và Password trong Settings
  - Điền vào .env: COINREMITTER_API_KEY, COINREMITTER_PASSWORD
  - Điền Wallet ID cho từng coin vào .env
"""

import aiohttp

from config import (
    COINREMITTER_API_KEY,
    COINREMITTER_PASSWORD,
    COINREMITTER_WALLETS,
    WEBHOOK_BASE_URL,
    PAYMENT_EXPIRY_MINUTES,
)

_BASE_URL = "https://coinremitter.com/api/v3"

# Tên hiển thị cho từng coin
SUPPORTED_COINS: dict[str, str] = {
    "LTC":  "Litecoin (LTC)",
    "BTC":  "Bitcoin (BTC)",
    "ETH":  "Ethereum (ETH)",
    "USDT": "Tether USDT (TRC20)",
}


def get_available_coins() -> dict[str, str]:
    """Trả về các coin đã được cấu hình wallet."""
    return {
        coin: label
        for coin, label in SUPPORTED_COINS.items()
        if COINREMITTER_WALLETS.get(coin)
    }


async def create_invoice(coin: str, amount_usd: float, description: str) -> dict:
    """
    Tạo invoice trên CoinRemitter.

    Returns:
        dict với các key: id, url, address, total_amount, expire_on, ...

    Raises:
        ValueError: coin không được cấu hình
        Exception: lỗi từ CoinRemitter API
    """
    coin = coin.upper()
    wallet_id = COINREMITTER_WALLETS.get(coin)
    if not wallet_id:
        raise ValueError(f"Chưa cấu hình wallet cho {coin}.")

    notify_url = f"{WEBHOOK_BASE_URL}/webhook/coinremitter"

    payload = {
        "api_key":    COINREMITTER_API_KEY,
        "password":   COINREMITTER_PASSWORD,
        "amount":     str(amount_usd),
        "notify_url": notify_url,
        "name":       description[:100],
        "description": description[:200],
        "expire_time": str(PAYMENT_EXPIRY_MINUTES),
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_BASE_URL}/{coin}/create-invoice",
            data=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            result = await resp.json()

    if result.get("flag") != 1:
        raise Exception(f"CoinRemitter: {result.get('msg', 'Unknown error')}")

    return result["data"]
