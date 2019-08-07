import collections
import importlib
import os
import pathlib
import sys
from pprint import pformat

from discord.ext import commands

from .utils.formats import format_exc


class Developers(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot
        self.valid = ('py', 'po', 'json', 'scr')

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
        func = getattr(self.bot.redis, cmd)
        args = [int(a) if a.isdigit() else a for a in args]
        try:
            ret = await func(*args)
        except Exception as e:
            await ctx.message.add_reaction(self.bot.tick_no)
            await ctx.author.send(f"```py\n{format_exc(e)}```")
        else:
            await ctx.message.add_reaction(self.bot.tick_yes)
            if not ret:
                return
            if isinstance(ret, dict):
                ret = {int(k) if k.isdigit() else k.decode(): int(v) if v.isdigit() else v.decode()
                       for k, v in ret.items()}
            elif isinstance(ret, list):
                ret = [int(k) if k.isdigit() else k.decode() for k in ret]
            elif isinstance(ret, bytes):
                ret = int(ret) if ret.isdigit() else ret.decode()
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


def setup(bot):
    bot.add_cog(Developers(bot))
