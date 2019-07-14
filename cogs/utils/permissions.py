from discord.ext.commands.errors import MissingPermissions, BotMissingPermissions
from discord.ext.commands import check


def check_permissions(*, allow_owner=True, **permissions):
    """A decorator applied to commands.
    This is an alternative to :func:`discord.ext.commands.has_permissions`,
    which stores the permissions inside ``command.callback.required_permissions.``

    Parameters
    ----------
    allow_owner: :class:`bool`
        If this is `True` (default), the owner of the bot will automatically
        bypass the permissions set.
    \*\*permissions
        A mapping of permissions to check against the invocating user.

    Example
    -------

    .. code-block:: python3

        >>> @bot.command()
        ... @check_permissions(manage_messages=True)
        ... async def cool(ctx):
        ...     await ctx.send("You are cool.")

        >>> "manage_messages" in cool.callback.required_permissions
        True
        """
    def inner(func):
        func.required_permissions = list(permissions)

        async def predicate(ctx):
            if allow_owner and await ctx.bot.is_owner(ctx.author):
                return True

            perms = ctx.channel.permissions_for(ctx.author)

            missing = [perm for perm, value in permissions.items() if getattr(perms, perm, None) != value]

            if not missing:
                return True

            raise MissingPermissions(missing)
        return check(predicate)(func)
    return inner


def bot_check_permissions(**permissions):
    """Similar to :func:`.check_permissions`, but for the bot."""

    def inner(func):
        func.bot_required_permissions = list(permissions)

        async def predicate(ctx):
            perms = ctx.channel.permissions_for(ctx.me)

            missing = [perm for perm, value in permissions.items() if getattr(perms, perm, None) != value]

            if not missing:
                return True

            raise BotMissingPermissions(missing)

        return check(predicate)(func)

    return inner
