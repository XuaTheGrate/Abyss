import datetime

from discord.ext import commands

from . import utils
from cogs.utils import i18n


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
    commands.NoPrivateMessage: "This command may not be used in DMs.",
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
    async def on_command_error(self, ctx, exc):
        if isinstance(exc, commands.CommandInvokeError):
            exc = exc.original
            await ctx.send(_("An internal error occured."))
            self.bot.send_error(f"""Error during execution of command
`{ctx.message.clean_content}`
User: {ctx.author}
Guild: {ctx.guild}
Timestamp: {ctx.message.created_at}
Permissions: {ctx.channel.permissions_for(ctx.author).value}
Bot permissions: {ctx.channel.permissions_for(ctx.me).value}
```py
{utils.format_exc(exc)}
```""")
            return

        if isinstance(exc, commands.CommandNotFound):
            return

        if isinstance(exc, commands.CommandOnCooldown):
            time = datetime.timedelta(seconds=exc.retry_after)
            await ctx.send(_("Command on cooldown, try again in `{time}`.").format(time=time))
            return

        if isinstance(exc, commands.TooManyArguments):
            if isinstance(ctx.command, commands.Group):
                return

        msg = _handles.get(type(exc), None)

        if not msg:
            self.bot.logger.warning(f"No handle for {type(exc)}.")
            return

        await ctx.send(_(msg))


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
