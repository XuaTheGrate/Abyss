import traceback

from discord.ext import commands

from cogs.utils.player import Player


def prettyjson(obj, indent=4, maxlinelength=80):
    """Renders JSON content with indentation and line splits/concatenations to fit maxlinelength.
    Only dicts, lists and basic types are supported"""

    items, _ = getsubitems(obj, itemkey="", islast=True, maxlinelength=maxlinelength)
    res = indentitems(items, indent, indentcurrent=0)
    return res


def getsubitems(obj, itemkey, islast, maxlinelength):
    items = []
    can_concat = True  # assume we can concatenate inner content unless a child node returns an expanded list

    isdict = isinstance(obj, dict)
    islist = isinstance(obj, list)
    istuple = isinstance(obj, tuple)

    # building json content as a list of strings or child lists
    if isdict or islist or istuple:
        if isdict:
            opening, closing, keys = ("{", "}", iter(obj.keys()))
        elif islist:
            opening, closing, keys = ("[", "]", range(0, len(obj)))
        elif istuple:
            opening, closing, keys = ("[", "]", range(0, len(obj)))  # tuples are converted into json arrays
        else:
            return

        if itemkey != "":
            opening = itemkey + ": " + opening
        if not islast:
            closing += ","

        # Get list of inner tokens as list
        count = 0
        subitems = []
        for k in keys:
            count += 1
            islast_ = count == len(obj)
            itemkey_ = ""
            if isdict:
                itemkey_ = basictype2str(k)
            inner, can_concat_ = getsubitems(obj[k], itemkey_, islast_, maxlinelength)  # inner = (items, indent)
            subitems.extend(inner)  # inner can be a string or a list
            can_concat = can_concat and can_concat_  # if a child couldn't concat, then we are not able either

        # atttempt to concat subitems if all fit within maxlinelength
        if can_concat:
            totallength = 0
            for item in subitems:
                totallength += len(item)
            totallength += len(subitems) - 1  # spaces between items
            if totallength <= maxlinelength:
                k = ""
                for item in subitems:
                    k += item + " "  # add space between items, comma is already there
                k = k.strip()
                subitems = [k]  # wrap concatenated content in a new list
                if len(opening) + totallength + len(closing) <= maxlinelength:
                    items.append(opening + subitems[0] + closing)
            else:
                can_concat = False

        if not can_concat:
            items.append(opening)  # opening brackets
            items.append(subitems)  # Append children to parent list as a nested list
            items.append(closing)  # closing brackets

    else:
        # basic types
        strobj = itemkey
        if strobj != "":
            strobj += ": "
        strobj += basictype2str(obj)
        if not islast:
            strobj += ","
        items.append(strobj)

    return items, can_concat


def basictype2str(obj):
    if isinstance(obj, str):
        strobj = "\"" + str(obj) + "\""
    elif isinstance(obj, bool):
        strobj = {True: "true", False: "false"}[obj]
    elif obj is None:
        strobj = 'null'
    else:
        strobj = str(obj)
    return strobj


def indentitems(items, indent, indentcurrent):
    """Recursively traverses the list of json lines, adds indentation based on the current depth"""
    res = ""
    indentstr = " " * indentcurrent
    for item in items:
        if isinstance(item, list):
            res += indentitems(item, indent, indentcurrent + indent)
        else:
            res += indentstr + item + "\n"
    return res


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


class NotSearched(commands.CommandError):
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
            await ctx.player._populate_skills(ctx.bot)
        return True

    return commands.check(predicate)(func)
