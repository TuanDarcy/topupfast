"""
SePay integration - Bank VN payment (chuyển khoản nội địa)

Flow:
  1. Bot tạo mã TFA duy nhất (VD: TFA12345)
  2. Bot gửi QR code VietQR cho user kèm nội dung chuyển khoản
  3. User chuyển khoản với nội dung đúng TFA code
  4. SePay gửi webhook đến /webhook/sepay
  5. Bot tìm giao dịch theo TFA, cộng tiền cho user

Cấu hình webhook trên SePay:
  https://my.sepay.vn -> Tài khoản ngân hàng -> Cấu hình webhook
  URL: https://your-server.com/webhook/sepay
"""

import re
import urllib.parse

from config import SEPAY_API_TOKEN, SEPAY_BANK_CODE, SEPAY_ACCOUNT_NUMBER, SEPAY_ACCOUNT_NAME


def generate_qr_url(amount_vnd: int, tfa_code: str) -> str:
    """
    Tạo URL ảnh QR VietQR qua API của SePay.
    Ảnh QR được tạo tự động phía server, không cần thư viện bên ngoài.
    """
    desc = urllib.parse.quote(tfa_code)
    return (
        f"https://qr.sepay.vn/img"
        f"?acc={SEPAY_ACCOUNT_NUMBER}"
        f"&bank={SEPAY_BANK_CODE}"
        f"&amount={amount_vnd}"
        f"&des={desc}"
        f"&template=compact2"
    )


def validate_webhook(headers: dict) -> bool:
    """
    Kiểm tra tính hợp lệ của webhook từ SePay.
    SePay gửi token trong header Authorization: Bearer <token>
    """
    if not SEPAY_API_TOKEN:
        # Chưa cấu hình secret - chỉ chấp nhận khi dev/test
        return True
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    return auth == f"Bearer {SEPAY_API_TOKEN}"


def extract_tfa_code(content: str) -> str | None:
    """Trích xuất mã TFA từ nội dung chuyển khoản (VD: 'chuyen tien TFA12345 ck')."""
    match = re.search(r"TFA\d{5}", content.upper())
    return match.group(0) if match else None
