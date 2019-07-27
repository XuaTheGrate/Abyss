import discord
from discord.ext import commands


class Prefixes(commands.Cog):
    """Handles all prefix related actions."""
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def prefix(self, ctx: commands.Context):
        """Base command for prefix related commands.
        Empty invocation will show a list of all prefixes."""
        prefixes = await self.bot.prefixes_for(ctx.guild)
        prefixes = prefixes.copy()
        prefixes.remove(self.bot.user.mention)
        embed = discord.Embed(colour=discord.Colour.blurple(), title=f"{ctx.guild} prefixes")
        embed.description = "\n".join([f'• {p}' for p in prefixes])
        await ctx.send(embed=embed)

    @prefix.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx: commands.Context, *prefixes: str):
        """Adds prefixes to the available guild prefixes.
        Extraneous whitespace will be stripped.
        "thing " will become "thing"

        Parameters
        `*prefixes`
            A list of prefixes to add. Must be split by a single space.
            To add a prefix with a space in it, use quotes, e.g.
                `prefix add "foo bar"`
        """
        await self.bot.add_prefixes(ctx.guild, *prefixes)
        await ctx.send(self.bot.tick_yes)

    @prefix.command()
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx: commands.Context, *prefixes: str):
        """Removes prefixes available to the server.
        Will silently ignore unknown prefixes.
        Invoke the prefix command with no subcommand to see all
        available prefixes. You cannot remove the @mentions.

        Parameters
        `*prefixes`
            A list of prefixes to remove. Must be split by a single space.
            To remove a prefix with a space in it, use quotes, e.g.
                `prefix remove "foo bar"`
        """
        await self.bot.rem_prefixes(ctx.guild, *prefixes)
        await ctx.send(self.bot.tick_yes)


def setup(bot):
    bot.add_cog(Prefixes(bot))
