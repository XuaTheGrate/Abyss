import asyncio
from datetime import time

from discord.ext import commands, tasks

from cogs.utils import formats


class Bullshit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.midnight_helper = tasks.loop(time=time(0, 0, 0), loop=bot.loop)(self.midnight_helper)
        self.midnight_helper.before_loop(self.pre_midnight_loop_start)
        self.midnight_helper.after_loop(self.post_midnight_loop_complete)
        self.midnight_helper.start()

    def cog_unload(self):
        self.midnight_helper.stop()

    async def midnight_helper(self):
        self.bot.log.info("we reached midnight")
        await self.bot.prepared.wait()
        for p in self.bot.players.players.values():
            p.sp_used = 0
        if self.bot.cluster_name not in ('Alpha', 'beta'):  # lowercase beta indicates testing bot, uppercase is cluster 2
            return await asyncio.sleep(1.5)
        cur = None
        keys = set()
        while cur != 0:
            cur, k = await self.bot.redis.scan(cur or 0, match='p_sp_used*', count=1000)
            keys.update(k)
        for key in keys:
            await self.bot.redis.delete(key)
        self.bot.log.info(f"reset sp of {len(keys)} players")
        cur = None
        keys.clear()
        while cur != 0:
            cur, k = await self.bot.redis.scan(cur or 0, match='treasures_found:*', count=1000)
            keys.update(k)
        for key in keys:
            await self.bot.redis.delete(key)
        self.bot.log.info(f'reset treasures of {len(keys)} players')
        await asyncio.sleep(1.5)

    async def pre_midnight_loop_start(self):
        self.bot.log.info("midnight loop: hello world")

    async def post_midnight_loop_complete(self):
        self.bot.log.error("loop stopped")
        if not self.midnight_helper.failed():
            return
        exc = self.midnight_helper.exception()
        if exc:
            self.bot.send_error(f'>>> Error occured in midnight_helper task\n```py\n{formats.format_exc(exc)}\n```')


def setup(bot):
    bot.add_cog(Bullshit(bot))
