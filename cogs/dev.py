import collections
import importlib
import os
import pathlib
import sys

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
    @commands.is_owner()
    async def linecount(self, ctx):
        total = collections.Counter()
        for path, subdirs, files in os.walk("."):
            for name in files:
                ext = name.split(".")[-1]
                if ext not in self.valid:
                    continue
                if any(x in './' + str(pathlib.PurePath(path, name)) for x in ('venv',)):
                    continue
                with open('./' + str(pathlib.PurePath(path, name)), 'r', encoding='unicode-escape') as f:
                    for l in f:
                        if (l.strip().startswith("#") and ext == 'py') or len(l.strip()) == 0:
                            continue
                        total[ext] += 1
        t = {a: b for a, b in sorted(total.items(), key=lambda x: x[1], reverse=True)}
        sizea = max(len(str(x)) for x in t.values())
        fmt = "```\n" + "\n".join(sorted([f'{x:>{sizea}} {y}' for y, x in t.items()],
                                         key=lambda m: len(m))) + "```"
        await ctx.send(fmt)


def setup(bot):
    bot.add_cog(Developers(bot))
