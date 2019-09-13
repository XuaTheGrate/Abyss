import traceback

from discord.ext import commands

from cogs.utils.player import Player


def format_exc(exc):
    """Helper function for formatting tracebacks.

    Parameters
    ----------
    exc: :class:`BaseException`
        The exception to format.

    Returns
    -------
    :class:`str`
        The formatted traceback."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


class SilentError(commands.CommandError):
    pass


class NoPlayer(commands.CommandError):
    pass


def ensure_player(func):
    async def predicate(ctx):
        try:
            ctx.player = ctx.bot.players.players[ctx.author.id]
        except KeyError:
            pdata = await ctx.bot.db.abyss.accounts.find_one({"owner": ctx.author.id})
            if not pdata:
                raise NoPlayer()
            ctx.player = ctx.bot.players.players[ctx.author.id] = Player(**pdata)
        return True

    return commands.check(predicate)(func)
