import logging
from datetime import datetime

from discord.ext import commands

NL = '\n'
NNL = '\\n'


class BetterRotatingFileHandler(logging.FileHandler):
    def __init__(self, *args, **kwargs):
        self.init = datetime.utcnow().strftime("%d-%m-%Y")
        super().__init__(*args, **kwargs)

    def _open(self):
        return open(self.baseFilename + self.init, 'a', encoding='utf-8')

    def emit(self, record):
        strf = datetime.utcnow().strftime("%d-%m-%Y")
        if strf != self.init:
            self.init = strf
            self.close()

        if self.stream is None:
            self.stream = self._open()

        return logging.StreamHandler.emit(self, record)


log = logging.getLogger("Abyss")
log.setLevel(logging.DEBUG)
log.handlers.clear()
hdlr = BetterRotatingFileHandler("logs/Abyss.log")
hdlr.setFormatter(logging.Formatter(fmt=""))
log.addHandler(hdlr)


class CommandLogger(commands.Cog):
    @commands.Cog.listener()
    async def on_command(self, ctx):
        if not ctx.guild:
            return
        log.info(
            f"[{datetime.utcnow().strftime('%Y-%m-%d@%H:%M:%S')}]"
            f"[{ctx.guild.id} {ctx.guild}] {ctx.author.id} {ctx.author}: "
            f"{ctx.message.clean_content.replace(NL, NNL)}"
        )
        if ctx.command.qualified_name.startswith(('jishaku', 'dev', '_')):
            return
        await ctx.bot.redis.incr('commands_used_total')
        await ctx.bot.redis.incr(f'commands_used_{datetime.utcnow().strftime("%Y-%m-%d")}')
        if ctx.command.root_parent:
            name = ctx.command.root_parent.qualified_name
        else:
            name = ctx.command.qualified_name
        await ctx.bot.redis.hincrby('command_totals', name, 1)

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot or not msg.guild:
            return
        if (
            msg.guild.me.permissions_in(msg.channel).send_messages and
            msg.guild.me.permissions_in(msg.channel).embed_links
        ) and str(msg.guild.me) in msg.clean_content:
            await msg.channel.send(
                "https://cdn.discordapp.com/attachments/561390634863165450/607731350732144641/993ec8f-1.jpg")


def setup(bot):
    bot.add_cog(CommandLogger())
