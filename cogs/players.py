import asyncio
import contextlib
import itertools
import random
from operator import itemgetter

import discord
import json5
from discord.ext import commands, ui

from .utils import lookups, scripts, i18n, imaging
from .utils.objects import Player, Skill

import collections


FMT = {
    'weak': 'Weak to:',
    'resist': 'Resists:',
    'immune': 'Immune to:',
    'absorb': 'Absorbs:',
    'reflect': 'Reflects:'
}


class LRUDict(collections.OrderedDict):
    """a dictionary with fixed size, sorted by last use

    credit to lambda#0987"""

    def __init__(self, size, bot):
        super().__init__()
        self.size = size
        self.bot = bot

    def __getitem__(self, key):
        # move key to the end
        result = super().__getitem__(key)
        del self[key]
        super().__setitem__(key, result)
        return result

    def __setitem__(self, key, value):
        try:
            # if an entry exists at key, make sure it's moved up
            del self[key]
        except KeyError:
            # we only need to do this when adding a new key
            if len(self) >= self.size:
                k, v = self.popitem(last=False)
                asyncio.run_coroutine_threadsafe(v.save(self.bot), loop=self.bot.loop)

        super().__setitem__(key, value)


def prepare_skill_tree_page(player):
    embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.title = "Skill tree status"
    embed.set_author(name=player.name, icon_url=player.owner.avatar_url_as(format="png", size=32))
    leaf = player.leaf['cost']//1000 if player.leaf else 'N/A'
    embed.description = _("""Current leaf: {player._active_leaf}
AP Points: {player.ap_points} | {leaf} to finish.""").format(player=player, leaf=leaf)
    embed.set_footer(text="<~ Home | Skills ~>")
    return embed


def skills_page(player):
    embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.title = "Skills"
    embed.set_author(name=player.name, icon_url=player.owner.avatar_url_as(format='png', size=32))
    skills = [f'{lookups.TYPE_TO_EMOJI[skill.type.name.lower()]} {skill.name}' for skill in player.skills]
    embed.description = '\n'.join(skills) or 'No skills? wtf'
    embed.set_footer(text='<~ Skill Tree Status')
    return embed


class Status(ui.Session):
    def __init__(self, player):
        super().__init__(timeout=120)
        embed = discord.Embed(title=player.name, colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
        embed.set_author(name=player.owner, icon_url=player.owner.avatar_url_as(format="png", size=32))
        res = {}
        for key, value_iter in itertools.groupby(list(player.resistances.items()), key=itemgetter(1)):
            res.setdefault(key.name.lower(), []).extend([v[0].name.lower() for v in value_iter])
        res.pop("normal", None)
        spec = f"{lookups.TYPE_TO_EMOJI[player.specialty.name.lower()]} {player.specialty.name.title()}"
        res_fmt = "\n".join(
            [f"{FMT[k]}: {' '.join(map(lambda x: str(lookups.TYPE_TO_EMOJI[x.lower()]), v))}" for k, v in res.items()])
        arcana = lookups.ROMAN_NUMERAL[player.arcana.value]
        desc = _("""**{arcana}** {player.arcana.name}

{player.description}

Specializes in {spec} type skills.

__Resistances__
{res_fmt}""").format(**locals())
        embed.description = desc
        embed.set_footer(text='Skill Tree Status ~>')
        self.pages = [embed, prepare_skill_tree_page(player), skills_page(player)]
        self.current_page = 0

    async def send_initial_message(self):
        return await self.context.send(embed=self.pages[0])

    async def handle_timeout(self):
        await self.stop()

    async def stop(self):
        await self.message.delete()
        await super().stop()

    @ui.button('\u25c0')
    async def back(self, payload):
        if self.current_page + 1 > 0:
            self.current_page -= 1
        else:
            return
        await self.message.edit(embed=self.pages[self.current_page])

    @ui.button('\u23f9')
    async def _stop(self, payload):
        await self.stop()

    @ui.button('\u25b6')
    async def next(self, payload):
        if self.current_page + 1 < len(self.pages):
            self.current_page += 1
        else:
            return
        await self.message.edit(embed=self.pages[self.current_page])


async def confirm(bot, msg, user):
    rs = (str(bot.tick_yes), str(bot.tick_no))
    for r in rs:
        await msg.add_reaction(r)
    try:
        r, u = await bot.wait_for('reaction_add', check=lambda r, u: str(r.emoji) in rs and u.id == user.id and
                                  r.message.id == msg.id, timeout=60)
    except asyncio.TimeoutError:
        return False
    else:
        if str(r.emoji) == rs[0]:
            return True
        return False
    finally:
        with contextlib.suppress(discord.Forbidden):
            await msg.clear_reactions()


class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = LRUDict(20, bot)
        self.skill_cache = {}
        self._base_demon_cache = {}
        self._skill_cache_task = self.bot.loop.create_task(self.cache_skills())
        self.bot.unload_tasks[self] = self._unloader_task = self.bot.loop.create_task(self.flush_cached_players())

        with open("skilltree.json") as f:
            self.skill_tree = json5.load(f)

    def __repr__(self):
        return f"<PlayerHandler {len(self.players)} loaded,\n\t{self._skill_cache_task!r}>"

    def cog_unload(self):
        task = self.bot.unload_tasks.pop(self)
        task.cancel()

    async def cog_before_invoke(self, ctx):
        try:
            ctx.player = self.players[ctx.author.id]
        except KeyError:
            data = await self.bot.db.adventure2.accounts.find_one({"owner": ctx.author.id})
            if not data:
                ctx.player = None
                return
            ctx.player = self.players[ctx.author.id] = player = Player(**data)
            player._populate_skills(self.bot)
            if player._active_leaf is not None:
                key, _ = player._active_leaf.split(':')
                branch = self.skill_tree[key]
                player.leaf = branch[player._active_leaf]

    async def flush_cached_players(self):
        await self.bot.wait_for("logout")
        for i in range(len(self.players)):
            _, player = self.players.popitem()
            await player.save(self.bot)

    async def cache_skills(self):
        await self.bot.prepared.wait()

        async for skill in self.bot.db.adventure2.skills.find():
            skill.pop("_id")
            self.skill_cache[skill['name']] = Skill(**skill)

        async for demon in self.bot.db.adventure2.basedemons.find():
            demon.pop("_id")
            self._base_demon_cache[demon['name']] = demon

    # -- finally, some fucking commands -- #

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def create(self, ctx):
        """Creates a new player.
        You will be given a random demon to use throughout your journey."""
        if ctx.player:
            return await ctx.send(_("You already own a player."))

        running = bool(await self.bot.redis.get(f'making:{ctx.author.id}'))
        if running:
            return
        await self.bot.redis.set(f'making:{ctx.author.id}', 'gay')

        msg = _("This appears to be a public server. The messages sent can get spammy, or cause ratelimits.\n"
                "It is advised to use a private server/channel.")

        if sum(not m.bot for m in ctx.channel.members) > 100:
            await ctx.send(msg)
            await asyncio.sleep(5)

        task = self.bot.loop.create_task(scripts.do_script(ctx, "creation", i18n.current_locale.get()))

        if not await self.bot.is_owner(ctx.author):
            demon = random.choice(list(self._base_demon_cache.keys()))
            data = self._base_demon_cache[demon]
            while data['testing']:
                demon = random.choice(list(self._base_demon_cache.keys()))
                data = self._base_demon_cache[demon]
        else:
            data = self._base_demon_cache['debug']
            data['testing'] = True
        data['owner'] = ctx.author.id
        data['exp'] = 0
        data['skill_leaf'] = None
        player = Player(**data)

        await task
        if not task.result():
            ctx.command.reset_cooldown(ctx)
            await self.bot.redis.delete(f'making:{ctx.author.id}')
            return

        self.players[ctx.author.id] = player
        player._populate_skills(self.bot)
        await player.save(self.bot)

        await ctx.send(
            _("???: The deed is done. You have been given the demon `{player.name}`. Use its power wisely...").format(
                player=player))
        await self.bot.redis.delete(f'making:{ctx.author.id}')

    @commands.command()
    async def status(self, ctx):
        """Gets your current players status."""
        if not ctx.player:
            return await ctx.send(_("You don't own a player."))
        
        session = Status(ctx.player)
        await session.start(ctx)

    @commands.command()
    async def delete(self, ctx):
        """Deletes your player.
        ! THIS ACTION IS IRREVERSIBLE !"""
        if not ctx.player:
            return

        m1 = await ctx.send(_("Are you sure you want to delete your account? This action is irreversible."))
        if not await confirm(self.bot, m1, ctx.author):
            return

        m2 = await ctx.send(_("...are you really sure?"))
        if not await confirm(self.bot, m2, ctx.author):
            return

        await asyncio.gather(m1.delete(), m2.delete())

        with contextlib.suppress(KeyError):
            self.players.pop(ctx.author.id)
        await self.bot.db.adventure2.accounts.delete_one({"owner": ctx.author.id})
        await ctx.send(self.bot.tick_yes)

    @commands.command()
    async def profile(self, ctx):
        if not ctx.player:
            return

        data = await imaging.profile_executor(self.bot, ctx.player)
        await ctx.send(file=discord.File(data, 'profile.png'))


def setup(bot):
    bot.add_cog(Players(bot))
