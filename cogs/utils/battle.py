import math
import random


class Enemy:
    # wild encounters dont have a skill preference or an ai
    # literally choose skills at random

    # true battles will avoid skills that you are immune to,
    # and aim for skills that you are weak to / support themself
    def __init__(self, **data):
        bot = data.pop('bot')
        self.name = data.pop('name')
        self.level = data.pop('level')
        self.skills = [bot.players.skill_cache[n] for n in data.pop('skills')]
        self.strength, self.magic, self.endurance, self.agility, self.luck = data.pop('stats')
        self._damage_taken = 0
        self._sp_used = 0

    def __repr__(self):
        return "<Enemy>"

    def __str__(self):
        return self.name

    @property
    def hp(self):
        return self.max_hp - self._damage_taken

    @hp.setter
    def hp(self, value):
        if self.hp - value <= 0:
            self._damage_taken = self.max_hp
        else:
            self._damage_taken += value

    @property
    def max_hp(self):
        return math.ceil(20 + self.endurance + (4.7 * self.level))

    @property
    def sp(self):
        return self.max_sp - self._sp_used

    @sp.setter
    def sp(self, value):
        if self.sp - value <= 0:
            self._sp_used = self.max_sp
        else:
            self._sp_used += value

    @property
    def max_sp(self):
        return math.ceil(10 + self.magic + (3.6 * self.level))

    def is_fainted(self):
        return self.hp <= 0

    def exp(self):
        return math.ceil(self.level ** 3 / random.uniform(1, 3))


from discord.ext import ui
from .loops import loop

# exp = ceil(level ** 3 / uniform(1, 3))


def confirm_not_dead(battle):
    return not battle.enemy.is_fainted() and not battle.player.is_fainted()


class InitialSession(ui.Session):
    def __init__(self, battle):
        super().__init__(timeout=180)
        self.battle = battle
        self.player = battle.player
        self.enemy = battle.enemy

    async def send_initial_message(self):
        return await self.context.send(
f"""[{self.player.owner.name}] {self.player.name} VS {self.enemy.name} [Wild]
{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP

\N{CROSSED SWORDS} Fight
""")

    @ui.button('\N{CROSSED SWORDS}')
    async def fight(self, _):
        pass



class WildBattle:
    def __init__(self, player, enemy, ctx):
        self.ctx = ctx
        self.cmd = self.ctx.bot.get_cog("BattleSystem").yayeet
        self.player = player
        self.enemy = enemy
        self.main.start(self)

    @loop(predicate=confirm_not_dead)
    async def main(self, _):
        m = await self.ctx.send(f"""[{self.player.owner.name}] {self.player.name}
{self.player.hp}/{self.player.max_hp} HP
{self.player.sp}/{self.player.max_sp} SP
""")

    @main.after_loop
    async def post_battle_complete(self):
        if self.main.failed():
            err = self.main.get_task().exception()
            await self.ctx.invoke(self.cmd, battle=self, err=err)
            return
        # do exp stuff here
        await self.ctx.invoke(self.cmd, battle=self)
