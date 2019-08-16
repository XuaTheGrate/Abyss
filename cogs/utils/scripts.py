import asyncio
import re
import os
import shlex
from contextlib import suppress

from discord.ext import ui


ID_GETTER = re.compile(r"@!ID:([0-9]+)!@")


_help = {}
for lang in os.listdir("cogs/utils/scripts"):
    with open(f"cogs/utils/scripts/{lang}/_help.xls") as f:
        data = f.readlines()
    d = {}
    for l in data:
        k, v = shlex.split(l)
        d[k] = v
    _help[lang] = d

assert 'en_US' in _help
assert len(_help['en_US']) > 0


SCRIPT_IDS = {}


for file in os.listdir("cogs/utils/scripts/en_US"):
    if not file.startswith("_"):
        with open(f"cogs/utils/scripts/en_US/{file}") as f:
            line = f.readline()
        mid = ID_GETTER.match(line)
        assert mid is not None
        SCRIPT_IDS[file] = int(mid.group(1))


scripts = [l for l, v in sorted(SCRIPT_IDS.items(), key=lambda m: m[1])]


class Choices(ui.Session):
    def __init__(self, question, *choices):
        super().__init__(timeout=180)
        self.question = question
        self.choices = {f'{a+1}\u20e3': c for a, c in enumerate(choices)}
        self.result = None
        for c in choices:
            self.add_button(self.make_choice, c)

    async def send_initial_message(self):
        return await self.context.send(f"> {self.question}\n\n"+"\n".join(f'{k} {v}' for k, v in self.choices.items()))

    async def stop(self):
        with suppress(Exception):
            await self.message.clear_reactions()
        await self.context.bot.redis.hset(f"choices@{self.context.author.id}", self.question, self.result)

    async def make_choice(self, payload):
        self.result = self.choices[str(payload)]
        await self.stop()


def check(msg, waiter):
    def inner(r, u):
        return str(r.emoji) in ('\u25b6', '⏹') and \
            u == waiter and \
            r.message.id == msg.id
    return inner


async def wait_next(bot, message, user):
    await message.add_reaction('⏹')
    await message.add_reaction('\u25b6')
    try:
        r, u = await bot.wait_for("reaction_add", check=check(message, user), timeout=180)
    except asyncio.TimeoutError:
        return False
    else:
        if str(r.emoji) == '\u25b6':
            return True
        return False
    finally:
        with suppress(Exception):
            await message.clear_reactions()


async def do_script(ctx, script, lang="en_US"):
    path = f"cogs/utils/scripts/{lang}/{script}.xls"
    if not os.path.isfile(path):
        if lang == 'en_US':
            raise TypeError(f"no such file: {path}")
        log.warning(f"no such file: {path}")
        return await do_script(ctx, script)

    with open(path) as f:
        data = f.read()

    ctx.cln = 0
    ctx.current_script = script+'.xls'

    skip = await ctx.bot.redis.get(f"breakpoint@{ctx.author.id}")
    snum, lnum = skip.decode().split(':')
    if scripts[int(snum)] == ctx.current_script:
        skip = int(lnum)  # we were partway in this script so lets jump to where we were
    else:
        skip = 0  # this is a new script with an outdated breakpoint, so lets erase it
        await ctx.bot.redis.delete(f"breakpoint@{ctx.author.id}")

    lines = iter(data.splitlines())
    prevline = None

    for line in data:
        l = line.strip().format(ctx=ctx)

        if not l or l.startswith(('#', '@!')):
            continue

        if l.startswith('$choice') and ctx.cln >= skip:
            cmd, question, *choices = shlex.split(l.lstrip("$"))
            outcomes = {}
            while True:
                ln = next(lines)
                ch, an = shlex.split(ln)
                assert ch in choices
                outcomes[ch] = an.rstrip("$")
                if an.endswith("$"):
                    break

            s = Choices(question, *choices)
            await s.start(ctx)
            r = s.result
            if not r:
                await breakpoint(ctx, stop=True)
                return True
            await ctx.send(outcomes[r])
            continue

        if l.startswith("$") and ctx.cln >= skip:
            cmd, *args = shlex.split(l.strip('$'))
            cmd = globals()[cmd]
            try:
                await cmd(ctx, *args)
            except StopIteration:
                return True
            continue

        if ctx.cln >= skip:  # skip so we continue where we left off
            m = await ctx.send(l)
            if not await wait_next(ctx.bot, m, ctx.author):
                await breakpoint(ctx, stop=True)
                return False
        ctx.cln += 1

    return True


# internal commands defined here

async def breakpoint(ctx, scriptnum=None, linenum=None, *, stop=False):
    scriptnum = scriptnum or scripts.index(ctx.current_script)
    linenum = linenum or ctx.cln
    await ctx.bot.redis.set(f"breakpoint@{ctx.author.id}", f'{scriptnum}:{linenum}')
    await ctx.send("*Saving progress...*", delete_after=3)
    if not stop:
        raise StopIteration


async def queuebgm(ctx, track, aftertrack=None):
    """Start playing a track in voice, if possible.
    Optional aftertrack param to loop after the first finishes.
    If undefined, will loop "track"."""
    pass


async def mapset(ctx, mapname):
    """Change the players map."""
    pass
