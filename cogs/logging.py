import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from discord.ext import commands

NL = '\n'
NNL = '\\n'

log = logging.getLogger("Abyss")
log.handlers.clear()
hdlr = TimedRotatingFileHandler("Abyss.log", "d", utc=True)
hdlr.setFormatter(logging.Formatter(fmt=""))
log.addHandler(hdlr)


class CommandLogger(commands.Cog):
    @commands.Cog.listener()
    async def on_command(self, ctx):
        log.info(
            f"[{datetime.utcnow().strftime('%Y-%m-%d@H:%M:%S')}]"
            f"[{ctx.guild.id} {ctx.guild}] {ctx.author.id} {ctx.author}: "
            f"{ctx.message.clean_content.replace(NL, NNL)}"
        )


def setup(bot):
    bot.add_cog(CommandLogger())
