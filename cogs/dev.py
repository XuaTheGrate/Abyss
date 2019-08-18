import collections
import os
import pathlib
from pprint import pformat

from discord.ext import commands

from .utils.formats import format_exc
from .utils.paginators import PaginationHandler


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


class Developers(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot
        self.valid = ('py', 'po', 'json', 'xls')
        self.timeout = 5

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

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
                except Exception as e:
                    done[mod] = format_exc(getattr(e, '__cause__', e))
            else:
                try:
                    self.bot.load_extension(mod)
                    done[mod] = True
                except commands.NoEntryPointError:
                    done[mod] = False
                except Exception as e:
                    done[mod] = format_exc(getattr(e, '__cause__', e))
        if all(z is True for z in done.values()):
            return await ctx.message.add_reaction(self.bot.tick_yes)
        fmt = []
        for k, v in done.items():
            if v is True:
                fmt.append(f"{self.bot.tick_yes} {k}\n")
            elif v is False:
                fmt.append(f'\U0001f504 {k}\n')
            else:
                fmt.append(f"{self.bot.tick_no} {k}\n```py\n{v}\n```\n")
        data = '\n'.join(fmt).split('\n')
        pg = commands.Paginator(prefix="", suffix="", max_size=1985)
        for l in data:
            pg.add_line(l)
        hdlr = PaginationHandler(self.bot, pg)
        await hdlr.start(ctx)

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
        pass


def setup(bot):
    bot.add_cog(Developers(bot))
