import asyncio
import base64
import os
from contextlib import suppress


def check(msg, waiter):
    def inner(r, u):
        return str(r.emoji) == '\u25b6' and \
            u == waiter and \
            r.message.id == msg.id
    return inner


async def wait_next(bot, message, user):
    await message.add_reaction('\u25b6')
    try:
        await bot.wait_for("reaction_add", check=check(message, user), timeout=180)
    except asyncio.TimeoutError:
        return False
    else:
        return True
    finally:
        with suppress(Exception):
            await message.clear_reactions()


async def do_script(ctx, script, lang="en_US"):
    path = f"cogs/utils/scripts/{lang}/{script}.scr"
    if not os.path.isfile(path):
        if lang == 'en_US':
            raise TypeError(f"no such file: {path}")
        return await do_script(ctx, script)

    with open(path) as f:
        data = base64.b64decode(f.read()).decode()

    for line in data.splitlines():
        m = await ctx.send(line.strip())
        if not await wait_next(ctx.bot, m, ctx.author):
            return False

    return True
