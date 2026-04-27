# VPS Setup - TopUpFast Bot

> IP VPS: `160.191.245.231`  
> Chạy toàn bộ theo thứ tự từ trên xuống

---

## BƯỚC 1 — Kết nối VPS

```bash
ssh root@160.191.245.231
```

---

## BƯỚC 2 — Cập nhật hệ thống + cài Python

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx ufw curl
```

---

## BƯỚC 3 — Tạo user riêng (không chạy bot bằng root)

```bash
adduser botuser
usermod -aG sudo botuser
su - botuser
```

---

## BƯỚC 4 — Upload code lên VPS

**Cách 1: Dùng Git (khuyến nghị)**

```bash
cd /home/botuser
git clone https://github.com/YOUR_USERNAME/topupfast.git
cd topupfast
```

**Cách 2: SCP từ máy Windows (chạy lệnh này trên máy local, không phải VPS)**

```powershell
scp -r "d:\code\topupfast" botuser@160.191.245.231:/home/botuser/topupfast
```

---

## BƯỚC 5 — Cài dependencies Python

```bash
cd /home/botuser/topupfast
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## BƯỚC 6 — Tạo file .env

```bash
cp .env.example .env
nano .env
```

Điền các giá trị sau vào `.env`:

```
DISCORD_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_guild_id

SEPAY_API_TOKEN=your_sepay_token
SEPAY_BANK_CODE=BIDV
SEPAY_ACCOUNT_NUMBER=your_account_number
SEPAY_ACCOUNT_NAME=NGUYEN VAN A

COINREMITTER_API_KEY=your_api_key
COINREMITTER_PASSWORD=your_password
COINREMITTER_WALLET_LTC=your_ltc_wallet_id

WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_BASE_URL=http://160.191.245.231:8080

DATABASE_PATH=topupfast.db
EXCHANGE_RATE=26000
MIN_DEPOSIT_VND=10000
MIN_DEPOSIT_USD=1.0
PAYMENT_EXPIRY_MINUTES=30
```

> Lưu: `Ctrl+O` → Enter → `Ctrl+X`

---

## BƯỚC 7 — Test chạy thử (kiểm tra không có lỗi)

```bash
source venv/bin/activate
python main.py
```

Nếu thấy `Đăng nhập: BotName#0000` là OK. Nhấn `Ctrl+C` để dừng rồi chuyển sang bước tiếp.

---

## BƯỚC 8 — Cài systemd (tự chạy lại khi crash / reboot)

```bash
sudo nano /etc/systemd/system/topupfast.service
```

Paste nội dung sau (thay `botuser` nếu dùng tên khác):

```ini
[Unit]
Description=TopUpFast Discord Bot
After=network.target

[Service]
User=botuser
WorkingDirectory=/home/botuser/topupfast
ExecStart=/home/botuser/topupfast/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable topupfast
sudo systemctl start topupfast
sudo systemctl status topupfast
```

---

## BƯỚC 9 — Cấu hình Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
# Port 8080 KHÔNG cần mở vì Nginx sẽ proxy
```

---

## BƯỚC 10 — (Tuỳ chọn) Nginx + HTTPS nếu có domain

> Nếu chưa có domain, bỏ qua bước này.  
> SePay yêu cầu HTTPS cho webhook — nếu dùng IP thì cần dùng HTTP (hạn chế).

```bash
sudo nano /etc/nginx/sites-available/topupfast
```

```nginx
server {
    server_name your-domain.com;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/topupfast /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

Sau đó cập nhật `.env`:

```
WEBHOOK_BASE_URL=https://your-domain.com
```

Rồi restart:

```bash
sudo systemctl restart topupfast
```

---

## Lệnh hữu ích hàng ngày

| Mục đích            | Lệnh                                                             |
| ------------------- | ---------------------------------------------------------------- |
| Xem log realtime    | `sudo journalctl -u topupfast -f`                                |
| Xem log file        | `tail -f /home/botuser/topupfast/topupfast.log`                  |
| Restart bot         | `sudo systemctl restart topupfast`                               |
| Dừng bot            | `sudo systemctl stop topupfast`                                  |
| Trạng thái bot      | `sudo systemctl status topupfast`                                |
| Cập nhật code (git) | `cd ~/topupfast && git pull && sudo systemctl restart topupfast` |

---

## Cấu hình Webhook trên SePay

1. Đăng nhập [my.sepay.vn](https://my.sepay.vn)
2. Vào **Tài khoản ngân hàng** → chọn tài khoản → **Cấu hình Webhook**
3. URL webhook: `http://160.191.245.231:8080/webhook/sepay`  
   _(nếu có domain HTTPS thì dùng `https://your-domain.com/webhook/sepay`)_
4. Lưu lại

---

## Kiểm tra webhook hoạt động

```bash
# Trên VPS - gửi test request thủ công
curl -X POST http://localhost:8080/webhook/sepay \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SEPAY_API_TOKEN" \
  -d '{"content":"TFA12345","transferAmount":100000}'
```

```bash
# Health check
curl http://localhost:8080/health
# Kết quả mong đợi: {"status": "ok"}
```
