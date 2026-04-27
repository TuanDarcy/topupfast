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
            try:
                await self.tree.sync(guild=guild)
                logger.info(f"Slash commands synced to guild {DISCORD_GUILD_ID}")
            except discord.errors.Forbidden:
                logger.warning(
                    f"Cannot sync to guild {DISCORD_GUILD_ID} (bot not in guild or missing access). "
                    "Falling back to global sync (may take up to 1 hour)."
                )
                await self.tree.sync()
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally (may take up to 1 hour)")

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
        """Auto-add new member to DB and send welcome message."""
        if member.bot:
            return
        import services.database as db
        from config import WELCOME_CHANNEL_ID, RULES_CHANNEL_ID, VERIFY_CHANNEL_ID
        avatar = str(member.display_avatar.url) if member.display_avatar else None
        await db.get_or_create_user(str(member.id), avatar)
        logger.info(f"New member: {member} ({member.id}) added to DB.")

        if WELCOME_CHANNEL_ID:
            channel = self.get_channel(WELCOME_CHANNEL_ID)
            if channel:
                rules_mention = f"<#{RULES_CHANNEL_ID}>" if RULES_CHANNEL_ID else "#rules"
                verify_mention = f"<#{VERIFY_CHANNEL_ID}>" if VERIFY_CHANNEL_ID else "#verify"
                embed = discord.Embed(
                    title="👋 Welcome to the server!",
                    description=(
                        f"Hey {member.mention}, welcome to **{member.guild.name}**!\n\n"
                        f"📖 Please read the rules in {rules_mention}\n"
                        f"✅ Then head over to {verify_mention} to verify and unlock all channels."
                    ),
                    color=discord.Color.green(),
                )
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                embed.set_footer(text=f"Member #{member.guild.member_count}")
                await channel.send(embed=embed)

    async def on_member_remove(self, member: discord.Member) -> None:
        """Send message when a member leaves."""
        if member.bot:
            return
        from config import WELCOME_CHANNEL_ID
        if WELCOME_CHANNEL_ID:
            channel = self.get_channel(WELCOME_CHANNEL_ID)
            if channel:
                embed = discord.Embed(
                    title="👋 Member Left",
                    description=f"**{member.name}** has left the server.",
                    color=discord.Color.red(),
                )
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                await channel.send(embed=embed)
