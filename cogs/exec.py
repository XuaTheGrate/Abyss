import asyncio
import contextlib
import ctypes
import functools
import io
import multiprocessing
import textwrap

from discord.ext import commands
from jishaku.paginators import WrappedPaginator, PaginatorInterface
from .utils.formats import format_exc


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
    out = err = io.StringIO()

    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            ret = asyncio.run(func)
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
        d.append(f'-- stder --\n{err}')

    d = '\n'.join(d) + '\n-- end --'

    value.value = d
    waiter.set()


class ExecCog(commands.Cog, command_attrs={"hidden": True}):
    async def cog_check(self, ctx):
        return ctx.author.id in ctx.bot.config.OWNERS

    @commands.group()
    async def eval(self, ctx):
        pass

    @eval.command()
    async def py(self, ctx, *, code_string):
        env = {"_ctx": ctx}
        waiter = multiprocessing.Event()
        v = multiprocessing.Value('u', code_string)
        proc = multiprocessing.Process(target=functools.partial(exec_py, v, waiter, env))
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
    bot.add_cog(ExecCog())
