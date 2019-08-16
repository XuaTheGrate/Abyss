from typing import Optional

import discord
from discord.ext import commands


GROUPS = ['misc', 'battle', 'music', 'maps']


def valid(k):
    if k not in GROUPS:
        raise IndexError
    return k


class TodoList(commands.Cog, command_attrs={"hidden": True}):
    def __init__(self, bot):
        self.bot = bot

    """
    {
        "group": "battle",
        "name": "todo name",
        "done": true
    }
    """

    async def cog_check(self, ctx):
        return ctx.author.id in self.bot.config.OWNERS

    @commands.group()
    async def todo(self, ctx):
        d = discord.Embed(title="Todo list")
        groups = {k: [] for k in GROUPS}
        async for doc in self.bot.db.abyss.todo.find({}):
            groups[doc['group']].append(f'{self.bot.tick_yes if doc["done"] else self.bot.tick_no}')
        for g, t in groups.items():
            d.add_field(name=g, value="\n".join(t), inline=False)
        await ctx.send(embed=d)

    @todo.command()
    async def add(self, ctx, group: Optional[valid] = "misc", *, name):
        await self.bot.db.abyss.todo.insert_one({"name": name, "group": group, "done": False})
        await ctx.message.add_reaction(self.bot.tick_yes)

    @todo.command()
    async def remove(self, ctx, *, name):
        await self.bot.db.abyss.todo.delete_one({"name": name})
        await ctx.message.add_reaction(self.bot.tick_yes)

    @todo.command()
    async def check(self, ctx, tick: bool, *, name):
        await self.bot.db.abyss.todo.update_one({"name": name}, {"$set": {"done": tick}})
        await ctx.message.add_reaction(self.bot.tick_yes)


def setup(bot):
    bot.add_cog(TodoList(bot))
