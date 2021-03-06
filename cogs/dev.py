import asyncio
import collections
import copy
import importlib
import inspect
import os
import pathlib
import random
import re
import textwrap
import time
from pprint import pformat
from typing import Union

import discord
import import_expression
import psutil
from discord.ext import commands

from cogs.utils.battle import TreasureDemonBattle, TreasureDemon
from cogs.utils.formats import format_exc, ensure_player
from cogs.utils.paginators import PaginationHandler, BetterPaginator, Timer
from cogs.utils.subprocess import Subprocess


def recursive_decode(i):
    if isinstance(i, dict):
        return {recursive_decode(k): recursive_decode(v) for k, v in i.items()}
    if isinstance(i, (list, tuple)):
        return type(i)(map(recursive_decode, i))
    if isinstance(i, bytes):
        if i.isdigit():
            return int(i)
        return i.decode()
    return i


# pylint: disable=invalid-name
class FakeUser:
    __slots__ = ('id', 'name', 'display_name')

    def __init__(self):
        self.id = 0
        self.name = ""
        self.display_name = ""

    async def send(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(.093)
        return FakeMessage


class FakeGuild:
    __slots__ = ('id', 'name', 'members')

    def __init__(self):
        self.id = 0
        self.name = ''
        self.members = []


class FakeChannel:
    __slots__ = ('id', 'name', 'category', 'members', 'guild', 'mention')

    def __init__(self):
        self.id = 0
        self.name = ""
        self.category = None
        self.members = []
        self.guild = FakeGuild
        self.mention = ""

    async def send(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(0.093)
        return FakeMessage

    async def delete(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(0.093)


class FakeMessage:
    __slots__ = ('content', 'id', 'author', 'channel', 'guild')

    def __init__(self):
        self.content = ""
        self.id = 0
        self.author = FakeUser
        self.channel = FakeChannel
        self.guild = FakeGuild

    async def add_reaction(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(0.093)
# pylint: enable=invalid-name


# pylint: disable=invalid-overridden-method
class PerformanceContext(commands.Context):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message = FakeMessage

    @property
    def guild(self):
        return FakeGuild

    @property
    def author(self):
        return FakeUser

    @property
    def channel(self):
        return FakeChannel

    async def send(self, *args, **kwargs):  # pylint: disable=arguments-differ,unused-argument
        await asyncio.sleep(0.093)
        return FakeMessage

    async def send_as_paginator(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(0.093)

    async def confirm(self, *args, **kwargs):  # pylint: disable=unused-argument
        await asyncio.sleep(0.093)
        return True
# pylint: enable=invalid-overridden-method


class Developers(commands.Cog, command_attrs={"hidden": True}):
    process = psutil.Process()

    def __init__(self, bot):
        self.bot = bot
        self.valid = ('py', 'po', 'json', 'xls', 'md', 'txt')
        self._latest_proc = None
        self._env = {}
        self._send_in_codeblocks = False
        self._show_stderr = False
        self._perf_loops = 10
        self._evals = []
        self._timeout = 60

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id not in self.bot.config.OWNERS:
            return
        if str(payload.emoji) == '\U0001f504':
            message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                await ctx.reinvoke()

    @commands.group()
    async def dev(self, ctx):
        pass

    @dev.command()
    async def reload(self, ctx, *modules):
        done = {}
        for mod in modules:
            if mod in self.bot.extensions:
                try:
                    self.bot.reload_extension(mod)
                    done[mod] = True
                except commands.NoEntryPointError:
                    done[mod] = False
                except Exception as exc:
                    done[mod] = format_exc(getattr(exc, '__cause__', exc) or exc)
            else:
                try:
                    self.bot.load_extension(mod)
                    done[mod] = True
                except commands.NoEntryPointError:
                    done[mod] = False
                except Exception as exc:
                    done[mod] = format_exc(getattr(exc, '__cause__', exc) or exc)
        if all(z is True for z in done.values()):
            return await ctx.message.add_reaction(self.bot.tick_yes)
        fmt = []
        for module, success in done.items():
            if success is True:
                fmt.append(f"{self.bot.tick_yes} {module}\n")
            elif success is False:
                fmt.append(f'\U0001f504 {module}\n')
            else:
                fmt.append(f"{self.bot.tick_no} {module}\n```py\n{success}\n```\n")
        await ctx.send_as_paginator('\n'.join(fmt))

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
        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            await ctx.send_as_paginator(format_exc(exc), codeblock=True)
        else:
            await ctx.message.add_reaction(self.bot.tick_yes)
            if not ret:
                return
            ret = recursive_decode(ret)
            await ctx.send_as_paginator(pformat(ret), codeblock=True)

    @dev.command()
    async def linecount(self, ctx):
        lines = collections.Counter()
        count = collections.Counter()
        for path, _, files in os.walk("."):
            for name in files:
                ext = name.split(".")[-1]
                if ext not in self.valid:
                    continue
                if any(x in './' + str(pathlib.PurePath(path, name)) for x in ('venv', '.git')):
                    continue
                count[ext] += 1
                with open('./' + str(pathlib.PurePath(path, name)), 'r', encoding='utf-8') as file:
                    for line in file:
                        if (line.strip().startswith("#") and ext == 'py') or len(line.strip()) == 0:
                            continue
                        lines[ext] += 1
        fmt = "```\n" + "\n".join(
            sorted([f'{x:,} {y} ({count[y]:,} files)' for y, x in lines.items()], key=len)) + "```"
        await ctx.send_as_paginator(fmt)

    @dev.command()
    async def eval(self, ctx, *, code_string):
        if not self._env:
            self._env.update({"discord": discord,
                              "commands": commands, '_': None,
                              import_expression.constants.IMPORTER: importlib.import_module})
        self._env['ctx'] = ctx
        try:
            expr = import_expression.compile(code_string)
            ret = eval(expr, self._env)
        except SyntaxError:
            pass
        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.send_as_paginator(format_exc(exc), codeblock=True)
        else:
            if inspect.isawaitable(ret):
                fut = asyncio.ensure_future(ret, loop=self.bot.loop)
                self._evals.append(fut)
                try:
                    with Timer(ctx.message):
                        ret = await asyncio.wait_for(fut, timeout=self._timeout)
                except Exception as exc:
                    await ctx.message.add_reaction(self.bot.tick_no)
                    return await ctx.send_as_paginator(format_exc(exc), codeblock=True)
                finally:
                    self._evals.remove(fut)
            await ctx.message.add_reaction(self.bot.tick_yes)
            if ret is None:
                return
            self._env['_'] = ret
            if isinstance(ret, discord.Embed):
                return await ctx.send(embed=ret)
            if not isinstance(ret, str):
                ret = repr(ret)
            return await ctx.send_as_paginator(ret, codeblock=self._send_in_codeblocks)
        code = f"""async def __func__():
    try:
{textwrap.indent(code_string, '        ')}
    finally:
        globals().update(locals())"""
        try:
            import_expression.exec(code, self._env)
        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.send_as_paginator(format_exc(exc), codeblock=True)

        func = self._env.pop('__func__')
        fut = asyncio.ensure_future(func(), loop=self.bot.loop)
        self._evals.append(fut)
        try:
            with Timer(ctx.message):
                await asyncio.wait_for(fut, timeout=self._timeout)
        except asyncio.CancelledError:
            await ctx.message.add_reaction('\U0001f6d1')
            return
        except asyncio.TimeoutError:
            await ctx.message.add_reaction('\u23f0')
            return
        except Exception as exc:
            await ctx.message.add_reaction(self.bot.tick_no)
            return await ctx.send_as_paginator(format_exc(exc), codeblock=True)
        else:
            ret = fut.result()
        finally:
            self._evals.remove(fut)

        await ctx.message.add_reaction(self.bot.tick_yes)

        if ret is None:
            return

        self._env['_'] = ret

        if isinstance(ret, discord.Embed):
            return await ctx.send(embed=ret)

        if not isinstance(ret, str):
            ret = repr(ret)

        return await ctx.send_as_paginator(ret, codeblock=self._send_in_codeblocks)

    @dev.command()
    async def stop(self, ctx):
        if self._latest_proc:
            self._latest_proc.process.kill()
            await ctx.message.add_reaction(self.bot.tick_yes)

    @dev.command()
    async def cancel(self, ctx, idx=-1):
        try:
            self._evals[idx].cancel()
        except IndexError:
            await ctx.message.add_reaction(self.bot.tick_no)
        else:
            await ctx.message.add_reaction(self.bot.tick_yes)

    @dev.command()
    async def shutdown(self, ctx):
        await ctx.send(":wave:")
        await self.bot.logout()

    @dev.command()
    async def reset(self, ctx):
        self._latest_proc = proc = await Subprocess.init("git", "pull", loop=self.bot.loop)
        with Timer(ctx.message):
            await proc.stream(lambda c: None)
        await ctx.message.add_reaction(self.bot.tick_yes)
        await self.bot.logout()

    @dev.command(name='try')
    async def try_(self, ctx, *, command):
        nmsg = copy.copy(ctx.message)
        nmsg.content = ctx.prefix+command
        nctx = await self.bot.get_context(nmsg)
        try:
            await self.bot.invoke(nctx)
        except Exception as exc:
            await ctx.send_as_paginator(format_exc(exc), codeblock=True)

    @dev.command(name='as')
    async def as_(self, ctx, user: Union[discord.Member, discord.User], *, command):
        nmsg = copy.copy(ctx.message)
        nmsg.author = user
        nmsg.content = ctx.prefix+command
        nctx = await self.bot.get_context(nmsg)
        await self.bot.invoke(nctx)

    @dev.command(name='in')
    async def in_(self, ctx, channel: discord.TextChannel, *, command):
        nmsg = copy.copy(ctx.message)
        nmsg.channel = channel
        nmsg.content = ctx.prefix+command
        nctx = await self.bot.get_context(nmsg)
        await self.bot.invoke(nctx)

    @dev.command(name='at')
    async def at_(self, ctx, guild_id: int, *, command):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return await ctx.send('no guild found')
        nmsg = copy.copy(ctx.message)
        nmsg.guild = guild
        nmsg.content = ctx.prefix+command
        nctx = await self.bot.get_context(nmsg)
        await self.bot.invoke(nctx)

    @dev.command()
    async def timeit(self, ctx, *, command):
        nmsg = copy.copy(ctx.message)
        nmsg.content = ctx.prefix + command
        nctx = await self.bot.get_context(nmsg, cls=PerformanceContext)
        if nctx.command is None:
            return await ctx.send("No command found.")
        times = []
        fail = False
        for _ in range(self._perf_loops):
            # nctx.command = copy.copy(nctx.command)
            # nctx.command.can_run = _replace_checks
            start = time.perf_counter()
            try:
                await nctx.reinvoke()
            except Exception as exc:
                if not fail:
                    fail = True
                    await ctx.author.send(f'```py\n{format_exc(exc)}\n```')
            finally:
                end = time.perf_counter() - start
                times.append(round(end*1000, 2))
        await ctx.send(f'{self._perf_loops} loops, {min(times)}ms min,'
                       f' {max(times)}ms max, {sum(times)/len(times):.2f}ms avg, success={not fail}')

    @dev.command(enabled=False)
    async def lua(self, ctx, *, code_string):
        with open("_exec.lua", "w") as file:
            file.write(code_string)
        paginator = BetterPaginator('```lua\n', '\n```', 1985)
        # log.debug("init")
        # log.debug("handler started")
        self._latest_proc = proc = await Subprocess.init('lua5.3', '_exec.lua',
                                                         loop=self.bot.loop, filter_error=self._show_stderr)
        # log.debug("process initialized")
        with Timer(ctx.message):
            await proc.stream(paginator.add_line)
            # log.debug("_update called")
        await asyncio.sleep(.1)
        code = proc.process.returncode
        paginator.add_line(f"\nExit code: {code}")
        hdlr = PaginationHandler(self.bot, paginator, no_help=True)
        await hdlr.start(ctx)
        # log.debug("eof")

    @dev.command(aliases=['sh'])
    async def bash(self, ctx, *, code_string):
        if os.sys.platform == 'win32':
            return await ctx.send("unsupported")

        cmd = ['/bin/bash', '-c', code_string]

        paginator = BetterPaginator('```sh\n', '\n```')

        async def hdlr():
            with Timer(ctx.message):
                await proc.stream(paginator.add_line)

        self._latest_proc = proc = await Subprocess.init(*cmd, loop=self.bot.loop, filter_error=self._show_stderr)

        try:
            await asyncio.wait_for(hdlr(), timeout=self._timeout)
        except asyncio.TimeoutError:
            await ctx.message.add_reaction("\u23f0")
        else:
            await ctx.message.add_reaction(self.bot.tick_yes)

        await asyncio.sleep(.1)
        code = proc.process.returncode
        paginator.add_line(f'\nExit code: {code}')
        hdlr = PaginationHandler(self.bot, paginator, no_help=True)
        await hdlr.start(ctx)  # todo: fix reactions

    @dev.command()
    async def src(self, ctx, *, command):
        cmd = self.bot.get_command(command)
        if not cmd:
            try:
                obj = import_expression.eval(command, {})
            except Exception as exc:
                await ctx.message.add_reaction(self.bot.tick_no)
                return await ctx.send_as_paginator(format_exc(exc), codeblock=True, destination=ctx.author)
        else:
            obj = cmd.callback

        lines, firstlno = inspect.getsourcelines(obj)
        paginator = BetterPaginator('```py\n', '```')
        for lno, line in enumerate(lines, start=firstlno):
            paginator.add_line(f'{lno}\t{line.rstrip()}'.replace('``', '`\u200b`'))
        await PaginationHandler(self.bot, paginator, no_help=True).start(ctx)

    @dev.command()
    async def giveitem(self, ctx, user: Union[discord.Member, discord.User], item, count=1):
        if user.id not in self.bot.players.players:
            return await ctx.send("User has no (cached) player.")
        player = self.bot.players.players[user.id]
        item = self.bot.item_cache.get_item(item)
        if not item:
            return await ctx.send("No item found.")
        for _ in range(count):
            player.inventory.add_item(item)
        await ctx.send(self.bot.tick_yes)

    @dev.command()
    async def removeitem(self, ctx, user: Union[discord.Member, discord.User], item, count=1):
        if user.id not in self.bot.players.players:
            return await ctx.send('User has no (cached) player.')
        player = self.bot.players.players[user.id]
        item = self.bot.item_cache.get_item(item)
        if not item:
            return await ctx.send('No item found.')
        for _ in range(count):
            player.inventory.remove_item(item)
        await ctx.send(self.bot.tick_yes)

    @dev.command()
    async def update(self, ctx):
        """
From https://github.com/XuaTheGrate/Abyss
   0387c15..7869764  master     -> origin/master
Updating 0387c15..7869764
Fast-forward
 cogs/dev.py | 6 +++++-
 1 file changed, 5 insertions(+), 1 deletion(-)
        """
        data = []
        self._latest_proc = proc = await Subprocess.init('git', 'pull', loop=self.bot.loop)
        await proc.stream(data.append)
        output = '\n'.join(data)
        if output.strip() == 'Already up to date.':
            return await ctx.send("Nothing to update.")
        ver = re.findall(r'([a-fA-F0-9]{7})\.\.([a-fA-F0-9]{7})', output)
        pre, pos = ver[0]
        await ctx.send(f'Update `{pre}` -> `{pos}`')
        # mods = re.findall(r'\s(cogs/[a-z_]+\.py) \|', m)
        # if not await ctx.confirm(f'Update `{pre}` -> `{pos}`\nReload modules?'):
        #     return
        # await ctx.invoke(self.reload, *[m.replace('/', '.')[:-3] for m in mods])

    @dev.command()
    async def status(self, ctx):
        pass

    @dev.command()
    @ensure_player
    async def force_treasure_demon_battle(self, ctx):
        mp_cog = self.bot.get_cog('Maps')
        demons = list(filter(lambda d: d['level'] >= ctx.player.level, mp_cog.treasure_demon_data))
        if demons:
            min_demon = min(demons, key=lambda f: f['level'])
            filt = list(filter(lambda d: d['level'] <= min_demon['level'], mp_cog.treasure_demon_data))
            tdemon = random.choice(filt)
        else:
            tdemon = max(mp_cog.treasure_demon_data, key=lambda f: f['level'])  # return highest
        enemy = await TreasureDemon(**tdemon).populate_skills(self.bot)
        bt_cog = self.bot.get_cog("BattleSystem")
        bt_cog.battles[ctx.author.id] = TreasureDemonBattle(ctx.player, ctx, enemy)

    @dev.group()
    async def config(self, ctx):
        pass

    @config.command()
    async def codeblocks(self, ctx, toggle: bool):
        self._send_in_codeblocks = toggle
        await ctx.message.add_reaction(self.bot.tick_yes if toggle else self.bot.tick_no)

    @config.command()
    async def clearenv(self, ctx):
        self._env.clear()
        await ctx.message.add_reaction(self.bot.tick_yes)

    @config.command()
    async def showstderr(self, ctx, toggle: bool):
        self._show_stderr = toggle
        await ctx.message.add_reaction(self.bot.tick_yes if toggle else self.bot.tick_no)

    @config.command()
    async def perfloops(self, ctx, amount: int):
        self._perf_loops = amount
        await ctx.message.add_reaction(self.bot.tick_yes)

    @config.command()
    async def timeout(self, ctx, amount: int):
        self._timeout = amount
        await ctx.message.add_reaction(self.bot.tick_yes)


def setup(bot):
    bot.add_cog(Developers(bot))
