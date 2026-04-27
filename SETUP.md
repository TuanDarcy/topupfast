# TopUpFast Bot — Hướng Dẫn Setup (Windows VPS)

> VPS Windows Server, chạy lệnh trong **PowerShell (Admin)**  
> Thực hiện từng BƯỚC theo thứ tự

---

## BƯỚC 1 — Cài Python 3.12

Dán toàn bộ vào PowerShell (Admin), chạy 1 lần:

```powershell
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe" -OutFile "$env:TEMP\python-installer.exe"
Start-Process "$env:TEMP\python-installer.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
python --version
```

> Thấy `Python 3.12.x` là OK

---

## BƯỚC 2 — Cài Git

```powershell
Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe" -OutFile "$env:TEMP\git-installer.exe"
Start-Process "$env:TEMP\git-installer.exe" -ArgumentList "/VERYSILENT /NORESTART" -Wait
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
git --version
```

> Thấy `git version 2.47.x` là OK

---

## BƯỚC 3 — Clone code và cài thư viện

```powershell
cd C:\Users\Administrator\Desktop
git clone https://github.com/TuanDarcy/topupfast.git
cd topupfast
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## BƯỚC 4 — Tạo file .env

Dán lệnh sau, **thay các giá trị trong `<...>` trước khi chạy**:

```powershell
@"
# ============================================================
# TopUpFast Bot - Environment Variables
# ============================================================

# ---- Discord ----
DISCORD_TOKEN=<BOT_TOKEN>
DISCORD_GUILD_ID=<GUILD_ID>

# ---- SePay (Bank VN) ----
SEPAY_API_TOKEN=<SEPAY_TOKEN>
SEPAY_BANK_CODE=BIDV
SEPAY_ACCOUNT_NUMBER=<SO_TAI_KHOAN>
SEPAY_ACCOUNT_NAME=<TEN_CHU_TK>

# ---- CoinRemitter ----
COINREMITTER_API_KEY=<API_KEY>
COINREMITTER_PASSWORD=<PASSWORD>
COINREMITTER_WALLET_LTC=
COINREMITTER_WALLET_BTC=
COINREMITTER_WALLET_ETH=
COINREMITTER_WALLET_USDT=

# ---- Webhook Server ----
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_BASE_URL=http://160.191.245.231:8080

# ---- Supabase (PostgreSQL) ----
DATABASE_URL=postgresql://postgres:<DB_PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres

# ---- Cài đặt chung ----
EXCHANGE_RATE=26000
MIN_DEPOSIT_VND=10000
MIN_DEPOSIT_USD=1.0
PAYMENT_EXPIRY_MINUTES=30
"@ | Out-File -FilePath "C:\Users\Administrator\Desktop\topupfast\.env" -Encoding utf8
```

Hoặc mở Notepad để điền tay:
```powershell
notepad C:\Users\Administrator\Desktop\topupfast\.env
```

---

## BƯỚC 5 — Tạo bảng trong Supabase

1. Vào [supabase.com](https://supabase.com) → project → **SQL Editor**
2. Mở file `schema.sql` trong repo, copy toàn bộ và paste vào SQL Editor
3. Nhấn **Run**

---

## BƯỚC 6 — Chạy thử (kiểm tra lỗi)

```powershell
cd C:\Users\Administrator\Desktop\topupfast
python main.py
```

> Thấy `Logged in as BotName#0000` và `Webhook server running on port 8080` là OK  
> Nhấn `Ctrl+C` để dừng

---

## BƯỚC 7 — Cài NSSM (chạy bot như Windows Service, tự khởi động khi reboot)

```powershell
# Tải NSSM
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$env:TEMP\nssm.zip"
Expand-Archive "$env:TEMP\nssm.zip" -DestinationPath "$env:TEMP\nssm"
Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" -Destination "C:\Windows\System32\nssm.exe"

# Đăng ký service
nssm install TopUpFast python
nssm set TopUpFast AppDirectory C:\Users\Administrator\Desktop\topupfast
nssm set TopUpFast AppParameters main.py
nssm set TopUpFast AppStdout C:\Users\Administrator\Desktop\topupfast\bot.log
nssm set TopUpFast AppStderr C:\Users\Administrator\Desktop\topupfast\error.log
nssm set TopUpFast Start SERVICE_AUTO_START

# Khởi động service
nssm start TopUpFast
nssm status TopUpFast
```

---

## BƯỚC 8 — Mở Port 8080 trên Windows Firewall

```powershell
New-NetFirewallRule -DisplayName "TopUpFast Webhook" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

---

## Lệnh quản lý hàng ngày

```powershell
# Xem trạng thái bot
nssm status TopUpFast

# Xem log
Get-Content C:\Users\Administrator\Desktop\topupfast\bot.log -Tail 50

# Xem log lỗi
Get-Content C:\Users\Administrator\Desktop\topupfast\error.log -Tail 50

# Dừng bot
nssm stop TopUpFast

# Khởi động lại bot
nssm restart TopUpFast

# Cập nhật code từ GitHub rồi restart
cd C:\Users\Administrator\Desktop\topupfast
git pull
nssm restart TopUpFast
```

---

## Gỡ service (nếu cần xoá)

```powershell
nssm stop TopUpFast
nssm remove TopUpFast confirm
```

---

## Lưu ý bảo mật

- **KHÔNG** commit file `.env` lên GitHub (đã có trong `.gitignore`)
- Reset Discord Bot Token tại: [discord.com/developers/applications](https://discord.com/developers/applications) → Bot → Reset Token
- Reset Supabase DB password tại: Supabase → Settings → Database → Reset database password
- Đổi password VPS sau khi setup xong
