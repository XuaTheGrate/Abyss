import asyncio
import collections
import contextlib
import ctypes
import functools
import importlib
import io
import multiprocessing
import os
import pathlib
import sys
import textwrap
from pprint import pformat

from discord.ext import commands
from jishaku.paginators import WrappedPaginator, PaginatorInterface

from .utils.formats import format_exc


def recursive_decode(i):
    if isinstance(i, dict):
        return {recursive_decode(k): recursive_decode(v) for k, v in i.items()}
    elif isinstance(i, (list, tuple)):
        return type(i)(map(recursive_decode, i))
    elif isinstance(i, bytes):
        if i.isdigit():
            return int(i)
        return i.decode()
    return i


def exec_py(value, waiter, env=None):
    code_string = value.value
    func = f"""
async def __run_func__():
{textwrap.indent(code_string, '    ')}
    pass
"""
    g = env or {}
    try:
        exec(func, g)
    except SyntaxError as e:
        value.value = format_exc(e)
        waiter.set()
        return

    func = g['__run_func__']
    out = io.StringIO()
    err = io.StringIO()

    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            fut = asyncio.run_coroutine_threadsafe(func, loop=asyncio.get_event_loop())
            ret = fut.result()
    except Exception as e:
        value.value = format_exc(e)
        waiter.set()
        return

    d = []

    if ret:
        if not isinstance(ret, str):
            ret = repr(ret)
        d.append(f'-- result --\n{ret}')

    out = out.getvalue()
    if out:
        d.append(f'-- stdout --\n{out}')
    err = err.getvalue()
    if err:
        d.append(f'-- stderr --\n{err}')

    d = '\n'.join(d) + '\n-- end --'

    value.value = d
    waiter.set()


class Developers(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot
        self.valid = ('py', 'po', 'json', 'xls')

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.group()
    async def dev(self, ctx):
        pass

    @dev.command()
    async def reload(self, ctx, *, module):
        try:
            sys.modules[module] = importlib.reload(sys.modules[module])
            await ctx.send(ctx.bot.tick_yes)
        except Exception as e:
            await ctx.send(ctx.bot.tick_no)
            ctx.bot.send_error(f'```py\n{format_exc(e)}\n```')

    @dev.command()
    async def cleanup(self, ctx):
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            await ctx.channel.purge(check=lambda m: m.author == ctx.me or m.content.startswith("$"), before=ctx.message)
        else:
            await ctx.channel.purge(check=lambda m: m.author == ctx.me, bulk=False)

    @dev.command()
    async def redis(self, ctx, cmd, *args):
        args = [int(a) if a.isdigit() else a.format(ctx=ctx) for a in args]
        try:
            func = getattr(self.bot.redis, cmd)
            ret = await func(*args)
        except Exception as e:
            await ctx.message.add_reaction(self.bot.tick_no)
            await ctx.author.send(f"```py\n{format_exc(e)}```")
        else:
            await ctx.message.add_reaction(self.bot.tick_yes)
            if not ret:
                return
            ret = recursive_decode(ret)
            await ctx.send(f"```py\n{pformat(ret)}```")

    @dev.command()
    async def linecount(self, ctx):
        lines = collections.Counter()
        count = collections.Counter()
        for path, subdirs, files in os.walk("."):
            for name in files:
                ext = name.split(".")[-1]
                if ext not in self.valid:
                    continue
                if any(x in './' + str(pathlib.PurePath(path, name)) for x in ('venv', '.git')):
                    continue
                count[ext] += 1
                with open('./' + str(pathlib.PurePath(path, name)), 'r', encoding='unicode-escape') as f:
                    for l in f:
                        if (l.strip().startswith("#") and ext == 'py') or len(l.strip()) == 0:
                            continue
                        lines[ext] += 1
        t = lines
        fmt = "```\n" + "\n".join(
            sorted([f'{x} {y} ({count[y]} files)' for y, x in t.items()], key=lambda m: len(m))) + "```"
        await ctx.send(fmt)

    @dev.command()
    async def py(self, ctx, *, code_string):
        env = {"_ctx": ctx}
        manager = multiprocessing.Manager()
        waiter = manager.Event()
        v = manager.Value(ctypes.c_char_p, code_string)
        proc = multiprocessing.Process(target=exec_py, args=(v, waiter, env))
        proc.start()
        get = await ctx.bot.loop.run_in_executor(None, functools.partial(waiter.wait, timeout=5))
        if not get:
            proc.kill()
            return await ctx.send("Execution took too long.")
        data = v.value
        pg = WrappedPaginator(max_size=1985)
        for line in data.split('\n'):
            pg.add_line(line)
        inf = PaginatorInterface(ctx.bot, pg, owner=ctx.author)
        await inf.send_to(ctx)


def setup(bot):
    bot.add_cog(Developers(bot))
