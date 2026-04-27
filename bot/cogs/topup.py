"""
TopUp Cog - tất cả các lệnh và UI liên quan đến nạp tiền.

Slash commands:
  /nap     - Mở menu nạp tiền (Bank VN hoặc Crypto)
  /sodu    - Xem số dư hiện tại
  /lichsu  - Xem 10 giao dịch gần nhất

Flow nạp Bank VN (SePay):
  /nap -> [💳 Bank VN] -> Modal nhập số VND
       -> Bot gửi QR + mã TFA -> User chuyển khoản
       -> SePay webhook -> balance cộng -> message cập nhật ✅

Flow nạp Crypto (CoinRemitter):
  /nap -> [🪙 Crypto] -> Chọn coin -> Modal nhập số USD
       -> Bot tạo invoice -> Bot gửi địa chỉ ví + link invoice
       -> CoinRemitter webhook -> balance cộng -> message cập nhật ✅
"""

import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import services.database as db
from config import (
    EXCHANGE_RATE,
    MIN_DEPOSIT_USD,
    MIN_DEPOSIT_VND,
    PAYMENT_EXPIRY_MINUTES,
)
from services.coinremitter import SUPPORTED_COINS, create_invoice, get_available_coins
from services.sepay import generate_qr_url

logger = logging.getLogger(__name__)


# ================================================================= Modals ==

class BankAmountModal(discord.ui.Modal, title="💳 Nạp tiền qua Bank VN"):
    amount_input = discord.ui.TextInput(
        label="Số tiền (VND)",
        placeholder=f"Ví dụ: 100000 (tối thiểu {50_000:,} VND)",
        min_length=4,
        max_length=12,
    )

    def __init__(self, cog: "TopUpCog") -> None:
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.amount_input.value.replace(",", "").replace(".", "").strip()
        try:
            amount_vnd = int(raw)
        except ValueError:
            await interaction.response.send_message(
                "❌ Số tiền không hợp lệ. Vui lòng nhập số nguyên.", ephemeral=True
            )
            return

        if amount_vnd < MIN_DEPOSIT_VND:
            await interaction.response.send_message(
                f"❌ Số tiền tối thiểu là **{MIN_DEPOSIT_VND:,} VND**.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        user = await db.get_or_create_user(
            str(interaction.user.id),
            _avatar(interaction.user),
        )

        # Tạo mã TFA duy nhất
        tfa_code = await _unique_tfa()
        amount_usd = round(amount_vnd / EXCHANGE_RATE, 4)
        qr_url = generate_qr_url(amount_vnd, tfa_code)

        expires_at = datetime.utcnow() + timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
        expire_ts = int(expires_at.timestamp())

        tx = await db.create_transaction(
            discord_id=str(interaction.user.id),
            user_id=user["id"],
            type="bank",
            provider="sepay",
            amount_usd=amount_usd,
            amount_vnd=amount_vnd,
            currency="VND",
            tfa_code=tfa_code,
            qr_url=qr_url,
            discord_channel_id=str(interaction.channel_id),
        )

        embed = _bank_embed(amount_vnd, amount_usd, tfa_code, expire_ts, qr_url)
        view = CancelPaymentView(tx["id"])
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        # Lưu message ID để webhook có thể edit sau
        await db.update_transaction(tx["id"], discord_message_id=str(msg.id))

        # Background polling: tự detect khi webhook đã cập nhật DB
        asyncio.create_task(
            self.cog.poll_payment(tx["id"], msg, kind="bank")
        )


class CryptoAmountModal(discord.ui.Modal):
    amount_input = discord.ui.TextInput(
        label="Số tiền (USD)",
        placeholder="Ví dụ: 5",
        min_length=1,
        max_length=10,
    )

    def __init__(self, cog: "TopUpCog", coin: str) -> None:
        super().__init__(title=f"🪙 Nạp tiền qua {coin}")
        self.cog = cog
        self.coin = coin

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.amount_input.value.replace(",", ".").strip()
        try:
            amount_usd = float(raw)
        except ValueError:
            await interaction.response.send_message(
                "❌ Số tiền không hợp lệ.", ephemeral=True
            )
            return

        if amount_usd < MIN_DEPOSIT_USD:
            await interaction.response.send_message(
                f"❌ Số tiền tối thiểu là **${MIN_DEPOSIT_USD:.2f} USD**.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        user = await db.get_or_create_user(
            str(interaction.user.id),
            _avatar(interaction.user),
        )

        description = f"TopUpFast {interaction.user.name} ({interaction.user.id})"
        try:
            invoice = await create_invoice(self.coin, amount_usd, description)
        except Exception as exc:
            logger.error(f"CoinRemitter error: {exc}")
            await interaction.followup.send(
                "❌ Không thể tạo invoice. Vui lòng thử lại sau hoặc liên hệ admin.",
                ephemeral=True,
            )
            return

        tx = await db.create_transaction(
            discord_id=str(interaction.user.id),
            user_id=user["id"],
            type="crypto",
            provider="coinremitter",
            amount_usd=amount_usd,
            currency=self.coin,
            coin=self.coin,
            provider_ref=str(invoice.get("id", "")),
            invoice_url=invoice.get("url", ""),
            discord_channel_id=str(interaction.channel_id),
        )

        embed = _crypto_embed(invoice, self.coin, amount_usd)
        view = CancelPaymentView(tx["id"])
        msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await db.update_transaction(tx["id"], discord_message_id=str(msg.id))

        asyncio.create_task(
            self.cog.poll_payment(tx["id"], msg, kind="crypto")
        )


# ================================================================== Views ==

class PaymentTypeView(discord.ui.View):
    def __init__(self, cog: "TopUpCog") -> None:
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.button(label="💳 Bank VN", style=discord.ButtonStyle.primary)
    async def bank_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(BankAmountModal(self.cog))

    @discord.ui.button(label="🪙 Crypto", style=discord.ButtonStyle.secondary)
    async def crypto_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        coins = get_available_coins()
        if not coins:
            await interaction.response.send_message(
                "❌ Chưa có coin nào được cấu hình. Vui lòng liên hệ admin.", ephemeral=True
            )
            return
        view = CoinSelectView(self.cog)
        await interaction.response.send_message(
            "🪙 Chọn loại coin muốn nạp:", view=view, ephemeral=True
        )


class CoinSelectView(discord.ui.View):
    def __init__(self, cog: "TopUpCog") -> None:
        super().__init__(timeout=120)
        self.cog = cog
        options = [
            discord.SelectOption(label=label, value=coin)
            for coin, label in get_available_coins().items()
        ]
        select = discord.ui.Select(
            placeholder="Chọn coin...",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        coin = interaction.data["values"][0]
        await interaction.response.send_modal(CryptoAmountModal(self.cog, coin))


class CancelPaymentView(discord.ui.View):
    def __init__(self, tx_id: int) -> None:
        super().__init__(timeout=PAYMENT_EXPIRY_MINUTES * 60)
        self.tx_id = tx_id

    @discord.ui.button(label="❌ Hủy giao dịch", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await db.update_transaction(self.tx_id, status="failed")
        embed = discord.Embed(
            title="❌ Giao dịch đã hủy",
            description="Giao dịch đã được hủy.",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ================================================================ Helpers ==

def _avatar(user: discord.User | discord.Member) -> str | None:
    return str(user.display_avatar.url) if user.display_avatar else None


async def _unique_tfa() -> str:
    """Tạo mã TFA không trùng với giao dịch pending nào."""
    for _ in range(10):
        code = db.generate_tfa_code()
        if not await db.get_transaction_by_tfa(code):
            return code
    # Fallback: thêm prefix ngẫu nhiên
    import random, string
    return "TFA" + "".join(random.choices(string.digits, k=6))


def _bank_embed(
    amount_vnd: int, amount_usd: float, tfa_code: str, expire_ts: int, qr_url: str
) -> discord.Embed:
    embed = discord.Embed(
        title="💳 Nạp tiền qua Bank VN",
        description=(
            "Quét mã QR hoặc chuyển khoản thủ công với thông tin bên dưới.\n\n"
            f"💰 **Số tiền:** `{amount_vnd:,} VND` (~`${amount_usd:.4f} USD`)\n"
            f"📝 **Nội dung CK:** `{tfa_code}` *(bắt buộc)*\n"
            f"⏱️ **Hết hạn:** <t:{expire_ts}:R>\n\n"
            f"⚠️ Nhập **đúng** nội dung `{tfa_code}` để bot xác nhận tự động."
        ),
        color=discord.Color.blue(),
    )
    embed.set_image(url=qr_url)
    embed.set_footer(text="Bot tự động cộng tiền sau khi nhận được thanh toán.")
    return embed


def _crypto_embed(invoice: dict, coin: str, amount_usd: float) -> discord.Embed:
    address = invoice.get("address", "Không lấy được địa chỉ")
    invoice_url = invoice.get("url", "")
    total_coin = invoice.get("total_amount", "?")
    expire_on = invoice.get("expire_on", "")

    desc = (
        f"Gửi đúng số coin đến địa chỉ bên dưới.\n\n"
        f"💰 **Số tiền:** `{total_coin} {coin}` (~`${amount_usd:.2f} USD`)\n"
        f"📋 **Địa chỉ ví:**\n```\n{address}\n```\n"
    )
    if invoice_url:
        desc += f"🔗 **Invoice:** [Xem tại đây]({invoice_url})\n"
    if expire_on:
        desc += f"⏱️ **Hết hạn:** {expire_on}\n"

    embed = discord.Embed(
        title=f"🪙 Nạp tiền qua {coin}",
        description=desc,
        color=discord.Color.orange(),
    )
    embed.set_footer(text="Bot tự động cộng tiền sau khi nhận được thanh toán.")
    return embed


STATUS_ICONS = {"pending": "⏳", "completed": "✅", "failed": "❌", "expired": "⏰"}


# ================================================================== Cog ==

class TopUpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --------------------------------------------------------- /nap ------

    @app_commands.command(name="nap", description="Nạp tiền vào tài khoản")
    async def nap(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="💰 Nạp tiền",
            description=(
                "Chọn phương thức thanh toán:\n\n"
                "💳 **Bank VN** — Chuyển khoản nội địa (VND)\n"
                "🪙 **Crypto** — Bitcoin, Litecoin, Ethereum, USDT..."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(
            embed=embed, view=PaymentTypeView(self), ephemeral=True
        )

    # --------------------------------------------------------- /sodu ------

    @app_commands.command(name="sodu", description="Xem số dư tài khoản")
    async def sodu(self, interaction: discord.Interaction) -> None:
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.response.send_message(
                "❌ Bạn chưa có tài khoản. Hãy dùng `/nap` để nạp tiền.", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="💰 Số dư tài khoản",
            description=f"💵 **${user['balance']:.4f} USD**",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(
            url=user.get("avatar_url") or str(interaction.user.display_avatar.url)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------------------------------------- /lichsu ----

    @app_commands.command(name="lichsu", description="Xem 10 giao dịch nạp tiền gần nhất")
    async def lichsu(self, interaction: discord.Interaction) -> None:
        txs = await db.get_user_transactions(str(interaction.user.id))
        if not txs:
            await interaction.response.send_message(
                "📋 Chưa có lịch sử giao dịch.", ephemeral=True
            )
            return

        lines: list[str] = []
        for tx in txs:
            icon = STATUS_ICONS.get(tx["status"], "❓")
            date = str(tx["created_at"])[:10]
            if tx["type"] == "bank":
                amt = f"{tx.get('amount_vnd', 0):,} VND"
            else:
                amt = f"${tx.get('amount_usd', 0):.4f} ({tx.get('coin', '')})"
            lines.append(f"{icon} `{date}` — {amt}")

        embed = discord.Embed(
            title="📋 Lịch sử nạp tiền",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------------- background polling --

    async def poll_payment(
        self,
        tx_id: int,
        message: discord.WebhookMessage,
        *,
        kind: str,
    ) -> None:
        """
        Polling background task: kiểm tra DB mỗi 10 giây.
        Khi webhook đã cập nhật status -> completed, task cập nhật message.
        """
        max_checks = PAYMENT_EXPIRY_MINUTES * 6  # check mỗi 10s trong X phút
        for _ in range(max_checks):
            await asyncio.sleep(10)
            tx = await db.get_transaction(tx_id)
            if not tx:
                return

            if tx["status"] == "completed":
                if kind == "bank":
                    desc = (
                        f"💰 `{tx.get('amount_vnd', 0):,} VND` → "
                        f"`${tx.get('amount_usd', 0):.4f} USD` đã được cộng vào tài khoản.\n"
                        f"📊 Xem số dư: `/sodu`"
                    )
                else:
                    desc = (
                        f"💰 `${tx.get('amount_usd', 0):.4f} USD` ({tx.get('coin', '')}) "
                        f"đã được cộng vào tài khoản.\n📊 Xem số dư: `/sodu`"
                    )
                embed = discord.Embed(
                    title="✅ Nạp tiền thành công!",
                    description=desc,
                    color=discord.Color.green(),
                )
                try:
                    await message.edit(embed=embed, view=None)
                except Exception:
                    pass
                return

            if tx["status"] in ("failed", "expired"):
                return

        # Hết thời gian - đánh dấu expired
        await db.update_transaction(tx_id, status="expired")
        embed = discord.Embed(
            title="⏰ Giao dịch hết hạn",
            description="Giao dịch đã hết hạn. Dùng `/nap` để tạo giao dịch mới.",
            color=discord.Color.orange(),
        )
        try:
            await message.edit(embed=embed, view=None)
        except Exception:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TopUpCog(bot))
