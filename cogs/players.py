import asyncio
import collections
import contextlib
import itertools
import json
import random
from operator import itemgetter

import discord
from discord.ext import commands, ui

from cogs.utils.formats import ensure_player
from cogs.utils.objects import CaseInsensitiveDict
from cogs.utils.paginators import EmbedPaginator, PaginationHandler
from .utils import lookups, imaging, items
from .utils.enums import SkillType
from .utils.player import Player
from .utils.skills import Skill, GenericAttack, Guard

NL = '\n'


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
    leaf = player.leaf.cost//1000 if player.leaf else 'N/A'
    embed.description = _("""Current leaf: {player._active_leaf}
AP Points: {player.ap_points} | {leaf} to finish.""").format(player=player, leaf=leaf)
    embed.set_footer(text="<~ Stats | Skills ~>")
    return embed


def skills_page(player):
    embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.title = "Skills"
    embed.set_author(name=player.name, icon_url=player.owner.avatar_url_as(format='png', size=32))
    skills = [f'{lookups.TYPE_TO_EMOJI[skill.type.name.lower()]} {skill.name}' for skill in player.skills
              if skill.name not in ('Attack', 'Guard')]
    embed.description = '\n'.join(skills) or ':warning:'
    embed.set_footer(text=_('<~ Skill Tree Status | Unset skills ~>'))
    return embed


def unset_skills_page(player):
    embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.title = "Unused skills"
    embed.set_author(name=player.name, icon_url=player.owner.avatar_url_as(format='png', size=32))
    skills = [f'{lookups.TYPE_TO_EMOJI[skill.type.name.lower()]} {skill.name}' for skill in player.unset_skills]
    embed.description = '\n'.join(skills) or _('(All skills equipped)')
    embed.set_footer(text=_('<~ Skills'))
    return embed


def stats_page(player):
    embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.title = "{}'s stats".format(player.name)
    embed.set_author(name=player.name, icon_url=player.owner.avatar_url_as(format='png', size=32))
    embed.description = f"""\u2694 {_('Strength')}: {player.strength}
\u2728 {_('Magic')}: {player.magic}
\U0001f6e1 {_('Endurance')}: {player.endurance}
\U0001f3c3 {_('Agility')}: {player.agility}
\U0001f340 {_('Luck')}: {player.luck}"""
    embed.set_footer(text=_('<~ Home | Skill Tree Status ~>'))
    return embed


async def status(ctx):
    player = ctx.player
    embed = discord.Embed(title=f"Lvl{player.level} {player.name}",
                          colour=lookups.TYPE_TO_COLOUR[player.specialty.name.lower()])
    embed.set_author(name=player.owner, icon_url=player.owner.avatar_url_as(format="png", size=32))
    res = {}
    for key, value_iter in itertools.groupby(list(player.resistances.items()), key=itemgetter(1)):
        res.setdefault(key.name.lower(), []).extend([v[0].name.lower() for v in value_iter])
    res.pop("normal", None)
    spec = f"{lookups.TYPE_TO_EMOJI[player.specialty.name.lower()]} {player.specialty.name.title()}"
    res_fmt = "\n".join(
        [f"{FMT[k]}: {' '.join(map(lambda x: str(lookups.TYPE_TO_EMOJI[x.lower()]), v))}" for k, v in res.items()])
    # prog = int(player.exp_progress())
    prog = -1
    arcana = lookups.ROMAN_NUMERAL[player.arcana.value]
    desc = f"""**{arcana}** {player.arcana.name}

{player.description}

Specializes in {spec} type skills.
{NL + f'{player.exp_to_next_level()} to level {player._next_level}' + NL + f'{prog}%' + NL}
__Resistances__
{res_fmt}"""
    embed.description = desc
    embed.set_footer(text=_('Stats ~>'))

    pg = EmbedPaginator()
    for e in [embed, stats_page(player), prepare_skill_tree_page(player),
              skills_page(player), unset_skills_page(player)]:
        pg.add_page(e)
    await PaginationHandler(ctx.bot, pg, send_as="embed").start(ctx)


class Statistics(ui.Session):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.tots = [0, 0, 0, 0, 0]

    async def send_initial_message(self):
        self.message = await self.context.send(".")
        await self.update()
        return self.message

    async def update(self):
        embed = discord.Embed(title="Distribute your stat points!")
        embed.set_author(name=f'{self.player.name} levelled to L{self.player.level}')
        embed.set_footer(text="Stats cannot go higher than 99!")
        embed.description = f"""Points remaining: {self.player.stat_points}

\u2694 Strength: {self.player.strength}{f'+{self.tots[0]}' if self.tots[0] else ''}
\u2728 Magic: {self.player.magic}{f'+{self.tots[1]}' if self.tots[1] else ''}
\U0001f6e1 Endurance: {self.player.endurance}{f'+{self.tots[2]}' if self.tots[2] else ''}
\U0001f3c3 Agility: {self.player.agility}{f'+{self.tots[3]}' if self.tots[3] else ''}
\U0001f340 Luck: {self.player.luck}{f'+{self.tots[4]}' if self.tots[4] else ''}

\U0001f504 Reset distribution
\u2705 Confirm"""
        await self.message.edit(content="", embed=embed)

    @ui.button('\u2694')  # strength
    async def add_strength(self, _):
        if self.player.stat_points == 0 or self.player.strength + self.tots[0] == 99:
            return
        self.tots[0] += 1
        self.player.stat_points -= 1
        await self.update()

    @ui.button('\u2728')  # magic
    async def add_magic(self, _):
        if self.player.stat_points == 0 or self.player.magic + self.tots[1] == 99:
            return
        self.tots[1] += 1
        self.player.stat_points -= 1
        await self.update()

    @ui.button('\U0001f6e1')  # endurance
    async def add_endurance(self, _):
        if self.player.stat_points == 0 or self.player.endurance + self.tots[2] == 99:
            return
        self.tots[2] += 1
        self.player.stat_points -= 1
        await self.update()

    @ui.button('\U0001f3c3')  # agility
    async def add_agility(self, _):
        if self.player.stat_points == 0 or self.player.agility + self.tots[3] == 99:
            return
        self.tots[3] += 1
        self.player.stat_points -= 1
        await self.update()

    @ui.button('\U0001f340')  # luck
    async def add_luck(self, _):
        if self.player.stat_points == 0 or self.player.luck + self.tots[4] == 99:
            return
        self.tots[4] += 1
        self.player.stat_points -= 1
        await self.update()

    @ui.button('\U0001f504')  # reset
    async def reset(self, _):
        self.player.stat_points = sum(self.tots) + self.player.stat_points
        self.tots = [0, 0, 0, 0, 0]
        await self.update()

    @ui.button('\u2705')  # confirm
    async def confirm(self, _):
        self.player.strength += self.tots[0]
        self.player.magic += self.tots[1]
        self.player.endurance += self.tots[2]
        self.player.agility += self.tots[3]
        self.player.luck += self.tots[4]
        await self.message.delete()

    async def stop(self):
        with contextlib.suppress(discord.HTTPException):
            await super().stop()


def ensure_no_player(func):
    async def predicate(ctx):
        if ctx.author.id in ctx.bot.players.players:
            return False
        elif await ctx.bot.db.abyss.accounts.find_one({"owner": ctx.author.id}) is not None:
            return False
        return True

    return commands.check(predicate)(func)


class Players(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = LRUDict(20, bot)
        self.skill_cache = CaseInsensitiveDict({"Attack": GenericAttack, "Guard": Guard})
        self._base_demon_cache = {}
        self.bot.unload_tasks[self] = self._unloader_task = self.bot.loop.create_task(self.flush_cached_players())
        self.cache_skills()
        bot.item_cache = items._ItemCache(self)

    def __repr__(self):
        return f"<PlayerHandler {len(self.players)} loaded, {len(self.skill_cache)} skills>"

    def cog_unload(self):
        task = self.bot.unload_tasks.pop(self)
        task.cancel()

    async def flush_cached_players(self):
        await self.bot.wait_for("logout")
        for i in range(len(self.players)):
            _, player = self.players.popitem()
            await player.save(self.bot)

    def cache_skills(self):
        with open("skill-data.json") as f:
            sd = json.load(f)
        for skill in sd:
            self.skill_cache[skill['name']] = Skill(**skill)

        with open("base-demons.json") as f:
            demon_data = json.load(f)
        for demon in demon_data:
            self._base_demon_cache[demon['name']] = demon

        try:
            self.bot.tree.do_cuz_ready()
        except (KeyError, AttributeError):
            pass

    async def cog_command_error(self, ctx, error):
        if ctx.command is self.create and isinstance(error, commands.CheckFailure):
            return await ctx.send("You can't create multiple players!")
        self.bot.dispatch("command_error", ctx, error, force=True)

    # -- finally, some fucking commands -- #

    @commands.command(hidden=True)
    @commands.is_owner()
    async def debug_create(self, ctx):
        pass

    @commands.command()
    @ensure_no_player
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def create(self, ctx):
        """Creates a new player.
        You will be given a random demon to use throughout your journey."""

        msg = _("This appears to be a public server. The messages sent can get spammy, or cause ratelimits.\n"
                "It is advised to use a private server/channel.")

        if sum(not m.bot for m in ctx.channel.members) > 100:
            await ctx.send(msg)
            await asyncio.sleep(5)

        # task = self.bot.loop.create_task(scripts.do_script(ctx, "creation", i18n.current_locale.get()))

        demon = random.choice(list(self._base_demon_cache.keys()))
        data = self._base_demon_cache[demon]
        while data.get('testing', False):
            demon = random.choice(list(self._base_demon_cache.keys()))
            data = self._base_demon_cache[demon]
        data['owner'] = ctx.author.id
        data['exp'] = 125
        data['skill_leaf'] = None
        data['unsetskills'] = []
        data['location'] = ('Sample Dungeon', 'Floor 1')
        data['area'] = 'Floor 1'
        # TODO: update this when we add a real map
        player = Player(**data)

        # await task
        # if not task.result():
        # ctx.command.reset_cooldown(ctx)
        # return

        # await self.bot.redis.set(f"story@{ctx.author.id}", 1)

        self.players[ctx.author.id] = player
        await player._populate_skills(self.bot)
        await player.save(self.bot)

        # await ctx.send(
        # _("<꽦䐯嬜継ḉ> The deed is done. You have been given the demon `{player.name}`. Use its power wisely..."
        # ).format(player=player))
        await ctx.send(f"Done. You now control the demon `{player.name}`.")

    @commands.command()
    @ensure_player
    async def status(self, ctx):
        """Gets your current players status."""

        await status(ctx)  # todo: maybe move this? idk its a lot of shit i dont want to break

    @commands.command()
    @ensure_player
    async def delete(self, ctx):
        """Deletes your player.
        ! THIS ACTION IS IRREVERSIBLE !"""

        m1 = await ctx.send("Are you sure you want to delete your account? This action is irreversible.")
        if not await self.bot.confirm(m1, ctx.author):
            return

        m2 = await ctx.send("...are you really sure?")
        if not await self.bot.confirm(m2, ctx.author):
            return

        await asyncio.gather(m1.delete(), m2.delete())

        scandata = await self.bot.redis.scan(0, match=f'*{ctx.author.id}*', count=1000)
        for key in scandata[1]:
            if key.startswith('locale'):
                continue  # keep locale settings
            await self.bot.redis.delete(key)

        self.players.pop(ctx.author.id)
        await self.bot.db.abyss.accounts.delete_one({"owner": ctx.author.id})
        await ctx.send(self.bot.tick_yes)

    @commands.command(hidden=True)
    @ensure_player
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def profile(self, ctx):
        if not ctx.player:
            return await ctx.send("You don't own a player.")

        data = await imaging.profile_executor(self.bot, ctx.player)
        await ctx.send(file=discord.File(data, 'profile.png'))

    @commands.command()
    @ensure_player
    async def levelup(self, ctx):
        """Levels up your player, if possible.
        Also lets you divide your spare stat points to increase your stats."""
        if ctx.player.can_level_up:
            ctx.player.level_up()
        if ctx.player.stat_points > 0:
            new = Statistics(ctx.player)
            await new.start(ctx)
        else:
            await ctx.send("You have no skill points remaining.")

    @commands.command(name='set')
    @ensure_player
    async def _set(self, ctx, *, name):
        """Puts an inactive skill into your repertoire."""
        if not ctx.player:
            return
        name = name.title()
        if name in ('Attack', 'Guard'):
            return await ctx.send("um lol?")
        if name not in self.skill_cache:
            return await ctx.send("Couldn't find a skill by that name.")
        skill = self.skill_cache[name]
        if skill not in ctx.player.unset_skills:
            if skill in ctx.player.skills:
                return await ctx.send("That skill is already in your repertoire.")
            return await ctx.send("You haven't unlocked that skill yet.")
        if len(ctx.player.skills)-2 == 8:  # -2 for Guard and Attack
            return await ctx.send("You can't equip more than 8 skills.")
        ctx.player.skills.append(skill)
        ctx.player.unset_skills.remove(skill)
        await ctx.send(self.bot.tick_yes)

    @commands.command()
    @ensure_player
    async def unset(self, ctx, *, name):
        """Removes an active skill from your repertoire."""
        if not ctx.player:
            return
        name = name.title()
        if name in ('Attack', 'Guard'):
            return await ctx.send("You can't remove that skill.")
        if name not in self.skill_cache:
            return await ctx.send("Couldn't find a skill by that name.")
        skill = self.skill_cache[name]
        cp = ctx.player.skills.copy()
        cp.remove(skill)
        if all(s.type is SkillType.PASSIVE for s in cp):
            return await ctx.send("You must have at least 1 non-active skill equipped.")
        if skill not in ctx.player.skills:
            if skill in ctx.player.unset_skills:
                return await ctx.send("That skill is not in your repertoire.")
            return await ctx.send("You haven't unlocked that skill yet.")
        if len(ctx.player.skills)-2 == 1:
            return await ctx.send("You must equip at least 1 skill.")
        ctx.player.unset_skills.append(skill)
        ctx.player.skills.remove(skill)
        await ctx.send(self.bot.tick_yes)


def setup(bot):
    bot.add_cog(Players(bot))
