import datetime

import discord
from discord.ext import commands

from .utils.formats import format_exc
from .utils import i18n


_handles = {
    commands.DisabledCommand: "This command is disabled, because it is broken, "
                              "in development or some other unspecified reason.",
    commands.BadArgument: "Bad argument passed to this command. Refer to the help command.",
    commands.BotMissingPermissions: "I am missing permissions to run this command. "
                                    "Check the help command for required permissions.",
    commands.CheckFailure: "You are unauthorized to use this command.",
    commands.MissingPermissions: "You are missing permissions to run this command. "
                                 "Check the help command for required permissions.",
    commands.MissingRequiredArgument: "Not enough arguments were passed to this command. "
                                      "Check the help command for proper arguments.",
    commands.NotOwner: "This command is for my developers only.",
    commands.UserInputError: "Failed to parse arguments for this command. "
                             "Check the help command for proper arguments.",
    commands.TooManyArguments: "Too many arguments were passed to the command. "
                               "Check the help command for proper arguments."
}


class ErrorHandler(commands.Cog):
    """The error handler for the bot. You shouldn't be reading this."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        target = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links:
                target = channel
                break
        if not target:
            return
        embed = discord.Embed()
        embed.description = ("\N{REGIONAL INDICATOR SYMBOL LETTER G}\N{REGIONAL INDICATOR SYMBOL LETTER B} "
                             "Hello! I'm Abyss. Use `$locale set en_US` to change your personal locale.")
        # await target.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc, *, force=False):
        if ctx.cog and commands.Cog._get_overridden_method(ctx.cog.cog_command_error) and not force:
            return

        if isinstance(exc, commands.CommandInvokeError):
            ctx.command.reset_cooldown(ctx)
            exc = exc.original
            await ctx.send("An internal error occured.")
            self.bot.send_error(f"""Error during execution of command
`{ctx.message.clean_content}`
User: {ctx.author}
Guild: {ctx.guild}
Timestamp: {ctx.message.created_at}
Permissions: {ctx.channel.permissions_for(ctx.author).value}
Bot permissions: {ctx.channel.permissions_for(ctx.me).value}
```py
{format_exc(exc)}
```""")
            return

        if isinstance(exc, (commands.CommandNotFound, commands.NoPrivateMessage)):
            return

        if isinstance(exc, commands.CommandOnCooldown):
            time = datetime.timedelta(seconds=exc.retry_after)
            await ctx.send("Command on cooldown, try again in `{time}`.".format(time=time))
            return

        ctx.command.reset_cooldown(ctx)

        if isinstance(exc, commands.TooManyArguments):
            if isinstance(ctx.command, commands.Group):
                return

        msg = _handles.get(type(exc), None)

        if not msg:
            log.warning(f"No handle for {type(exc)}.")
            return

        await ctx.send(_(msg))


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
