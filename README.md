# TopUpFast Discord Bot

Bot Discord tự động nạp tiền qua **Bank VN (SePay)** và **Crypto (CoinRemitter)**.

---

## Cài đặt nhanh

### 1. Cài Python dependencies

```bash
cd topupfast
pip install -r requirements.txt
```

### 2. Tạo file `.env`

```bash
copy .env.example .env
```

Sau đó mở `.env` và điền đầy đủ thông tin.

---

## Cấu hình từng service

### Discord Bot

1. Vào [Discord Developer Portal](https://discord.com/developers/applications)
2. Tạo **New Application** → **Bot** → bật **Message Content Intent**
3. Copy **Token** → điền vào `DISCORD_TOKEN` trong file `.env`
4. Lấy **Server (Guild) ID** (chuột phải server → Copy Server ID, cần bật Developer Mode) → điền vào `DISCORD_GUILD_ID` trong file `.env`
5. **Invite bot** vào server: Trong OAuth2 → URL Generator → chọn `bot` + `applications.commands` → cấp quyền `Send Messages`, `Embed Links`, `Read Message History`

### SePay (Bank VN)

1. Đăng ký tại [my.sepay.vn](https://my.sepay.vn)
2. Kết nối tài khoản ngân hàng của bạn
3. Vào **Cài đặt → API** → tạo API Token → điền vào `SEPAY_API_TOKEN`
4. Điền thông tin tài khoản ngân hàng: `SEPAY_BANK_CODE`, `SEPAY_ACCOUNT_NUMBER`, `SEPAY_ACCOUNT_NAME`
5. Cấu hình **Webhook** tại SePay:
   - URL: `https://your-server.com/webhook/sepay`
   - Method: POST

   > Danh sách mã ngân hàng: [sepay.vn/list-bank.html](https://sepay.vn/list-bank.html)

### CoinRemitter (Crypto)

1. Đăng ký tại [coinremitter.com](https://coinremitter.com)
2. Tạo **Wallet** cho từng coin muốn hỗ trợ (LTC / BTC / ETH / USDT)
3. Vào **Settings → API** → lấy **API Key** và **Password**
4. Điền vào `.env`:
   ```
   COINREMITTER_API_KEY=xxx
   COINREMITTER_PASSWORD=xxx
   COINREMITTER_WALLET_LTC=wallet_id_ltc
   COINREMITTER_WALLET_BTC=wallet_id_btc
   # Bỏ trống coin nào không dùng
   ```
5. **Webhook** được cấu hình tự động khi tạo invoice (bot gửi URL callback)

### Webhook Server (Public URL)

Bot cần có **URL công khai** để SePay và CoinRemitter gửi webhook về.

**Khi test local → dùng ngrok:**

```bash
ngrok http 8080
# Copy URL như: https://xxxx.ngrok.io
# Điền vào WEBHOOK_BASE_URL=https://xxxx.ngrok.io
```

**Trên VPS:**

```
WEBHOOK_BASE_URL=https://your-domain.com
WEBHOOK_PORT=8080
```

Nhớ mở port 8080 (hoặc dùng Nginx reverse proxy).

---

## Chạy bot

```bash
cd topupfast
python main.py
```

---

## Cấu trúc file

```
topupfast/
├── main.py                  # Entry point
├── config.py                # Load biến môi trường
├── requirements.txt
├── schema.sql               # Database schema
├── .env                     # Biến môi trường (KHÔNG commit lên git)
├── .env.example             # Template
├── bot/
│   ├── client.py            # Discord bot client
│   └── cogs/
│       └── topup.py         # Slash commands + Views + Modals
├── services/
│   ├── database.py          # Tất cả thao tác với SQLite
│   ├── sepay.py             # Tạo QR, validate webhook SePay
│   └── coinremitter.py      # Tạo invoice CoinRemitter
└── webhooks/
    └── server.py            # aiohttp server nhận webhook
```

---

## Slash Commands

| Command   | Mô tả                               |
| --------- | ----------------------------------- |
| `/nap`    | Mở menu nạp tiền (Bank VN / Crypto) |
| `/sodu`   | Xem số dư USD hiện tại              |
| `/lichsu` | Xem 10 giao dịch gần nhất           |

---

## Luồng thanh toán

### Bank VN

```
User /nap → Chọn "Bank VN" → Nhập số VND
→ Bot gửi QR + mã TFA (VD: TFA12345)
→ User chuyển khoản đúng nội dung TFA12345
→ SePay webhook → Bot xác nhận → Cộng USD vào balance
```

### Crypto

```
User /nap → Chọn "Crypto" → Chọn coin → Nhập số USD
→ Bot tạo invoice CoinRemitter
→ Bot gửi địa chỉ ví + link invoice
→ User gửi coin → CoinRemitter webhook → Cộng USD vào balance
```

---

## Database

**Bảng `users`**: `id`, `discord_id`, `avatar_url`, `balance` (USD), `language`, timestamps

**Bảng `transactions`**: Lịch sử nạp tiền với đầy đủ thông tin (loại, provider, số tiền, trạng thái, TFA code, invoice ID...)
