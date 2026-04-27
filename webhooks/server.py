"""
Webhook server (aiohttp) nhận thông báo thanh toán từ SePay và CoinRemitter.
Chạy cùng process với Discord bot thông qua asyncio.gather().

Endpoints:
  GET  /health                  - health check
  POST /webhook/sepay           - nhận từ SePay khi có chuyển khoản ngân hàng
  POST /webhook/coinremitter    - nhận từ CoinRemitter khi invoice được thanh toán
"""

import asyncio
import logging

import aiohttp.web
import discord

import services.database as db
from config import EXCHANGE_RATE, WEBHOOK_HOST, WEBHOOK_PORT
from services.sepay import validate_webhook as sepay_validate, extract_tfa_code

logger = logging.getLogger(__name__)


class WebhookServer:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.app = aiohttp.web.Application()
        self.app.router.add_get("/health", self._health)
        self.app.router.add_post("/webhook/sepay", self._sepay)
        self.app.router.add_post("/webhook/coinremitter", self._coinremitter)

    # -------------------------------------------------------------- routes --

    async def _health(self, _: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"status": "ok"})

    async def _sepay(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Xử lý webhook từ SePay."""
        try:
            if not sepay_validate(dict(request.headers)):
                logger.warning("SePay webhook: xác thực thất bại")
                return aiohttp.web.Response(status=401, text="Unauthorized")

            data: dict = await request.json()
            logger.info(f"SePay webhook: {data}")

            content: str = (
                data.get("content")
                or data.get("transferContent")
                or data.get("description")
                or ""
            )
            amount_vnd: int = int(data.get("transferAmount") or data.get("amount") or 0)

            tfa = extract_tfa_code(content)
            if not tfa:
                logger.warning(f"SePay: không tìm thấy TFA trong nội dung: {content!r}")
                return aiohttp.web.json_response({"success": False, "msg": "TFA not found"})

            tx = await db.get_transaction_by_tfa(tfa)
            if not tx:
                logger.warning(f"SePay: không có giao dịch pending cho TFA {tfa}")
                return aiohttp.web.json_response({"success": False, "msg": "Transaction not found"})

            amount_usd = round(amount_vnd / EXCHANGE_RATE, 4)

            await db.update_transaction(tx["id"], status="completed",
                                        amount_usd=amount_usd, amount_vnd=amount_vnd)
            await db.add_balance(tx["discord_id"], amount_usd)

            logger.info(f"SePay OK: TFA={tfa} | {amount_vnd:,} VND = ${amount_usd} USD | user={tx['discord_id']}")
            asyncio.create_task(
                self._notify(tx, amount_usd=amount_usd, amount_vnd=amount_vnd, kind="bank")
            )
            return aiohttp.web.json_response({"success": True})

        except Exception:
            logger.exception("SePay webhook lỗi")
            return aiohttp.web.Response(status=500, text="Internal error")

    async def _coinremitter(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Xử lý webhook từ CoinRemitter."""
        try:
            data: dict = await request.json()
            logger.info(f"CoinRemitter webhook: {data}")

            # CoinRemitter gửi nhiều event; chỉ xử lý khi paid
            status = str(data.get("status", "")).lower()
            if status not in ("paid", "paid_partial"):
                return aiohttp.web.json_response({"success": True, "msg": f"ignored status={status}"})

            invoice_id: str = str(data.get("id") or data.get("invoice_id") or "")
            if not invoice_id:
                return aiohttp.web.json_response({"success": False, "msg": "missing invoice id"})

            tx = await db.get_transaction_by_provider_ref(invoice_id)
            if not tx:
                logger.warning(f"CoinRemitter: không tìm thấy giao dịch cho invoice {invoice_id}")
                return aiohttp.web.json_response({"success": False, "msg": "Transaction not found"})

            if tx["status"] == "completed":
                return aiohttp.web.json_response({"success": True, "msg": "already completed"})

            # Lấy số tiền USD thực tế từ webhook (CoinRemitter gửi paid_fiat)
            amount_usd = float(
                data.get("paid_fiat") or data.get("total_amount_in_fiat") or tx.get("amount_usd", 0)
            )

            await db.update_transaction(tx["id"], status="completed", amount_usd=amount_usd)
            await db.add_balance(tx["discord_id"], amount_usd)

            logger.info(f"CoinRemitter OK: invoice={invoice_id} | ${amount_usd} | user={tx['discord_id']}")
            asyncio.create_task(
                self._notify(tx, amount_usd=amount_usd, amount_vnd=None, kind="crypto")
            )
            return aiohttp.web.json_response({"success": True})

        except Exception:
            logger.exception("CoinRemitter webhook lỗi")
            return aiohttp.web.Response(status=500, text="Internal error")

    # --------------------------------------------------------- notification --

    async def _notify(
        self,
        tx: dict,
        *,
        amount_usd: float,
        amount_vnd: int | None,
        kind: str,
    ) -> None:
        """Cập nhật tin nhắn Discord khi thanh toán xong."""
        try:
            channel_id = tx.get("discord_channel_id")
            message_id = tx.get("discord_message_id")
            if not channel_id:
                return

            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                return

            if kind == "bank":
                desc = (
                    f"💰 Số tiền: `{amount_vnd:,} VND` (~`${amount_usd:.4f} USD`)\n"
                    f"📊 Kiểm tra số dư: `/sodu`"
                )
            else:
                coin = tx.get("coin", "")
                desc = (
                    f"💰 Số tiền: `${amount_usd:.4f} USD` ({coin})\n"
                    f"📊 Kiểm tra số dư: `/sodu`"
                )

            embed = discord.Embed(
                title="✅ Nạp tiền thành công!",
                description=desc,
                color=discord.Color.green(),
            )

            if message_id:
                try:
                    msg = await channel.fetch_message(int(message_id))
                    await msg.edit(embed=embed, view=None)
                    return
                except discord.NotFound:
                    pass

            # Fallback: gửi message mới
            await channel.send(f"<@{tx['discord_id']}>", embed=embed)

        except Exception:
            logger.exception("Không thể notify Discord")

    # -------------------------------------------------------------- start --

    async def start(self) -> None:
        runner = aiohttp.web.AppRunner(self.app, access_log=logger)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
        await site.start()
        logger.info(f"Webhook server đang chạy tại http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
        # Giữ task chạy mãi
        while True:
            await asyncio.sleep(3600)
