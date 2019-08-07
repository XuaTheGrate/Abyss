import discord
from discord.ext import commands


class Meta(commands.Cog):
    @commands.command()
    async def ping(self, ctx):
        """Get my websocket latency to Discord."""
        await ctx.send(f":ping_pong: Pong! | {ctx.bot.latency*1000:.2f}ms websocket latency.")

    @commands.command(aliases=['about'])
    async def info(self, ctx):
        """Information about the bot."""
        await ctx.send(f"""Hi! I'm {ctx.me.name}, a W.I.P. RPG bot for Discord.
I am in very beta, be careful when using my commands as they are not ready for public use yet.
Currently gazing over {len(ctx.bot.guilds)} servers, enjoying {len(ctx.bot.users):,} users' company.
I don't have my own support server, so you can join my owners general server here: <https://discord.gg/hkweDCD>""")

    @commands.group(invoke_without_command=True)
    async def faq(self, ctx):
        """Brings up the Frequently Asked Questions."""
        embed = discord.Embed(title="FAQ")
        embed.description = "\n".join(f"${c}" for c in self.faq.commands)
        await ctx.send(embed=embed)

    @faq.group()
    async def battle(self, ctx):
        embed = discord.Embed(title="FAQ: Battle")
        embed.description = """Each battle will require you to fight against one or more opponents.
> __Losing the battle will not be tolerated.__
Each demon gets a turn. The fastest demon moves first, in order of your Agility stat.
There is an exception to this, however.
If you successfully **ambush** the enemy, you will be guaranteed to move first, then the enemies move in order of their agility.
If you are **ambushed** by the enemy, they will move in order of their agility before you get your turn.
Winning the battle will earn EXP, Credits and you may even obtain an item."""
        await ctx.send(embed=embed)

    @faq.command()
    async def resistances(self, ctx):
        embed = discord.Embed(title="FAQ: Resistances")
        embed.description = """Each demon has their own unique resistances.
Some may not have a weakness, and some may not have a resistance.
Some may even nullify all attacks of a certain type.
The demons themselves cannot nullify attacks without the use of a Null skill.
A Null skill can nullify, increase resistance/evasion against, absorb or repel attacks of a certain type.
There is one of each for all types, excluding Light and Dark (instant death).
Exploiting an enemies weakness in battle will give you another turn to act.
Be careful, as the enemy can also exploit your weakness, which will give them another turn.

Attacks the enemy is **weak** to will deal 1.5x more damage if they are not guarding.
On top of this, you will get another turn.
If the enemy **resists** an attack, it will deal 0.5x damage.

The following 3 only apply with a passive skill. No (none, 0) players will have these without the skill. (Not including demons)
Nulling an attack is as simple as it sounds. Does no damage.
Repelling an attack will deal 0.65x damage back to you, resistance inclusive.
(If you also repel those attacks, it is instead nullified)
Absorbsing an attack will heal the target by 0.5x the damage you would have dealt, resistance exclusive.

Todo: exploiting all enemies' weaknesses (players only) grants bonuses
Todo: exploiting an enemy's weakness will knock them down, nullifying any evasion and increasing damage taken by 1.15x
Todo: dont obtain bonus turns for exploting the same enemy's weakness twice"""
        await ctx.send(embed=embed)

    @faq.command()
    async def skills(self, ctx):
        embed = discord.Embed(title="FAQ: Skills")
        embed.description = """Each skill has their own type, power, accuracy and possible secret ability.
There are 6 categories of skills:
> __Physical__
The physical damaging skills. These are the only skills that can land **Criticals**.
Physical and Gun type skills fall under this category.
> __Special__
The special damaging skills. These skills cannot land **Criticals**, but have unique effects opposed to most Physical skills.
Fire, Wind, Electric, Ice, Nuclear, Psychokinetic, Bless, Curse and Almighty type skills fall under this category.
> __Support__
Non-damaging skills focused on buffing your team, or debuffing the opposing team. `Guard` also falls under here.
These include buffs/debuffs, manual type negation or skill charging.
> __Healing__
Anti-damaging skills focused on keeping you alive, or healing status effects.
**Items** do the same thing, but are expensive. Healing skills only use your SP.
> __Passive__
Unusable skills that activate automatically when a certain requirement is met.
Can be automatic buffs at the start of battle, increased criticals or even automatic skill negation.
> __Ailment__
Non-damaging skills to inflict various status ailments on the enemy.
You can view `$faq ailments` to view information about every ailment."""
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Meta())
