import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from .utils.items import Unusable, Craftable, HealingItem
from .utils.formats import ensure_player
from .utils.paginators import EmbedPaginator, PaginationHandler
from .utils.player import Player


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task = None
        self.relaunch_task()

    def convert_ts_to_seconds(self, ts):
        return (ts - datetime.utcnow()).total_seconds()

    async def craft_waiter(self):
        await self.bot.prepared.wait()
        self.bot.log.info('craft task initialized')
        while True:
            task = await self.bot.db.abyss.crafttasks.find({}).sort('after').to_list(1)
            if not task:
                break
            task = task[0]
            ts = task['after']
            await asyncio.sleep(self.convert_ts_to_seconds(ts))
            self.bot.dispatch('craft_complete', task)
            await self.bot.db.abyss.crafttasks.delete_one(task)
        self.bot.log.info('all craft tasks completed')

    def cog_unload(self):
        try:
            self._task.cancel()
        except:
            pass

    def relaunch_task(self):
        try:
            self._task.cancel()
        except:
            pass
        self._task = self.bot.loop.create_task(self.craft_waiter())

    async def new_craft_task(self, ctx, item):
        nd = datetime.utcnow()
        nd += timedelta(minutes=item.time)
        pd = {
            'user': ctx.author.id,
            'item': item.name,
            'count': item.makes,
            'after': nd,  # datetime when complete
            'channel': ctx.channel.id,  # for notifications
            'msg': ctx.message.jump_url
        }
        await self.bot.db.abyss.crafttasks.insert_one(pd)
        self.relaunch_task()
        return pd

    @commands.Cog.listener()
    async def on_craft_complete(self, crafting_data):
        user = self.bot.get_user(crafting_data['user'])
        channel = self.bot.get_channel(crafting_data['channel'])
        if not user:
            return
        msg = f'''{user.mention}, your crafting job has been completed!
Obtained **{crafting_data['count']} {crafting_data['item']}**!

<{crafting_data['msg']}>
'''
        item = self.bot.item_cache.get_item(crafting_data['item'])
        # todo: when clustering, send an op to recache the player if it exists
        if user.id not in self.bot.players.players:
            pdata = await self.bot.db.abyss.accounts.find_one({"owner": user.id})
            if not pdata:
                return  # the player was deleted i guess?
            player = await Player(**pdata)._populate_skills(self.bot)
            for i in range(crafting_data['count']):
                player.inventory.add_item(item)
            await player.save(self.bot)
        else:  # player is cached
            player = self.bot.players.players[user.id]
            for i in range(crafting_data['count']):
                player.inventory.add_item(item)
        if channel is not None and channel.permissions_for(channel.guild.me).send_messages:
            await channel.send(msg)
        else:
            try:
                await user.send(msg)
            except discord.HTTPException:
                pass

    @commands.group(invoke_without_command=True)
    @ensure_player
    async def craft(self, ctx, *, item):
        """Crafts an item of your choosing."""
        item = self.bot.item_cache.get_item(item.title())
        if not item:
            return await ctx.send("Couldn't find any items by that name.")
        if not isinstance(item, Craftable):
            return await ctx.send(f"You cannot craft **{item.name}** as it does not have a recipe.")
        if not item.can_craft(ctx.player.inventory):
            mats = '\n'.join(f'`{j}x {i}  (You have {ctx.player.inventory.get_item_count(i)})`' for i, j in item.recipe)
            return await ctx.send(f"You do not have enough materials to craft **{item.name}**. You require:\n"+mats)
        m = f'Crafting job will use:\n' + '\n'.join(f'`{j}x {i}`' for i, j in item.recipe)
        if not await ctx.confirm(f'{m}\n\nCraft {item.makes}x **{item.name}**?'):
            return
        for i, j in item.recipe:
            for __ in range(j):
                ctx.player.inventory.remove_item(i)
        await self.new_craft_task(ctx, item)
        await ctx.send(f'Now crafting {item.makes}x **{item.name}** and will finish in {item.time} minutes.')

    @craft.command()
    @ensure_player
    async def list(self, ctx):
        """Lists all items you can currently craft."""
        k = []
        ix = 1
        for item in self.bot.item_cache.items.values():
            if isinstance(item, Craftable) and item.can_craft(ctx.player.inventory):
                k.append(f'{ix}. {item.name}')
                ix += 1
        if not k:
            return await ctx.send("Not enough materials to craft anything \N{CONFUSED FACE}. "
                                  "Try opening some treasures to find materials.")
        pg = EmbedPaginator()
        if len(dt := '\n'.join(k)) > 2048:
            for chunk in [k[x:x+20] for x in range(0, len(dt), 20)]:
                pg.add_page(discord.Embed(description='\n'.join(chunk)))
        else:
            pg.add_page(discord.Embed(description=dt))
        await PaginationHandler(self.bot, pg, send_as='embed', wrap=True).start(ctx)

    @commands.command()
    @ensure_player
    async def inventory(self, ctx):
        """Opens your inventory and shows your items.
        You can select some items and use them if you wish,
        though some items may only be used in battle."""
        in_battle = ctx.author.id in self.bot.get_cog('BattleSystem').battles
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
        # self.bot.log.debug(f'c1 {c1.done()}, c1 {c2.done()}')
        if c2.done() and not c1.done():
            c1.cancel()
            return
        c2.cancel()
        try:
            m = c1.result()
        except asyncio.TimeoutError:
            return

        item = ctx.player.inventory.get_item(m.content.lower())
        try:
            if isinstance(item, HealingItem):
                if in_battle:
                    battle = self.bot.get_cog('BattleSystem').battles[ctx.author.id]
                    await item.use(ctx, battle=battle)
                    # item.use will raise Unusable before we hit skip turn
                    battle.skip_turn()
                else:
                    await item.use(ctx, battle=None)
            else:
                await item.use(ctx, battle=in_battle)
        except Unusable as e:
            await ctx.send(str(e))
            return
        if not ctx.player.inventory.remove_item(item.name):
            self.bot.log.warning(f"apparently {ctx.player} has {item}, but we couldnt remove it for some reason")


def setup(bot):
    bot.add_cog(Inventory(bot))
