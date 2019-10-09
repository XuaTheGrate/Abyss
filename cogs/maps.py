import asyncio
import random

import discord

from cogs.utils.enums import ItemType
from cogs.utils.formats import *
from cogs.utils.items import Unusable
from cogs.utils.paginators import EmbedPaginator, PaginationHandler


def ensure_searched(func):
    async def check(ctx):
        c = await ctx.bot.redis.get(f'{ctx.author.id}:searchedmap-{ctx.player.map.name}:{ctx.player.area}')
        if not c or int(c) == 0:
            raise NotSearched()
        return True

    return commands.check(check)(func)


class Maps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # note to self: when travelling to another dungeon, will cost 15 sp
    # 15 because that is the lowest possible amount of sp when full healed

    def get_item_pool(self):
        cache = self.bot.item_cache
        pool = []
        for item in cache.items.values():
            if item.type is ItemType.TRASH or item.type is ItemType.HEALING:
                pool.append(item)
        maxn = sum(i.weight for i in pool)
        assert maxn > 0
        idx = 1
        npool = {}
        for i in pool:
            npool[i] = range(idx, idx + i.weight)
            idx += i.weight
        return maxn, npool

    async def cog_before_invoke(self, ctx):
        if ctx.author.id in self.bot.get_cog("BattleSystem").battles:
            raise SilentError  # cant use these commands during battle
        if ctx.command is self.inventory:
            return  # we dont want to interrupt the search if we are just opening our inventory
        if random.randint(1, 5) == 1:
            await ctx.invoke(self.bot.get_command("encounter"), force=True)
            raise SilentError

    @commands.command()
    @ensure_player
    async def whereami(self, ctx):
        """Tells you where you are currently located."""
        await ctx.send(f'You are currently on map "{ctx.player.map.name}", area "{ctx.player.area}".')

    @commands.command()
    @ensure_player
    async def search(self, ctx):
        """Looks around to see what you can interact with.
        Has a chance of spawning an enemy, interrupting the search."""
        await self.bot.redis.set(f'{ctx.author.id}:searchedmap-{ctx.player.map.name}:{ctx.player.area}', 1)
        tcount = ctx.player.map.areas[ctx.player.area]['treasurecount']
        locs = sum(1 for i in ctx.player.map.areas[ctx.player.area]['interactions'] if i['type'] == 0)
        chests = sum(1 for i in ctx.player.map.areas[ctx.player.area]['interactions'] if i['type'] == 1)
        await ctx.send(f'You looked around {ctx.player.map.name}#{ctx.player.area} and found {tcount} treasures, '
                       f'{locs} doors and {chests} chests.')

    @commands.command()
    @ensure_player
    async def inventory(self, ctx):
        """Opens your inventory and shows your items.
        You can select some items and use them if you wish,
        though some items may only be used in battle."""
        await ctx.player.inventory.view(ctx)
        c1 = self.bot.loop.create_task(
            self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and ctx.player.inventory.has_item(
                    m.content.lower()),
                timeout=60))
        c2 = self.bot.loop.create_task(ctx.player.inventory.pg.wait_stop())
        await asyncio.wait([c1, c2], return_when=asyncio.FIRST_COMPLETED)
        await ctx.player.inventory.pg.stop()
        if c2.done():
            c1.cancel()
            return
        try:
            m = c1.result()
        except asyncio.TimeoutError:
            return

        item = ctx.player.inventory.get_item(m.content.lower())
        try:
            await item.use(ctx)
        except Unusable as e:
            await ctx.send(str(e))
            return
        if not ctx.player.inventory.remove_item(item):
            self.bot.log.warning(f"apparently {ctx.player} has {item}, but we couldnt remove it for some reason")

    @commands.command()
    @ensure_searched
    @ensure_player
    async def move(self, ctx):
        """Moves to another location.
        You can find what locations are available after `search`ing."""
        pg = EmbedPaginator()
        valid = [x['name'].lower() for x in ctx.player.map.areas[ctx.player.area]['interactions']]
        it = []
        for k, v in enumerate(
                [i['name'] for i in ctx.player.map.areas[ctx.player.area]['interactions'] if i['type'] == 0], start=1):
            it.append(f'{k}. {v}')
        tot = '\n'.join(it)
        if len(tot) > 2048:
            for chunk in [it[x:x + 20] for x in range(0, len(tot), 20)]:
                embed = discord.Embed(description='\n'.join(chunk), colour=discord.Colour.dark_grey())
                pg.add_page(embed)
        else:
            embed = discord.Embed(description=tot, colour=discord.Colour.dark_grey())
            pg.add_page(embed)
        hdlr = PaginationHandler(self.bot, pg, send_as='embed')
        await hdlr.start(ctx)

        def filter_location(message):
            return message.author == ctx.author and \
                   message.channel.id == ctx.channel.id and \
                   message.content.lower() in valid

        goto = None
        while hdlr.running:
            try:
                msg = await self.bot.wait_for('message', check=filter_location, timeout=60)
            except asyncio.TimeoutError:
                await hdlr.stop()
                break
            for k in ctx.player.map.areas[ctx.player.area]['interactions']:
                if k['type'] == 0 and k['name'].lower() == msg.content:
                    if await ctx.confirm(f"Travel to {k['command']}?"):
                        goto = k['command']
                    break
            if goto:
                break
        if not goto:
            return
        await hdlr.stop()
        ctx.player.area = goto
        await ctx.send(f"Travelled to {goto}! Remember to use `$search` to look around the area.")

    @commands.command(enabled=False)
    @ensure_searched
    @ensure_player
    async def interact(self, ctx):
        """Interacts with an object in this area.
        You can find what objects are available after `search`ing."""

    @commands.command(aliases=['open-treasure', 'opentreasure'])
    @ensure_searched
    @ensure_player
    async def open_treasure(self, ctx):
        """Opens a treasure in this room, if there are any remaining.
        Treasures reset daily at midnight UTC."""
        k = await ctx.player.map.open_treasure(ctx.player)
        if k == -1:  # no treasures available
            return await ctx.send("There are no treasures in this area right now, try again after midnight! (utc)")
        elif k == 0:  # didnt find anything
            return await ctx.send("There was nothing in the treasure.")
        elif k == 1:  # give random item
            # the only pools we can grab from rn are `Trash` and `Healing` pools, remind me to add support for
            # the `Materials` pool when i make it
            maxn, pool = self.get_item_pool()
            p = random.randint(1, maxn)
            for i, rng in pool.items():
                if p in rng:
                    await ctx.send(f"Obtained **{i.name}**!")
                    ctx.player.inventory.add_item(i)
                    return
        elif k == 2:  # treasure demon
            await ctx.send("todo")


def setup(bot):
    bot.add_cog(Maps(bot))
