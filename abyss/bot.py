import asyncio
import logging
import sys
from types import SimpleNamespace

import aiohttp
import aioredis
import discord
import toml
from discord.ext import commands
from rethinkdb import r

from . import logs
logs.inject()
del logs

r.set_loop_type("asyncio")


class Abyss(commands.Bot):
    def __init__(self, debug=False):
        self.debug = debug
        self.log = logging.getLogger("Abyss")
        # self.log.setLevel(logging.DEBUG if debug else logging.INFO)
        self.log.setLevel(logging.INFO)
        self.log.info("Hello, world!")
        with open("config.toml") as f:
            cfg = toml.load(f)
            self.config = SimpleNamespace(**cfg['beta' if debug else 'production'], **cfg['global'])
            self.log.debug("Applied config %r", "beta" if debug else "production")
        super().__init__(command_prefix=self.config.prefix, activity=discord.Game(name=self.config.prefix + 'help'))

        self.__rethinkdb_connection = None
        self.redis = None
        self.session = None

    async def on_ready(self):
        self.log.info("Logged in as %s (%s)", self.user, self.user.id)

    def recursively_add_better_cooldowns(self, command):
        cooldown = getattr(command.callback, '_better_cooldown', None)
        bucket = getattr(command.callback, '_better_cooldown_bucket', None)
        command._better_cooldown = cooldown
        command._better_cooldown_bucket = bucket
        self.log.debug("Applied command %s", command)
        if isinstance(command, commands.Group):
            for command in command.commands:
                self.recursively_add_better_cooldowns(command)

    def add_command(self, command):
        self.recursively_add_better_cooldowns(command)
        return super().add_command(command)

    async def invoke(self, ctx):
        if ctx.command is not None:
            # noinspection PyProtectedMember
            cooldown = ctx.command._better_cooldown
            if cooldown is not None:
                try:
                    await cooldown(ctx)
                except commands.CommandOnCooldown as e:
                    self.dispatch("command_error", ctx, e)
                    return
        return await super().invoke(ctx)

    async def run_setup(self):
        self.__rethinkdb_connection = c = await r.connect(
            host=self.config.rethinkdb['host'], port=self.config.rethinkdb['port'],
            user=self.config.rethinkdb['user'], password=self.config.rethinkdb['password'])
        c.use(self.config.rethinkdb['database'])
        c.repl()
        self.log.info("RethinkDB connection successful")
        self.redis = await aioredis.create_redis_pool('redis://:{password}@{host}:{port}/{database}'.format(
            **self.config.redis))
        self.log.info("Redis connection successful")
        self.session = aiohttp.ClientSession()

    def prepare_extensions(self):
        from glob import glob

        try:
            self.load_extension("jishaku")
            self.log.info("Jishaku was found and loaded")
        except commands.ExtensionNotFound:
            self.log.info("Jishaku was not found")

        for file in glob("abyss/extensions/*.py"):
            transformed = file[:-3].replace('\\', '.').replace('/', '.')
            if transformed == 'abyss.extensions.test':
                continue
            try:
                self.load_extension(transformed)
                self.log.info("Loaded extension %s", transformed)
            except Exception as e:
                self.log.error("Failed to load extension %s", transformed)
                import traceback
                traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

    async def close(self):
        self.log.info("Shutting down...")
        await super().close()
        self.log.debug("a")
        await self.session.close()
        self.log.debug("b")
        try:
            await asyncio.wait_for(self.__rethinkdb_connection.close(), timeout=1)
        except asyncio.TimeoutError:
            pass
        self.log.debug("c")
        self.redis.close()
        await self.redis.wait_closed()
        self.log.debug("d")
        self.log.debug("Goodbye")

    def run(self):
        super().run(self.config.token)
