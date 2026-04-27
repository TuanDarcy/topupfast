import logging

import discord
from discord.ext import commands

from config import DISCORD_GUILD_ID

logger = logging.getLogger(__name__)


class TopUpBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True          # cần để đọc danh sách member
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="TopUpFast Bot",
        )

    async def setup_hook(self) -> None:
        await self.load_extension("bot.cogs.topup")

        if DISCORD_GUILD_ID:
            guild = discord.Object(id=DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Slash commands synced đến guild {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            logger.info("Slash commands synced toàn cục (có thể mất tới 1 giờ)")

    async def on_ready(self) -> None:
        logger.info(f"Đăng nhập: {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="💰 /nap để nạp tiền",
            )
        )
        await self._sync_members()

    async def _sync_members(self) -> None:
        """Thêm toàn bộ member của guild vào DB (trừ bot)."""
        import services.database as db
        guild = self.get_guild(DISCORD_GUILD_ID) if DISCORD_GUILD_ID else None
        if guild is None:
            return
        count = 0
        async for member in guild.fetch_members(limit=None):
            if member.bot:
                continue
            avatar = str(member.display_avatar.url) if member.display_avatar else None
            await db.get_or_create_user(str(member.id), avatar)
            count += 1
        logger.info(f"Đồng bộ {count} member vào database.")

    async def on_member_join(self, member: discord.Member) -> None:
        """Tự động thêm member mới khi vào server và gửi tin chào."""
        if member.bot:
            return
        import services.database as db
        from config import WELCOME_CHANNEL_ID
        avatar = str(member.display_avatar.url) if member.display_avatar else None
        await db.get_or_create_user(str(member.id), avatar)
        logger.info(f"Member mới: {member} ({member.id}) đã được thêm vào DB.")

        if WELCOME_CHANNEL_ID:
            channel = self.get_channel(WELCOME_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="👋 Thành viên mới!",
                    description=f"{member.mention} vừa tham gia server.",
                    color=discord.Color.green(),
                )
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                embed.set_footer(text=f"Thành viên thứ {member.guild.member_count}")
                await channel.send(embed=embed)

    async def on_member_remove(self, member: discord.Member) -> None:
        """Gửi tin khi member rời server."""
        if member.bot:
            return
        from config import WELCOME_CHANNEL_ID
        if WELCOME_CHANNEL_ID:
            channel = self.get_channel(WELCOME_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="👋 Thành viên rời đi",
                    description=f"**{member.name}** đã rời server.",
                    color=discord.Color.red(),
                )
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                await channel.send(embed=embed)
