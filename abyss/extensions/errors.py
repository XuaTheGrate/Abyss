import datetime
import traceback
import uuid

import discord
from discord.ext import commands

from .utils.checks import key_fmt


def format_exception(exc):
    return ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hook = discord.Webhook.from_url(bot.config.error_hook, adapter=discord.AsyncWebhookAdapter(bot.session))

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc):
        if isinstance(exc, (commands.CommandNotFound, commands.NotOwner, commands.NoPrivateMessage)):
            return

        if isinstance(exc, commands.CommandOnCooldown):
            msg = "You are running commands too quickly! Take a breather; `{}`"
            await ctx.send(msg.format(datetime.timedelta(seconds=exc.retry_after)))
            return

        # noinspection PyProtectedMember
        bucket = ctx.command._better_cooldown_bucket
        if bucket is not None:
            key = key_fmt(ctx, bucket)
            await self.bot.redis.decr(key)
            await self.bot.redis.persist(key)

        if False:
            ...
        else:
            if isinstance(exc, commands.CommandInvokeError):
                exc = exc.original
            unique = uuid.uuid4()
            embed = discord.Embed(timestamp=ctx.message.created_at,
                                  colour=discord.Colour.red(),
                                  title=f'Error occured in command "{ctx.command.qualified_name}"')
            embed.set_footer(text=str(unique))
            embed.add_field(name="Extra Information", value=f"""
Author: {ctx.author} ({ctx.author.id})
Guild: {ctx.guild or "Direct Message"} {f"({ctx.guild.id})" if ctx.guild else ""}
[Jump URL]({ctx.message.jump_url})
[Permissions](https://discordapi.com/permissions.html#{ctx.me.guild_permissions.value if ctx.me else 0})
""", inline=False)
            embed.add_field(name="Traceback", value=f'```py\n{format_exception(exc)}\n```')
            await self.hook.send(embed=embed, username=("Abyss (Beta)" if self.bot.debug else "Abyss") + " Errors",
                                 avatar_url=ctx.bot.user.avatar_url)
            await ctx.send(f"""An error occured during the processing of this command.
Join my server to know when this issue is fixed.
UID: `{unique}`""")


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
