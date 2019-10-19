import asyncio

from discord.ext import commands

import config


class DBLCrap(commands.Cog, name="DBL"):
    def __init__(self, bot):
        assert bot.cluster_name == 'Alpha'
        self.bot = bot
        self.task = self.bot.loop.create_task(self.tasker())

    def cog_unload(self):
        self.task.cancel()

    async def tasker(self):
        await self.bot.wait_until_ready()
        while await asyncio.sleep(86400, True):
            async with self.bot.session.post(f"https://top.gg/api/bots/{self.bot.user.id}/stats",
                                             data={"server_count": f"{len(self.bot.guilds)}"},
                                             headers={"Authorization": config.DBL_KEY}) as post:
                if 200 <= post.status < 400:  # OK
                    self.bot.log.info(f"Updated DBL server count with {len(self.bot.guilds)} servers.")
                else:
                    try:
                        data = await post.json()
                    except Exception:
                        data = None
                    self.bot.send_error(f">>> Error during DBL task\n{post.status}: {post.reason}\n`{data}`")
                    return


def setup(bot):
    bot.add_cog(DBLCrap(bot))
