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

NL = '\n'


class BetterRotatingFileHandler(logging.FileHandler):
    def __init__(self, *args, **kwargs):
        self.init = datetime.utcnow().strftime("%d-%m-%Y")
        self.stream = None
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

    def check(reaction, user):
        return user.id == author.id and \
               reaction.message.id == msg.id and \
               str(reaction.emoji) == '\u25b6'
    return check


def get_logger(name):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    # uncomment the above line to enable debug logging

    stream = logging.StreamHandler()

    stream.setFormatter(logging.Formatter("[{asctime} {name}/{levelname}]: {message}", "%H:%M:%S", "{"))

    log.handlers = [
        stream,
        BetterRotatingFileHandler(f"logs/{name}", encoding="utf-8")
    ]
    return log


if not os.path.isdir("music"):
    os.mkdir("music")
if not os.path.isdir("logs"):
    os.mkdir("logs")


class ContextSoWeDontGetBannedBy403(commands.Context):
    async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
        if not self.guild:
            return await super().send(content, embed=embed, file=file, files=files,
                                      tts=tts, delete_after=delete_after, nonce=nonce)
        if not self.guild.me.permissions_in(self.channel).send_messages:
            self.bot.log.info(
                "Didn't have permissions to send messages in #{0.name} ({0} {0.guild.id}".format(self.channel))
            return
        if embed and not self.guild.me.permissions_in(self.channel).embed_links:
            self.bot.log.info(
                "Didn't have permissions to embed links in #{0.name} ({0} {0.guild.id}".format(self.channel))
            return
        if (file or files) and not self.guild.me.permissions_in(self.channel).attach_files:
            self.bot.log.info(
                "Didn't have permissions to attach files in #{0.name} ({0} {0.guild.id}".format(self.channel))
            return
        if tts and not self.guild.me.permissions_in(self.channel).send_tts_messages:
            self.bot.log.info(
                "Didn't have permissions to send TTS messages in #{0.name} ({0} {0.guild.id}".format(self.channel))
            return
        return await super().send(content, embed=embed, file=file, files=files,
                                  tts=tts, delete_after=delete_after, nonce=nonce)

    async def send_as_paginator(self, content=None, *, embeds=None, destination=None, codeblock=False):
        if embeds:  # embed has higher priority over content
            paginator = EmbedPaginator()  # also `codeblock` has no effect with embeds
            for embed in embeds:
                paginator.add_page(embed)
            await PaginationHandler(self.bot, paginator, send_as="embed", owner=self.author, no_help=True
                                    ).start(destination or self)
            return
        if content:
            paginator = BetterPaginator(prefix='```' if codeblock else None, suffix='```' if codeblock else None,
                                        max_size=1985)
            for line in content.split("\n"):
                paginator.add_line(line)
            await PaginationHandler(self.bot, paginator, no_help=True, owner=self.author).start(destination or self)
            return
        raise TypeError("missing arguments")

    async def confirm(self, message, *, waiter=None, timeout=60):
        waiter = waiter or self.author
        msg = await self.send(message)
        await asyncio.gather(msg.add_reaction(self.bot.tick_yes), msg.add_reaction(self.bot.tick_no))
        try:
            payload = await self.bot.wait_for('raw_reaction_add', check=lambda p: str(p.emoji) in (self.bot.tick_yes,
                                                                                                   self.bot.tick_no)
                                              and p.user_id == waiter.id and p.message_id == msg.id,
                                              timeout=timeout)
        except asyncio.TimeoutError:
            return False
        else:
            return str(payload.emoji) == self.bot.tick_yes
        finally:
            await msg.delete()


class Abyss(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        self.pipe = kwargs.pop('pipe', None)
        self.cluster_name = kwargs.pop('cluster_name', 'beta')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if self.cluster_name == 'beta':
            super().__init__('beta$ ', **kwargs, loop=loop, activity=discord.Game(name='Testing shit'))
        else:
            super().__init__(commands.when_mentioned_or("$"), **kwargs, loop=loop,
                             activity=discord.Game(name="$help"))
        self.remove_command("help")  # fuck you danny
        self.prepared = asyncio.Event()
        # `prepared` is to make sure the bot has loaded the database and such

        self.eval_wait = False

        if self.cluster_name == 'beta':
            self.db = motor.motor_asyncio.AsyncIOMotorClient(host=config.MONGODB_HOST, io_loop=self.loop)
        else:
            self.db = motor.motor_asyncio.AsyncIOMotorClient(  # pylint: disable=invalid-name
                host=config.MONGODB_HOST,
                username=config.MONGODB_USER,
                password=config.MONGODB_PASS,
                authSource=config.MONGODB_DBSE,
                io_loop=self.loop
            )
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
        handler = BetterRotatingFileHandler(f'logs/Abyss-{self.cluster_name}-discord.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)

        self.log = get_logger(f'Abyss-{self.cluster_name}')

        self.add_check(self.global_check)
        # self.before_invoke(self.before_invoke_handler)
        self.prepare_extensions()
        self.run(config.TOKEN)

    async def on_command_error(self, context, exception, *, force=False):
        pass

    async def is_owner(self, user):
        return user.id in config.OWNERS

    @property
    def description(self):
        return random.choice([
            # "~~Stuck? Try using `$story` to progress.~~",
            "Confused? Try `$faq` for more information.",
            # "~~Bored? Try your hand at an online battle.~~",
            "If you have spare stat points, you can still use `$levelup` to use them.",
            "Join the support server for updates and announcements via `$support`",
            # "~~During scripts, press the stop button to save your progress. Using `$story`"
            # "will continue where you left off.~~",
            # "Join a voice channel to experience immersive Background Music!",
            "You can check all the recipes you can currently craft via `$craft list`.",
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

    async def wait_for_close(self):
        for cog, task in self.unload_tasks.items():
            try:
                await asyncio.wait_for(task, timeout=30)
            except asyncio.TimeoutError:
                self.log.warning(f"{cog!r} unload task did not finish in time.")
                task.cancel()

    async def global_check(self, ctx):
        if not ctx.guild and ctx.author.id not in config.OWNERS:
            raise commands.NoPrivateMessage
        if self.cluster_name == 'beta' and ctx.author.id not in config.OWNERS:
            raise commands.NotOwner
        return True
    
    def get_command(self, name):
        # patch this to support commands prefixed with space
        c = self.all_commands.get(name)
        if c:
            return c
        return super().get_command(name)

    # noinspection PyShadowingNames
    async def confirm(self, msg, user):
        reactions = (str(self.tick_yes), str(self.tick_no))
        for react in reactions:
            await msg.add_reaction(react)
        try:
            react, user = await self.wait_for('reaction_add',
                                              check=lambda r, u: str(r.emoji) in reactions and u.id == user.id and
                                              r.message.id == msg.id, timeout=60)
        except asyncio.TimeoutError:
            return False
        else:
            if str(react.emoji) == reactions[0]:
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
                file = io.BytesIO(message.encode())
                return await self._send_error(discord.File(file, "error.txt"))
        elif isinstance(message, discord.File):
            await self.debug_hook.send(message)
        else:
            await self.debug_hook.send(message)

    def send_error(self, message):
        return asyncio.run_coroutine_threadsafe(self._send_error(message), self.loop)

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

            if filename == "cogs.dbl" and self.cluster_name != "Alpha":
                continue  # no loady on any other clusters

            try:
                self.load_extension(filename)
            except Exception as exc:
                self.log.warning(f"Could not load ext `{filename}`.")
                self.send_error(f"Could not load ext `{filename}`\n```py\n{formats.format_exc(exc)}\n````")

    async def on_ready(self):
        if self.prepared.is_set():
            # await self.change_presence(activity=discord.Game(name="$help"))
            return

        try:
            await self.db.abyss.accounts.find_one({})
            self.log.info("MongoDB connection success")
            # dummy query to ensure the db is connected
        except Exception as exc:
            self.log.error("COULD NOT CONNECT TO MONGODB DATABASE.")
            self.log.error("This could lead to fatal errors. Falling back prefixes to mentions only.")
            self.send_error(f"FAILED TO CONNECT TO MONGODB\n```py\n{formats.format_exc(exc)}\n```")
            return

        try:
            self.redis = await aioredis.create_redis_pool(**config.REDIS, loop=self.loop)
            self.log.info("Redis connection succeeded")
        except Exception as exc:
            self.log.error("couldnt connect to redis")
            self.send_error(F"failed to connect to redis\n```py\n{formats.format_exc(exc)}\n```")

        if self.cluster_name == "Alpha":
            self.log.info("start: hello world")

        self.prepared.set()
        self.start_date = datetime.utcnow()
        self.log.warning("Successfully loaded.")
        # await self.change_presence(activity=discord.Game(name="$help"))
        if self.pipe:
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

    async def close(self):
        self.log.info("Shutting down")
        self.dispatch("logout")
        await self.wait_for_close()
        self.db.close()
        await self.session.close()
        await super().close()

    async def on_error(self, event_method, *args, **kwargs):
        if not self.prepared.is_set():
            return
        message = f""">>> Error occured in event `{event_method}`
Arguments: {args}
KW Arguments: {kwargs}
```py
{traceback.format_exc()}
```"""
        self.send_error(message)
