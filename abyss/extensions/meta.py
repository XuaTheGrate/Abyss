import discord
from discord.ext import commands


class Meta(commands.Cog):
    """Unsorted commands showing information about the bot."""

    @commands.command()
    async def ping(self, ctx):
        """Returns the bots latency with Discord."""
        # todo: http latency
        await ctx.send(f':ping_pong: {ctx.bot.latency*1000:.2f}ms')

    @commands.command()
    async def invite(self, ctx):
        """Returns the invite link for the bot."""
        permissions = discord.Permissions(
            read_messages=True,
            read_message_history=True,
            send_messages=True,
            embed_links=True,
            attach_files=True
        )
        await ctx.send(f'<{discord.utils.oauth_url(ctx.me.id, permissions)}>')


def setup(bot):
    bot.add_cog(Meta(bot))
