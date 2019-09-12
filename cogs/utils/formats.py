import traceback

from discord.ext import commands


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
