import random
import re
import traceback
from abc import ABC
from contextlib import suppress

import discord
import tabulate
from discord.ext import ui

from .enums import AilmentType, ResistanceModifier, SkillType
from . import lookups


NL = '\n'
FAKE_ENEMY_DATA = {
    "user_id": 0,
    "enemy": "replace me",
    "resistances": [-1 for a in range(10)],
    "moves": []
}


class TargetSession(ui.Session, ABC):
    def __init__(self, *targets, target='enemy'):
        super().__init__(timeout=180)
        if target in ('enemy', 'ally'):
            self.targets = {f"{c + 1}\u20e3": targets[c] for c in range(len(targets))}
            for e in self.targets.keys():
                self.add_button(self.button_enemy, e)
        elif target in ('enemies', 'self', 'allies'):
            self.targets = targets
            self.add_button(self.target_enemies, '<:tickYes:568613200728293435>')
        else:
            raise RuntimeError("unhandled target")
        self.result = None
        self.target = target

    async def send_initial_message(self, dm=False):
        if self.target == 'enemy':
            c = ["**Pick a target!**\n"]
            # noinspection PyUnresolvedReferences
            c.extend([f"{a} {b.name}" for a, b in self.targets.items()])
            # log.debug("target session initial message")
            return await self.context.send(NL.join(c))
        elif self.target == 'enemies':
            c = ["**Targets all enemies**\n"]
            c.extend([str(e) for e in self.targets])
            return await self.context.send(NL.join(c))
        elif self.target == 'self':
            return await self.context.send("**You can only use this skill on yourself**")
        elif self.target == 'allies':
            c = ["**Targets all allies**\n"]
            c.extend([str(e) for e in self.targets])
            return await self.context.send(NL.join(c))
        elif self.target == 'ally':
            c = ["**Choose an ally!**\n"]
            # noinspection PyUnresolvedReferences
            c.extend([f'{a} {b.name}' for a, b in self.targets.items()])
            return await self.context.send(NL.join(c))

    async def stop(self):
        with suppress(discord.HTTPException):
            await self.message.delete()
        # log.debug("le stop()")
        await super().stop()

    @ui.button("<:tickNo:568613146152009768>")
    async def cancel(self, _):
        self.result = 'cancel'
        await self.stop()

    async def button_enemy(self, payload):
        # log.debug("le button")
        # noinspection PyTypeChecker
        self.result = (self.targets[str(payload.emoji)],)
        await self.stop()

    async def target_enemies(self, _):
        self.result = self.targets
        await self.stop()


class InitialSession(ui.Session, ABC):
    def __init__(self, battle, player):
        # log.debug("initial session init")
        self._message = None
        self._k = 0
        super().__init__(timeout=180)
        self.battle = battle
        self.player = player
        self.enemies = battle.enemies
        self.bot = battle.ctx.bot
        self.result = None  # dict, {"type": "fight/run", data: [whatever is necessary]}
        self.add_command(self.select_skill, "(" + "|".join(map(str, filter(
            lambda s: s.type is not SkillType.PASSIVE, self.player.skills))) + ")")

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, value):
        # print(f"saved stack to stack-{self._k}.txt")
        # with open(f"stack-{self._k}.txt", "w") as f:
        #     for line in traceback.format_stack():
        #         f.write(line.strip('\n'))
        # self._k += 1
        self._message = value

    async def stop(self):
        # log.debug("initialsession stop()")
        with suppress(discord.HTTPException):
            await self.message.delete()
        await super().stop()

    async def start(self, ctx, *, dm=False):
        self.context = ctx

        self.message = await self.send_initial_message(dm)
        # `self.context` is replaced inside `send_initial_message` if `dm is True`
        # however, an initial context is required to re-get the context
        # so we always use a base context first, then use the updated one down the road

        if self.allowed_users is None:
            self.allowed_users = {ctx.author.id}

        await self._prepare()
        # log.debug("after prepare")

        # log.debug("before loop")
        await self._Session__loop()  # @ikusaba-san pls
        # log.debug("after loop")

    async def select_target(self, target):
        # log.debug("initialsession target selector")
        if target in ('enemy', 'enemies'):
            menu = TargetSession(*[e for e in self.enemies if not e.is_fainted()], target=target)
        elif target == 'self':
            menu = TargetSession(self.player, target=target)
        elif target in ('ally', 'allies'):
            # this is a 1 player only battle, but for future reference this needs to return all allies
            menu = TargetSession(self.player, target=target)
        else:
            raise RuntimeError

        await menu.start(self.context)
        if not menu.result:
            # log.debug("no result")
            return 'cancel'
        # log.debug(f"result: {menu.result!r}")
        return menu.result

    async def select_skill(self, _, skill):
        obj = self.bot.players.skill_cache[skill.title()]
        if skill.lower() == 'guard':
            self.result = {"type": "fight", "data": {"skill": obj}}
            return await self.stop()
        target = await self.select_target(obj.target)
        if target != 'cancel':
            self.result = {"type": "fight", "data": {"skill": obj, "targets": target}}
            # log.debug(f"select skill: {self.result}")
            await self.stop()

    async def handle_timeout(self):
        self.result = {"type": "run", "data": {"timeout": True}}
        # log.debug("timeout")
        await self.stop()

    async def on_message(self, message):
        if message.channel.id != self.message.channel.id:
            return

        if message.author.id not in self.allowed_users:
            return

        if self.player.inventory.open:
            return  # we dont want to run commands while our inventory is open

        for pattern, command in self.__ui_commands__.items():
            match = re.fullmatch(pattern, message.content, flags=re.IGNORECASE)
            if not match:
                continue
            # log.debug("callback found for message")
            callback = command.__get__(self, self.__class__)
            await self._queue.put((callback, message, *match.groups()))
            break

    @property
    def header(self):
        return f"""(Turn {self.battle.turn_cycle})
{NL.join(e.header() for e in self.battle.players)}
VS
{NL.join(e.header() for e in self.enemies)}

{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP"""

    def get_home_content(self):
        return _(f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{BLACK QUESTION MARK ORNAMENT} Help
\N{INFORMATION SOURCE} Overview
\N{RUNNER} Escape
""")

    async def send_initial_message(self, dm=False):
        # log.debug("sent initial message")
        if not dm:
            m = await self.context.send(self.get_home_content())
            # log.debug(f"sent non-dm message {m!r}")
            return m
        else:
            m = await self.player.owner.send(self.get_home_content())
            old_ctx = self.context
            self.context = await self.context.bot.get_context(m)
            # log.debug(f"changed context and sent dm message {m!r} {old_ctx!r} {self.context!r} {old_ctx is self.context}")
            return m

    @ui.button('\N{CROSSED SWORDS}')
    async def fight(self, __):
        # log.debug("fight() called")
        skills = []
        for skill in self.player.skills:
            if skill.type is SkillType.PASSIVE:
                continue
            e = lookups.TYPE_TO_EMOJI[skill.type.name.lower()]
            if skill.uses_sp:
                cost = skill.cost
                if any(s.name == 'Spell Master' for s in self.player.skills):
                    cost /= 2
                can_use = self.player.sp >= cost
                if skill.name != 'Guard' and self.player.ailment and self.player.ailment.type is AilmentType.FORGET:
                    can_use = False
                t = 'SP'
            else:
                if skill.cost != 0:
                    cost = self.player.max_hp * (skill.cost / 100)
                    if any(s.name == 'Arms Master' for s in self.player.skills):
                        cost /= 2
                else:
                    cost = 0
                can_use = self.player.max_hp > cost
                if skill.name != 'Attack' and self.player.ailment and self.player.ailment.type is AilmentType.FORGET:
                    can_use = False
                t = 'HP'
            if can_use:
                skills.append(f"{e} {skill} ({cost:.0f} {t})")
            else:
                skills.append(f"{e} ~~{skill} ({cost:.0f} {t})~~")

        await self.message.edit(content=_(
            f"{self.header}\n\n{NL.join(skills)}\n\n> Use \N{HOUSE BUILDING} to go back"), embed=None)

    @ui.button("\N{BLACK QUESTION MARK ORNAMENT}")
    async def help(self, __):
        # log.debug("info() called")
        embed = discord.Embed(title="How to: Interactive Battle")
        embed.description = _("""Partially ported from Adventure, the battle system has been revived!
Various buttons have been reacted for use, but move selection requires you to send a message.
\N{CROSSED SWORDS} Brings you to the Fight menu, where you select your moves.
\N{BLACK QUESTION MARK ORNAMENT} Shows this page.
\N{INFORMATION SOURCE} Overviews the enemies on field.
\N{RUNNER} Runs from the battle. Useful if you don't think you can beat this enemy.
\N{HOUSE BUILDING} Brings you back to the home screen.

For more information regarding battles, see `$faq battle`.""")
        await self.message.edit(content="", embed=embed)

    @ui.button("\N{INFORMATION SOURCE}")
    async def status(self, __):
        """
$dev eval discord.Embed(title='[Wild] Arsene ● Lv. 1',
 colour=discord.Colour.greyple(), description='546 Max HP ● 216 Max SP').add_field(name='Resistances', value='''
**Normal**: :fire~1::almighty:
**Resists**: :phys::nuke:
**Weak**: :gun~1::psy:
**Immune**: :ice::curse:
**Repel**: :wind::bless:
**Absorb**: :elec:''').add_field(name='Stats', value='''
:crossed_swords: **Strength** 5
:sparkles: **Magic** 5
:shield: **Endurance** 5
:runner: **Agility** 5
:four_leaf_clover: **Luck** 5''').add_field(name='Moves', value='''```
Lunge | Lunge
Lunge | Lunge
 ???  | Lunge
Lunge | Lunge```''', inline=False)
        """
        s = TargetSession(*self.enemies)
        await s.start(self.context)
        target = s.result
        if target == 'cancel':
            return
        target = target[0]
        p = discord.Embed(title=f'[Wild] {target.name} ● Lv. {target.level_}')
        p.description = f'{target.max_hp} Max HP ● {target.max_sp} Max SP'
        res_data = await self.context.bot.db.abyss.demonresearch.find_one({"user_id": self.player.owner.id, "enemy": target.name})
        if not res_data:
            res_data = FAKE_ENEMY_DATA.copy()
            res_data['enemy'] = target.name
        fdata = {}
        for res, val in zip(SkillType, res_data['resistances']):
            if val != -1:
                mod = ResistanceModifier(val)
                fdata.setdefault(mod.name.title(), []).append(lookups.TYPE_TO_EMOJI[res.name.lower()])
        p.add_field(name='Resistances', value='\n'.join(f'**{k}**: {"".join(map(str, v))}' for k, v in fdata.items()) or '???')
        p.add_field(name='Stats', value=f'''\N{CROSSED SWORDS} **Strength** {target.strength}
\N{SPARKLES} **Magic** {target.magic}
\N{SHIELD} **Endurance** {target.endurance}
\N{FOUR LEAF CLOVER} **Luck** {target.luck}
\N{RUNNER} **Agility** {target.agility}''')
        s = res_data['moves']
        while len(s) != 8:
            s.append('???')
        skills = tabulate.tabulate([s[x:x+2] for x in range(0, 8, 2)], tablefmt='presto')
        p.add_field(name='Moves', value=f'```\n{skills}\n```', inline=False)
        p.set_footer(text="Reaction control is still enabled, click \N{HOUSE BUILDING} to go back.")
        await self.message.edit(content="", embed=p)

    @ui.button("\N{RUNNER}")
    async def escape(self, _):
        # log.debug("escape() called")
        chance = 75 - (max(self.enemies, key=lambda e: e.level).level - self.player.level)
        self.result = {"type": "run", "data": {"success": random.randint(1, 100) < chance}}
        return await self.stop()

    @ui.button("\N{HOUSE BUILDING}")
    async def ret(self, _):
        # log.debug("ret() called")
        await self.message.edit(content=f"""{self.header}

\N{CROSSED SWORDS} Fight
\N{BLACK QUESTION MARK ORNAMENT} Help
\N{INFORMATION SOURCE} Overview
\N{RUNNER} Escape""", embed=None)
