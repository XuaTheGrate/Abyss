import asyncio
import re
import os
import shlex
from contextlib import suppress

from discord.ext import ui
NL = '\n'
NNL = '\\n'


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
            log.debug(f"Choices: added {c.encode('unicode-escape')} as button")

    async def send_initial_message(self):
        log.debug("Choices: start")
        return await self.context.send(f"> {self.question}\n\n"+"\n".join(f'{k} {v}' for k, v in self.choices.items()))

    async def stop(self):
        with suppress(Exception):
            await self.message.clear_reactions()
            log.debug("Choices: remove reactions")
        await self.context.bot.redis.hset(f"choices@{self.context.author.id}", self.question, self.result)
        log.debug("Choices: stop")

    async def make_choice(self, payload):
        log.debug(f"Choices: received {str(payload.emoji).encode('unicode-escape')}")
        self.result = self.choices[str(payload.emoji)]
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

    with open(path, encoding='utf-8') as f:
        data = f.read()

    log.debug(f"opened and read file {script} ({lang})")

    ctx.cln = 0
    ctx.current_script = script+'.xls'

    skip = await ctx.bot.redis.get(f"breakpoint@{ctx.author.id}")
    if skip:
        log.debug(f"skip key found for {ctx.author}")
        snum, lnum = skip.decode().split(':')
        if scripts[int(snum)] == ctx.current_script:
            skip = int(lnum)  # we were partway in this script so lets jump to where we were
            log.debug(f"skip key is for this script")
        else:
            skip = 0  # this is a new script with an outdated breakpoint, so lets erase it
            log.debug(f"skip key is not for this script")
            await ctx.bot.redis.delete(f"breakpoint@{ctx.author.id}")
    else:
        skip = 0
        log.debug(f"no script key found for {ctx.author}")

    lines = iter(data.split('\n'))

    for line in lines:
        l = line.strip().format(ctx=ctx)

        if not l or l.startswith(('#', '@!')):
            continue
        log.debug(f"new line in script: {l.startswith('$choice')} {ctx.cln >= skip} {l.replace(NL, NNL)}")
        if l.startswith('$choice') and ctx.cln >= skip:
            log.debug("choice command found")
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
            log.debug("regular command found")
            cmd, *args = shlex.split(l.strip('$'))
            cmd = globals()[cmd]
            try:
                await cmd(ctx, *args)
            except StopIteration:
                return True
            continue

        if ctx.cln >= skip:  # skip so we continue where we left off
            log.debug("regular script line, sending")
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
