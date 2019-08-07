import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from discord.ext import commands

NL = '\n'
NNL = '\\n'

log = logging.getLogger("Abyss")
log.setLevel(logging.DEBUG)
log.handlers.clear()
hdlr = TimedRotatingFileHandler("logs/Abyss.log", "d", utc=True)
hdlr.setFormatter(logging.Formatter(fmt=""))
log.addHandler(hdlr)


class CommandLogger(commands.Cog):
    @commands.Cog.listener()
    async def on_command(self, ctx):
        log.info(
            f"[{datetime.utcnow().strftime('%Y-%m-%d@%H:%M:%S')}]"
            f"[{ctx.guild.id} {ctx.guild}] {ctx.author.id} {ctx.author}: "
            f"{ctx.message.clean_content.replace(NL, NNL)}"
        )
        await ctx.bot.redis.incr('commands_used_total')
        await ctx.bot.redis.incr(f'commands_used_{datetime.utcnow().strftime("%Y-%m-%d")}')
        await ctx.bot.redis.hincrby('command_totals', ctx.command.qualified_name, 1)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot:
            return
        if msg.guild.me.mentioned_in(msg):
            await msg.channel.send("https://cdn.discordapp.com/attachments/561390634863165450/607731350732144641/993ec8f-1.jpg")


def setup(bot):
    bot.add_cog(CommandLogger())
