import asyncio
import contextlib
import io
import logging
import os
import random
import traceback
from datetime import datetime, timedelta

import aiohttp
import aioredis
import discord
import motor.motor_asyncio
from discord.ext import commands

import config
from cogs.utils import i18n, formats
from cogs.utils.mapping import MapHandler
from cogs.utils.paginators import PaginationHandler, EmbedPaginator, BetterPaginator
from cogs.utils.player import Player

NL = '\n'


class BetterRotatingFileHandler(logging.FileHandler):
    def __init__(self, *args, **kwargs):
        self.init = datetime.utcnow().strftime("%d-%m-%Y")
        super().__init__(*args, **kwargs)

    def _open(self):
        return open(self.baseFilename+self.init, 'a', encoding='utf-8')

    def emit(self, record):
        strf = datetime.utcnow().strftime("%d-%m-%Y")
        if strf != self.init:
            self.init = strf
            self.close()

        if self.stream is None:
            self.stream = self._open()

        if os.path.isfile("logs/"+self.baseFilename+(datetime.utcnow()-timedelta(days=7)).strftime("%d-%m-%Y")):
            os.remove("logs/"+self.baseFilename+(datetime.utcnow()-timedelta(days=7)).strftime("%d-%m-%Y"))

        return logging.StreamHandler.emit(self, record)


def do_next_script(msg, author=None):
    author = author or msg.author

    def check(r, u):
        return u.id == author.id and \
            r.message.id == msg.id and \
            str(r.emoji) == '\u25b6'
    return check


def get_logger(name):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    "uncomment the above line to enable debug logging"

    stream = logging.StreamHandler()

    stream.setFormatter(logging.Formatter("[{asctime} {name}/{levelname}]: {message}", "%H:%M:%S", "{"))

    log.handlers = [
        stream,
        BetterRotatingFileHandler("logs/log", encoding="utf-8")
    ]
    return log


if not os.path.isdir("music"):
    os.mkdir("music")
if not os.path.isdir("logs"):
    os.mkdir("logs")


class ContextSoWeDontGetBannedBy403(commands.Context):
    async def send(self, content=None, *, embed=None, file=None, files=None, tts=False, **kwargs):
        if not self.guild.me.permissions_in(self.channel).send_messages:
            return
        if embed and not self.guild.me.permissions_in(self.channel).embed_links:
            return
        elif (file or files) and not self.guild.me.permissions_in(self.channel).attach_files:
            return
        elif tts and not self.guild.me.permissions_in(self.channel).send_tts_messages:
            return
        return await super().send(content, embed=embed, file=file, files=files, tts=tts, **kwargs)

    async def send_as_paginator(self, content=None, *, embeds=None, destination=None, codeblock=False):
        if embeds:  # embed has higher priority over content
            pg = EmbedPaginator()  # also `codeblock` has no effect with embeds
            for e in embeds:
                pg.add_page(e)
            await PaginationHandler(self.bot, pg, send_as="embed", owner=self.author, no_help=True).start(destination or self)
        elif content:
            pg = BetterPaginator(prefix='```' if codeblock else None, suffix='```' if codeblock else None, max_size=1985)
            for l in content.split("\n"):
                pg.add_line(l)
            await PaginationHandler(self.bot, pg, no_help=True, owner=self.author).start(destination or self)
        else:
            raise TypeError("missing arguments")

    async def confirm(self, message, waiter=None):
        waiter = waiter or self.author
        m = await self.send(message)
        await asyncio.gather(m.add_reaction(self.bot.tick_yes), m.add_reaction(self.bot.tick_no))
        try:
            p = await self.bot.wait_for('raw_reaction_add', check=lambda p: str(p.emoji) in (self.bot.tick_yes, self.bot.tick_no)
                                        and p.user_id == waiter.id and p.message_id == m.id,
                                        timeout=60)
        except asyncio.TimeoutError:
            return False
        else:
            return str(p.emoji) == self.bot.tick_yes
        finally:
            await m.delete()


class Abyss(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.pipe = kwargs.pop('pipe')
        self.cluster_name = kwargs.pop('cluster_name')
        super().__init__(commands.when_mentioned_or("$"), **kwargs)
        self.remove_command("help")  # fuck you danny
        self.prepared = asyncio.Event()
        # `prepared` is to make sure the bot has loaded the database and such

        self.db = motor.motor_asyncio.AsyncIOMotorClient(
            username=config.MONGODB_USER, password=config.MONGODB_PASS, authSource=config.MONGODB_DBSE)
        self.redis = None
        self.session = aiohttp.ClientSession()

        self.tick_yes = config.TICK_YES
        self.tick_no = config.TICK_NO
        self.debug_hook = config.DEBUG_WEBHOOK
        self.unload_tasks = {}
        self.config = config
        self.start_date = None
        self.map_handler = MapHandler(self)
        self.item_cache = None

        logger = logging.getLogger('discord')
        # log.setLevel(logging.DEBUG)
        handler = BetterRotatingFileHandler(f'logs/{self.cluster_name}-discord.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)

        self.log = get_logger(f'Abyss#{self.cluster_name}')

        self.add_check(self.global_check)
        # self.before_invoke(self.before_invoke_handler)
        self.prepare_extensions()
        self.run()

    async def on_command_error(self, *__, **_):
        pass

    @property
    def description(self):
        return random.choice([
            "> ~~Stuck? Try using `$story` to progress.~~",
            "> Confused? Try `$help` for more information.",
            "> ~~Bored? Try your hand at an online battle.~~",
            "> If you have spare stat points, you can still use `$levelup` to use them.",
            "> Join the support server for updates and announcements: <https://discord.gg/hkweDCD>",
            "> ~~During scripts, press the stop button to save your progress. Using `$story` will continue where you left off.~~",
            "> Join a voice channel to experience immersive Background Music!",
            "corn"
        ])

    @description.setter
    def description(self, value):
        pass

    @property
    def players(self):
        return self.get_cog("Players")

    @property
    def tree(self):
        return self.get_cog("SkillTreeCog")

    async def before_invoke_handler(self, ctx):
        if not self.players:
            ctx.player = None
            return
        try:
            ctx.player = self.players.players[ctx.author.id]
        except KeyError:
            data = await self.db.abyss.accounts.find_one({"owner": ctx.author.id})
            if not data:
                ctx.player = None
                return
            ctx.player = self.players.players[ctx.author.id] = player = Player(**data)
            player._populate_skills(self)
            if player._active_leaf is not None:
                key, _ = player._active_leaf.split(':')
                branch = self.tree.skill_tree[key].copy()
                branch[player._active_leaf]['name'] = player._active_leaf
                player.leaf = branch[player._active_leaf]

    async def wait_for_close(self):
        for cog, task in self.unload_tasks.items():
            try:
                await asyncio.wait_for(task, timeout=30)
            except asyncio.TimeoutError:
                self.log.warning(f"{cog!r} unload task did not finish in time.")
                task.cancel()

    # noinspection PyMethodMayBeStatic
    async def global_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    # noinspection PyShadowingNames
    async def confirm(self, msg, user):
        rs = (str(self.tick_yes), str(self.tick_no))
        for r in rs:
            await msg.add_reaction(r)
        try:
            r, u = await self.wait_for('reaction_add', check=lambda r, u: str(r.emoji) in rs and u.id == user.id and
                                       r.message.id == msg.id, timeout=60)
        except asyncio.TimeoutError:
            return False
        else:
            if str(r.emoji) == rs[0]:
                return True
            return False
        finally:
            with contextlib.suppress(discord.Forbidden):
                await msg.clear_reactions()

    # noinspection PyTypeChecker
    async def _send_error(self, message):

        # Hey, if you've stumbled upon this, you might be asking:
        # "Xua, why are you instantiating your own DMChannel?"
        # My answer: no idea
        # I could save the stupidness and just use get_user.dm_channel
        # But what if an error happens pre on_ready?
        # The user might not be cached.

        # Of course, this wouldn't technically matter if the webhook exists,
        # but webhooks are optional so :rooShrug:

        if isinstance(config.DEBUG_WEBHOOK, str):
            if config.DEBUG_WEBHOOK:
                self.debug_hook = discord.Webhook.from_url(config.DEBUG_WEBHOOK,
                                                           adapter=discord.AsyncWebhookAdapter(self.session))
            else:
                data = await self.http.start_private_message(config.OWNERS[0])
                self.debug_hook = discord.DMChannel(me=self.user, state=self._connection, data=data)

        if isinstance(message, str) and len(message) > 2000:
            async with self.session.post("https://mystb.in/documents", data=message.encode()) as post:
                if post.status == 200:
                    data = await post.json()
                    return await self._send_error(f"Error too long: https://mystb.in/{data['key']}")

                # no mystbin, fallback to files
                f = io.BytesIO(message.encode())
                return await self._send_error(discord.File(f, "error.txt"))
        elif isinstance(message, discord.File):
            await self.debug_hook.send(file=message)
        else:
            await self.debug_hook.send(message)

    def send_error(self, message):
        return self.loop.create_task(self._send_error(message))

    def prepare_extensions(self):
        try:
            self.load_extension("jishaku")
        except commands.ExtensionNotFound:
            pass

        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                file = file[:-3]

            if file in config.COG_BLACKLIST:
                continue

            filename = "cogs." + file

            try:
                self.load_extension(filename)
            except Exception as e:
                self.log.warning(f"Could not load ext `{filename}`.")
                self.send_error(f"Could not load ext `{filename}`\n```py\n{formats.format_exc(e)}\n````")

    async def on_ready(self):
        if self.prepared.is_set():
            await self.change_presence(activity=discord.Game(name="$cmds"))
            return

        try:
            await self.db.abyss.accounts.find_one({})
            self.log.info("MongoDB connection success")
            # dummy query to ensure the db is connected
        except Exception as e:
            self.log.error("COULD NOT CONNECT TO MONGODB DATABASE.")
            self.log.error("This could lead to fatal errors. Falling back prefixes to mentions only.")
            self.send_error(f"FAILED TO CONNECT TO MONGODB\n```py\n{formats.format_exc(e)}\n```")
            return

        try:
            self.redis = await aioredis.create_redis_pool(**config.REDIS)
            self.log.info("Redis connection succeeded")
        except Exception as e:
            self.log.error("couldnt connect to redis")
            self.send_error(F"failed to connect to redis\n```py\n{formats.format_exc(e)}\n```")

        self.prepared.set()
        self.start_date = datetime.utcnow()
        self.log.warning("Successfully loaded.")
        await self.change_presence(activity=discord.Game(name="$cmds"))
        self.pipe.send(1)
        self.pipe.close()

    async def on_message(self, message):
        if message.author.bot:
            return

        current = await self.redis.get(f"locale:{message.author.id}")
        if not current:
            current = i18n.LOCALE_DEFAULT.encode()
        i18n.current_locale.set(current.decode())

        await self.process_commands(message)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or ContextSoWeDontGetBannedBy403)

    async def on_message_edit(self, before, after):
        if after.author.bot or before.content == after.content:
            return

        current = await self.redis.get(f"locale:{before.author.id}")
        if not current:
            current = i18n.LOCALE_DEFAULT.encode()
        i18n.current_locale.set(current.decode())
        await self.process_commands(after)

    def run(self):
        super().run(config.TOKEN)

    async def close(self):
        self.log.info("Shutting down")
        self.dispatch("logout")
        await self.wait_for_close()
        self.db.close()
        await self.session.close()
        await super().close()

    async def on_error(self, event, *args, **kwargs):
        if not self.prepared.is_set():
            return
        to = f""">>> Error occured in event `{event}`
Arguments: {args}
KW Arguments: {kwargs}
```py
{traceback.format_exc()}
```"""
        await self.send_error(to)
