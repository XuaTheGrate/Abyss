import asyncio
import json
import random

import discord

from cogs.utils.battle import TreasureDemon, TreasureDemonBattle
from cogs.utils.formats import *
from cogs.utils.paginators import EmbedPaginator, PaginationHandler


def ensure_searched(func):
    async def check(ctx):
        c = await ctx.bot.redis.get(f'{ctx.author.id}:searchedmap-{ctx.player.map.name}:{ctx.player.area}')
        if not c or int(c) == 0:
            raise NotSearched()
        return True

    return commands.check(check)(func)


class Maps(commands.Cog, name="Exploration"):
    def __init__(self, bot):
        self.bot = bot
        self.debug = []

        with open("treasure-demons.json") as f:
            self.treasure_demon_data = json.load(f)

    # note to self: when travelling to another dungeon, will cost 15 sp
    # 15 because that is the lowest possible amount of sp when full healed

    def get_item_pool(self, map_name):
        cache = self.bot.item_cache
        pool = []
        for item in cache.items.values():
            # dont give items weight if you dont want them in treasures
            if item.weight and map_name in item.dungeons:
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
            raise SilentError("You can't use this command while you are in a battle!")  # cant use these commands during battle
        if ctx.command is self.whereami:
            return  # we dont want to interrupt the search if we are just checking our location
        if ctx.author.id not in self.debug and random.randint(1, 5) == 1:  # debug is the tutorial usually
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
    @ensure_searched
    @ensure_player
    async def move(self, ctx):
        """Moves to another location.
        You can find what locations are available after `search`ing."""
        pg = EmbedPaginator()
        valid = [x['name'].lower() for x in ctx.player.map.areas[ctx.player.area]['interactions'] if x['type'] == 0]
        it = []
        for k, v in enumerate(
                [i['name'] for i in ctx.player.map.areas[ctx.player.area]['interactions'] if i['type'] == 0], start=1):
            it.append(f'{k}. {v}')
        tot = '\n'.join(it)
        if len(tot) > 2048:
            for chunk in [it[x:x + 20] for x in range(0, len(tot), 20)]:
                embed = discord.Embed(description='\n'.join(chunk))
                pg.add_page(embed)
        else:
            embed = discord.Embed(description=tot)
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

    @commands.command()
    @ensure_searched
    @ensure_player
    async def interact(self, ctx):
        """Interacts with an object in this area.
        You can find what objects are available after `search`ing."""
        pg = EmbedPaginator()
        valid = [x['id'] for x in ctx.player.map.areas[ctx.player.area]['interactions'] if x['type'] == 1]
        chest_ids = await self.bot.redis.hgetall(f'open_chests:{ctx.author.id}')
        for cid in chest_ids.keys():
            if (i := int(cid)) in valid:
                valid.remove(i)
        it = []
        for v in (i['name'] for i in ctx.player.map.areas[ctx.player.area]['interactions']
                  if i['type'] == 1 and i['id'] in valid):
            it.append(f'{v["id"]}. {v}')
        tot = '\n'.join(it)
        if len(tot) > 2048:
            for chunk in [it[x:x+20] for x in range(0, len(tot), 20)]:
                embed = discord.Embed(description='\n'.join(chunk))
                embed.set_footer(text="Type the Number to open")
                pg.add_page(embed)
        else:
            embed = discord.Embed(description=tot)
            embed.set_footer(text="Type the Number to open")
            pg.add_page(embed)
        hdlr = PaginationHandler(self.bot, pg, send_as='embed')
        await hdlr.start(ctx)

        def filter_interaction(message):
            return message.author == ctx.author and \
                   message.channel.id == ctx.channel.id and \
                   message.content.isdigit() and \
                   int(message.content) in valid

        goto = None
        while hdlr.running:
            try:
                id = await self.bot.wait_for('message', check=filter_interaction, timeout=60)
            except asyncio.TimeoutError:
                await hdlr.stop()
                break
            id = int(id.content)
            for k in ctx.player.map.areas[ctx.player.area]['interactions']:
                if k['type'] == 1 and k['id'] == id:
                    goto = k
                    break
            if goto:
                break
        if not goto:
            return
        await hdlr.stop()

        chest_id = goto['id']
        if await self.bot.redis.hget(f'open_chests:{ctx.author.id}', str(chest_id)):
            return await ctx.send('You\'ve already opened this chest!')

        if goto['locked']:
            if not ctx.player.inventory.has_item('Lockpick'):
                return await ctx.send("This chest is locked, and requires 1 **Lockpick** to unlock.")
            if not await ctx.confirm("This chest is locked. Use **Lockpick**?"):
                return
            ctx.player.inventory.remove_item('Lockpick')
        await self.bot.redis.hset(f'open_chests:{ctx.author.id}', str(chest_id), '1')
        item = ctx.bot.item_cache.get_item(goto['command'])
        await ctx.send(f"You opened the chest and obtained **{item.name}**!")
        ctx.player.inventory.add_item(item)

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
            maxn, pool = self.get_item_pool(ctx.player.map.name)
            p = random.randint(1, maxn)
            for i, rng in pool.items():
                if p in rng:
                    await ctx.send(f"Obtained **{i.name}**!")
                    ctx.player.inventory.add_item(i)
                    return
        elif k == 2:  # treasure demon
            demons = list(filter(lambda d: d['level'] >= ctx.player.level, self.treasure_demon_data))
            if demons:
                # `lambda d: d['level'] <= ctx.player.level`
                # this wont work as the player might not be a higher
                # level than the lowest treasure demon on my list
                # so to counter that, i select the closest one possible
                # then get every single demon that is that level
                # or lower level to it, then select a random one
                min_demon = min(demons, key=lambda f: f['level'])
                filt = list(filter(lambda d: d['level'] <= min_demon['level'], self.treasure_demon_data))
                tdemon = random.choice(filt)
            else:
                # if `demons` is empty, that means no demons are
                # a higher level to the player, so we just select
                # the highest level one instead
                tdemon = max(self.treasure_demon_data, key=lambda f: f['level'])  # return highest
            enemy = await TreasureDemon(**tdemon).populate_skills(self.bot)
            bt_cog = self.bot.get_cog("Battle")
            bt_cog.battles[ctx.author.id] = TreasureDemonBattle(ctx.player, ctx, enemy)


def setup(bot):
    bot.add_cog(Maps(bot))
