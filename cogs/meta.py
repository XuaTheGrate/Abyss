import collections
import inspect
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

import discord
import humanize
import psutil
from discord.ext import commands

from cogs.utils import weather
from cogs.utils.paginators import EmbedPaginator, PaginationHandler

NL = '\n'
R = re.compile(r"Description:\s+(.+)$")


class Meta(commands.Cog):
    def __init__(self):
        self.proc = psutil.Process()
        self.bucket = commands.CooldownMapping.from_cooldown(1, 3600, commands.BucketType.default)
        self._changelog = None

    def update_changelog(self):
        with open("changelog") as file:
            changelog = file.read()
        pages = changelog.split('-'*20+'\n')
        if not self._changelog:
            self._changelog = []
        self._changelog.clear()
        for page in pages:
            embed = discord.Embed(title=re.findall(r'^\*\*(v\d\.\d\.\d(?: Alpha)?)\*\*$', page, flags=re.M)[0])
            embed.description = '\n'.join(l.lstrip('* ') for l in page.split('\n')[1:])
            self._changelog.append(embed)

    @commands.command()
    async def support(self, ctx):
        """Sends my owners general server invite link."""
        await ctx.send("https://discord.gg/hkweDCD")

    @commands.command()
    async def invite(self, ctx):
        """Sends a discord url to invite me to your server."""
        perms = discord.Permissions(379968)
        await ctx.send('<'+discord.utils.oauth_url(ctx.me.id, perms)+'>')

    @commands.command(aliases=['vote'])
    async def dbl(self, ctx):
        """Sends the DBL link to my page."""
        await ctx.send('https://top.gg/bot/574442175534989322')

    @commands.command()
    @commands.cooldown(1, 5)
    async def changelog(self, ctx):
        """Views recent updates, fixes and additions."""
        ratelimited = self.bucket.update_rate_limit(ctx.message)
        if not ratelimited:
            self.update_changelog()
        assert self._changelog
        paginator = EmbedPaginator()
        for page in self._changelog:
            paginator.add_page(page)
        await PaginationHandler(ctx.bot, paginator, send_as='embed').start(ctx)

    @commands.command()
    async def ping(self, ctx):
        """Get my websocket latency to Discord."""
        await ctx.send(f":ping_pong: Pong! | {ctx.bot.latency * 1000:.2f}ms websocket latency.")

    @commands.command()
    async def ping2(self, ctx):
        """Measures round trip time to Discord."""
        start = time.perf_counter()
        msg = await ctx.send("\u200b")
        end = time.perf_counter() - start
        await msg.edit(content=f':ping_pong: Pong! | {end*1000:.2f}ms')

    @commands.command(aliases=['about'])
    async def info(self, ctx):
        """Information about the bot."""
        await ctx.send(f"""Hi! I'm {ctx.me.name}, a W.I.P. RPG bot for Discord.
I am in very beta, be careful when using my commands as they are not ready for public use yet.
Currently gazing over {len(ctx.bot.guilds)} servers, enjoying {len(ctx.bot.users):,} users' company.
I don't have my own support server, so you can join my owners general server here: <https://discord.gg/hkweDCD>

Created by {', '.join(str(ctx.bot.get_user(u)) for u in ctx.bot.config.OWNERS)}""")

    @commands.command()
    async def forecast(self, ctx):
        """Gets the weather forecast for the week."""
        _now = datetime.utcnow()
        start = _now - timedelta(days=3)
        season = weather.get_current_season()
        embed = discord.Embed(title=f"Weekly Forecast: {_now.strftime('%B')} ({season.name.title()})")
        embed.description = ""
        for day in range(0, 7):
            date = start + timedelta(days=day)
            day = date.strftime("%a")
            current_weather = weather.get_current_weather(date)
            wind_speed = weather.get_wind_speed(date)
            fmt = f"{current_weather.name.replace('_', ' ').title()}"
            if date.day == _now.day:
                embed.description += f"> `{day} {date.strftime('%d')}: {fmt} ({wind_speed}km/h wind speed)`\n"
            else:
                embed.description += f"`{day} {date.strftime('%d')}: {fmt} ({wind_speed}km/h wind speed)`\n"
        await ctx.send(embed=embed)

    @commands.command()
    async def botstats(self, ctx):
        """Views various statistics about me and my server."""
        embed = discord.Embed(title="Statistics")
        embed.set_footer(text=f'Created by {", ".join(ctx.bot.get_user(u).name for u in ctx.bot.config.OWNERS)}')
        get_total = await ctx.bot.redis.get("commands_used_total")
        get_today = await ctx.bot.redis.get(f"commands_used_{datetime.utcnow().strftime('%Y-%m-%d')}")
        cmds = collections.Counter(
            {d.decode(): int(v)
             for d, v in (await ctx.bot.redis.hgetall("command_totals")).items()
             if not d.startswith((b'jishaku', b'dev'))
             }).most_common(5)
        try:
            mem_info = self.proc.memory_full_info().uss / 1024 / 1024
        except psutil.AccessDenied:
            mem_info = self.proc.memory_info().rss / 1024 / 1024
        player_count = await ctx.bot.db.abyss.accounts.count_documents({})
        try:
            platform = R.findall(subprocess.run(['/usr/bin/lsb_release', '-d'],
                                                capture_output=True,
                                                check=False).stdout.decode('utf-8'))[0]
        except (IndexError, FileNotFoundError):
            platform = 'Non-linux system'
        embed.description = f"""> **Discord**
{len(ctx.bot.guilds)} Guilds
{len(set(ctx.bot.get_all_members()))} Members
{len(list(ctx.bot.get_all_channels()))} Channels
> **Abyss**
{len(ctx.bot.players.players)} players loaded
{player_count} total players
{len(ctx.bot.players.skill_cache)} skills
{len(ctx.bot.get_cog("BattleSystem").battles)} on-going battles
> **Command Stats**
{get_today.decode() if get_today else 0} commands used today
{get_total.decode()} commands used overall
> **Top commands**
{NL.join(f"{i + 1}. {c} ({v} uses)" for i, (c, v) in enumerate(cmds))}
> **Extra**
{mem_info:.1f} MB Memory Usage
{platform}
Python {'.'.join(map(str, sys.version_info[:3]))}
Online for {humanize.naturaldelta(ctx.bot.start_date - datetime.utcnow())}
"""
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def faq(self, ctx):
        """Brings up the Frequently Asked Questions."""
        embed = discord.Embed(title="Help")
        embed.description = "\n".join(f"${c} - **{c.short_doc}**"
                                      for c in self.faq.commands)  # pylint: disable=no-member
        await ctx.send(embed=embed)

    @faq.group()
    async def battle(self, ctx):
        """How do I fight?"""
        embed = discord.Embed(title="Help: Battle")
        embed.description = """Each battle will require you to fight against one or more opponents.
> __Losing the battle will not be tolerated.__
Each demon gets a turn. The fastest demon moves first, in order of your Agility stat.
There is an exception to this, however.
If you successfully **ambush** the enemy, you will be guaranteed to move first, then the enemies move in order of their agility.
If you are **ambushed** by the enemy, they will move in order of their agility before you get your turn.
Winning the battle will earn EXP, Credits and you may even obtain an item."""
        await ctx.send(embed=embed)

    @faq.command(aliases=['resistance'])
    async def resistances(self, ctx):
        """What are resistances and how do they affect battle?"""
        embed = discord.Embed(title="Help: Resistances")
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
Nulling an attack is as simple as it sounds. Does no damage.
Repelling an attack will deal 0.65x damage back to you, resistance inclusive.
(If you also repel those attacks, it is instead nullified)
Absorbsing an attack will heal the target by 0.5x the damage you would have dealt, resistance exclusive."""
        # Todo: exploiting all enemies' weaknesses (players only) grants bonuses.
        #  exploiting an enemy's weakness will knock them down,
        #  nullifying any evasion and increasing damage taken by 1.15x.
        #  dont obtain bonus turns for exploting the same enemy's weakness twice.
        await ctx.send(embed=embed)

    @faq.command(aliases=['skill'])
    async def skills(self, ctx):
        """What are all the skill categories?"""
        embed = discord.Embed(title="Help: Skills")
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
You can view `$help ailments` to view information about every ailment."""
        await ctx.send(embed=embed)

    @faq.command(aliases=['statuses', 'ailment'])
    async def ailments(self, ctx):
        """What is an ailment and what do they do?"""
        embed = discord.Embed(title="Help: Ailments")
        embed.set_footer(text="All ailments will heal themselves 2-7 turns after infliction.")
        embed.description = """In total, there are **12** ailments.
`Technical` is like a crit, but different. See `$help technicals`
> \N{FIRE} **Burn**   Technical: Wind/Nuclear
After you take your turn, you will take 6% of your max HP in damage.
> \N{SNOWFLAKE} **Freeze**   Technical: Physical/Nuclear
You are unable to move.
> \N{HIGH VOLTAGE SIGN} **Shock**   Technical: Physical/Nuclear
High chance of being immobilized. If you hit someone with your Attack, or they hit you with their Attack,
there is a medium chance of them being inflicted with Shock.
> \N{DIZZY SYMBOL} **Dizzy**   Technical: Any
Accuracy is severely reduced.
> \N{SLEEPING SYMBOL} **Sleep**   Technical: Physical
You are unable to move, however your HP and SP will recover by 8% every turn. You have a high chance of
waking if the enemy hits you with a physical attack.
> \N{SPEAKER WITH CANCELLATION STROKE} **Forget**   Technical: Psychokinetic
You will be unable to use your skills. You can still use Attack and Guard, and your passive skills will
still work.
> \N{WHITE QUESTION MARK ORNAMENT} **Confuse**   Technical: Psychokinetic
Chance to throw away an item/credits, do nothing ~~or use a random skill~~.
> \N{FACE SCREAMING IN FEAR} **Fear**   Technical: Psychokinetic
High chance of being immobilized. Low chance of running away from battle.
> \N{FEARFUL FACE} **Despair**   Technical: Psychokinetic
Unable to move, and you will lose 6% SP per turn.
> \N{POUTING FACE} **Rage**   Technical: Psychokinetic
Attack is doubled, but defense is halved. You will automatically use Attack instead of taking a turn.
> \N{PLAYING CARD BLACK JOKER} **Brainwash**   Technical: Psychokinetic
Chance to heal/buff the enemy.
> \N{HAMBURGER} **Hunger**   Technical: Gun
Greatly lowers your attack power."""
        await ctx.send(embed=embed)


def setup(bot):
    bot.help_command = commands.MinimalHelpCommand(verify_checks=False)
    bot.add_cog(Meta())
