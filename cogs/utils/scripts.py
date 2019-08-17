import asyncio
import functools
import re
import os
import shlex
import subprocess
from contextlib import suppress

import discord
from discord.ext import ui

from .formats import format_exc


@property
def kill_track(self):
    if not hasattr(self, "_kill_track"):
        self._kill_track = asyncio.Event()
    return self._kill_track


discord.Guild.kill_track = kill_track

NL = '\n'
NNL = '\\n'


class StopScript(Exception):
    pass


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
        for c in self.choices:
            self.add_button(self.make_choice, c)
            # log.debug(f"Choices: added {c.encode('unicode-escape')} as button")

    async def handle_timeout(self):
        return await self.stop()

    async def send_initial_message(self):
        # log.debug("Choices: start")
        return await self.context.send(f"> {self.question}\n\n"+"\n".join(f'{k} {v}' for k, v in self.choices.items()))

    async def stop(self):
        with suppress(Exception):
            await super().stop()
            await self.message.clear_reactions()
            # log.debug("Choices: remove reactions")
        await self.context.bot.redis.hset(f"choices@{self.context.author.id}", self.question, self.result)
        # log.debug("Choices: stop")

    async def make_choice(self, payload):
        # log.debug(f"Choices: received {str(payload.emoji).encode('unicode-escape')}")
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

    # log.debug(f"opened and read file {script} ({lang})")

    ctx.cln = 0
    ctx.current_script = script+'.xls'

    skip = await ctx.bot.redis.get(f"breakpoint@{ctx.author.id}")
    if skip:
        # log.debug(f"skip key found for {ctx.author}")
        key = skip.decode()
        t_help = _help[lang].get(key)
        if t_help:
            return await ctx.send(t_help)
        snum, lnum = skip.decode().split(':')
        if scripts[int(snum)] == ctx.current_script:
            skip = int(lnum)  # we were partway in this script so lets jump to where we were
            # log.debug(f"skip key is for this script")
        else:
            skip = 0  # this is a new script with an outdated breakpoint, so lets erase it
            # log.debug(f"skip key is not for this script")
            await ctx.bot.redis.delete(f"breakpoint@{ctx.author.id}")
    else:
        skip = 0
        # log.debug(f"no script key found for {ctx.author}")

    lines = iter(data.split('\n'))

    for line in lines:
        ctx.cln += 1

        l = line.strip().format(ctx=ctx)

        if not l or l.startswith(('#', '@!')):
            continue
        # log.debug(f"new line in script: {l.startswith('$choice')} {ctx.cln >= skip} {l.replace(NL, NNL)}")
        if l.startswith('$choice') and ctx.cln >= skip:
            # log.debug("choice command found")
            cmd, question, *choices = shlex.split(l.lstrip("$"))
            outcomes = {}
            # log.debug(f"{cmd},{question},{choices}")
            while True:
                ln = next(lines)
                ch, an = shlex.split(ln)
                assert ch in choices
                outcomes[ch] = an.rstrip("$")
                if an.endswith("$"):
                    break

            s = Choices(question, *choices)
            # log.debug(f"outcomes")
            await s.start(ctx)
            r = s.result
            # log.debug(f"{r!r}")
            if not r:
                await breakpoint(ctx, stop=True)
                return True
            await ctx.send(outcomes[r])
            # log.debug("choice finished")
            continue

        if l.startswith("$") and ctx.cln >= skip:
            # log.debug("regular command found")
            cmd, *args = shlex.split(l.strip('$'))
            cmd = globals()[cmd]
            try:
                await cmd(ctx, *args)
            except StopScript:
                return True
            continue

        if ctx.cln >= skip:  # skip so we continue where we left off
            # log.debug("regular script line, sending")
            m = await ctx.send(l)
            if not await wait_next(ctx.bot, m, ctx.author):
                await breakpoint(ctx, stop=True)
                return False

    return True


# internal commands defined here

async def breakpoint(ctx, scriptnum=None, linenum=None, *, stop=False):
    scriptnum = scriptnum or scripts.index(ctx.current_script)
    linenum = linenum or ctx.cln
    await ctx.bot.redis.set(f"breakpoint@{ctx.author.id}", f'{scriptnum}:{linenum}')
    await ctx.send("*Saving progress...*", delete_after=3)
    if not stop:
        raise StopScript


TRACKS = {
    "38 - Butterfly Kiss": "https://youtu.be/Yjdo6KSqMcg"
}


def _download_track_file(name):
    link = TRACKS.get(name)
    if not link:
        raise ValueError("unknown track name {}".format(name))
    cmd = f"youtube-dl --abort-on-error --output \"music/{name}.mp3\" --extract-audio --audio-format mp3 --prefer-ffmpeg"
    proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if out:
        log.debug(f"track download stdout: {out.decode()}")
    if err:
        log.error(f"track download stderr: {err.decode()}")


def _post_track_complete(exc=None):
    if exc:
        log.error(f"exception during track play:\n{format_exc(exc)}")
        raise exc


def _bgm_loop_complete(task):
    log.debug("bgm loop complete")
    if task.exception():
        log.error(f"bgm loop error: {format_exc(task.exception())}")


async def queuebgm(ctx, track, aftertrack=None):
    """Start playing a track in voice, if possible.
    Optional aftertrack param to loop after the first finishes.
    If undefined, will loop "track"."""
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        if ctx.author.voice is not None and ctx.author.voice.channel is not None:
            await ctx.author.voice.channel.connect()
        else:
            return
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        ctx.guild.kill_track.set()

    if not os.path.isfile("music/"+track+".mp3"):
        log.debug(f"no file named music/{track}.mp3, downloading")
        loop = ctx.bot.loop
        func = functools.partial(_download_track_file, track)
        await loop.run_in_executor(None, func)
        log.debug("download finished")

    task = ctx.bot.loop.create_task(_bgm_loop(ctx, track, aftertrack))
    task.add_done_callback(_bgm_loop_complete)


async def _bgm_loop(ctx, track, aftertrack=None):
    track_wait = asyncio.Event()
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio("music/" + track + ".mp3"))
    while True:
        track_wait.clear()
        ctx.voice_client.play(source, after=lambda e: _post_track_complete(e) or track_wait.set())
        await asyncio.wait([track_wait.wait(), ctx.guild.kill_track.wait()])
        if ctx.guild.kill_track.is_set():
            ctx.guild.kill_track.clear()
            ctx.voice_client.stop()
            return

        if aftertrack:
            return await queuebgm(ctx, track=aftertrack, aftertrack=None)


async def mapset(ctx, mapname):
    """Change the players map."""
    pass
