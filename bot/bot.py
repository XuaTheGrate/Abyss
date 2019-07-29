import asyncio
import contextlib
import io
import os
import traceback
from collections import defaultdict
from logging.handlers import TimedRotatingFileHandler

import aiohttp
import aioredis
import discord
from discord.ext import commands
import motor.motor_asyncio

import config
from cogs import utils
from cogs.utils import i18n
from cogs.utils.player import Player

import logging

NL = '\n'

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


def do_next_script(msg, author=None):
    author = author or msg.author

    def check(r, u):
        return u.id == author.id and \
            r.message.id == msg.id and \
            str(r.emoji) == '\u25b6'
    return check


def get_logger():
    """Prepares the logging system.

    Returns
    -------
    :class:`logging.Logger`
        The base logger.
    """
    log = logging.getLogger(__name__)
    # log.setLevel(logging.DEBUG)
    "uncomment the above line to enable debug logging"

    stream = logging.StreamHandler()

    stream.setFormatter(logging.Formatter("[{asctime} {name}/{levelname}]: {message}", "%H:%M:%S", "{"))

    log.handlers = [
        TimedRotatingFileHandler("logs/log", "d", encoding="utf-8")
    ]

    return log


PREFIXES = defaultdict(set)
CONFIG_NEW = {
    "guild": None,              # guild id
    "prefixes": config.PREFIX,  # list of prefixes
    "autoMessages": True,       # toggle automatic messages in the entire guild
    "ignoreChannels": [],       # prevent automatic messages in these channels
    "blacklist": []             # ignore commands from these users
}


class Abyss(commands.Bot):
    """Hi, this is my alternate adventure bot.

    Attributes
    ----------
    prepared: :class:`asyncio.Event`
        Set when the database and such is connected successfully.
    logger: :class:`logging.Logger`
        The logger used for logging stuff.
    db: :class:`motor.motor_asyncio.AsyncIOMotorClient`
        The MongoDB database for storing shit.
    redis: :class:`aioredis.ConnectionsPool`
        The Redis connection.
    session: :class:`aiohttp.ClientSession`
        Session for internet getting stuff.
    tick_yes: :class:`str`
        ✅
    tick_no: :class:`str`
        ❎
    debug_hook: Optional[:class:`str`, :class:`discord.Webhook`, :class:`discord.DMChannel`]
        If this is a :class:`str`, it is an unprepared webhook for sending messages to.
        If this is either a :class:`discord.Webhook`, or :class:`discord.DMChannel`, it
            is a prepared webhook for sending errors to.
    """
    def __init__(self):
        super().__init__(self.prefix)
        self.prepared = asyncio.Event()
        # `prepared` is to make sure the bot has loaded the database and such

        self.logger = get_logger()

        self.db = motor.motor_asyncio.AsyncIOMotorClient(
            username=config.MONGODB_USER, password=config.MONGODB_PASS, authSource=config.MONGODB_DBSE)
        self.redis = None
        self.session = aiohttp.ClientSession()

        self.tick_yes = config.TICK_YES
        self.tick_no = config.TICK_NO
        self.debug_hook = config.DEBUG_WEBHOOK
        self.unload_tasks = {}

        self.help_command = commands.MinimalHelpCommand(verify_checks=False)

        self.add_check(self.global_check)
        self.before_invoke(self.before_invoke_handler)
        self.prepare_extensions()

    @property
    def description(self):
        return _("> Stuck? Try using `$story` to progress.")

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
        """Helper function that waits for all cogs to finish unloading."""
        for cog, task in self.unload_tasks.items():
            try:
                await asyncio.wait_for(task, timeout=30)
            except asyncio.TimeoutError:
                self.logger.warning(f"{cog!r} unload task did not finish in time.")
                task.cancel()

    async def global_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

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
        """If a webhook is not specified, falls back to the first id in `config.OWNERS` and DMs the error.
        If the message is > 2000 characters, will attempt to upload to mystb.in and send the URL.
        If uploading to mystb.in failed somehow, falls back to sending an error.txt file.

        Parameters
        -----------
        message: :class:`str`
            The message to send.

        Returns
        -------
        :class:`asyncio.Task`
            The task for sending the message. Awaitable, so you can pause until its sent."""
        return self.loop.create_task(self._send_error(message))

    async def get_guild_config(self, guild):
        """Returns a dict containing all the guild specific configuration.
        If no guild data was found in the MongoDB database, a new one is
        cloned from the base.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to get data from.

        Returns
        -------
        :class:`dict`
            The dict configuration.
        """
        data = await self.db.abyss.guildconfig.find_one({"guild": guild.id})
        if not data:
            data = CONFIG_NEW.copy()
            data['guild'] = guild.id
            await self.db.abyss.guildconfig.insert_one(data)
        return data

    async def prefix(self, bot, message):
        """Gets the prefix for the bot/guild/whatever.
        If no guild is present, the returned prefix is an empty string.

        Parameters
        ----------
        bot: :class:`AdventureTwo`
            It's a me.
        message: :class:`discord.Message`
            The message to determine how to get the prefix.

        Returns
        -------
        Union[:class:`str`, List[:class:`str`]]
            The prefix(es) for the guild."""
        if not self.prepared.is_set():
            return commands.when_mentioned(bot, message)

        # prefix-less in DMs
        if not message.guild:
            return ""

        return await self.prefixes_for(message.guild)

    async def prefixes_for(self, guild):
        """Returns a set of valid prefixes for the guild.

        .. note::
            If you are wondering why I'm using a set to begin with,
            this is to prevent duplicate prefixes.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to get the prefixes for.

        Returns
        -------
        List[:class:`str`]
            The prefixes for that guild."""
        if not self.prepared.is_set():
            return

        if not PREFIXES[guild.id]:
            cfg = await self.get_guild_config(guild)
            PREFIXES[guild.id] = set(cfg['prefixes'])

        return list(PREFIXES[guild.id] | {f"<@{self.user.id}> ", f"<@!{self.user.id}> "})

    async def add_prefixes(self, guild, *prefix):
        """Appends a prefix to the allowed prefixes.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to add prefixes for.
        *prefix: :class:`str`
            Prefixes to add for that guild.

        Raises
        ------
        RuntimeError
            The bot has not finished loading.
        """
        if not self.prepared.is_set():
            raise RuntimeError

        PREFIXES[guild.id].update([p.strip() for p in prefix])

    async def rem_prefixes(self, guild, *prefix):
        """Removes a prefix from the list of prefixes.

        .. note::
            You cannot remove the @mentions.

        Parameters
        ----------
        guild: :class:`discord.Guild`
            The guild to remove prefixes from.
        *prefix: :class:`str`
            The list of prefixes to remove.

        Raises
        ------
        RuntimeError
            The bot has not finished loading."""
        if not self.prepared.is_set():
            raise RuntimeError

        PREFIXES[guild.id].difference_update(prefix)

    def prepare_extensions(self):
        """Loads every cog possible in ./cogs"""
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
                self.logger.warning(f"Could not load ext `{filename}`.")
                self.send_error(f"Could not load ext `{filename}`\n```py\n{utils.format_exc(e)}\n````")

    async def on_ready(self):
        if self.prepared.is_set():
            return

        try:
            await self.db.abyss.accounts.find().to_list(None)
            # dummy query to ensure the db is connected
        except Exception as e:
            self.logger.error("COULD NOT CONNECT TO MONGODB DATABASE.")
            self.logger.error("This could lead to fatal errors. Falling back prefixes to mentions only.")
            self.send_error(f"FAILED TO CONNECT TO MONGODB\n```py\n{utils.format_exc(e)}\n```")
            return

        try:
            self.redis = await aioredis.create_redis_pool(**config.REDIS)
        except Exception as e:
            self.logger.error("couldnt connect to redis")
            self.send_error(F"failed to connect to redis\n```py\n{utils.format_exc(e)}\n```")

        self.prepared.set()
        self.logger.warning("Successfully loaded.")

    async def on_message(self, message):
        if message.author.bot:
            return

        current = await self.redis.get(f"locale:{message.author.id}")
        if not current:
            current = i18n.LOCALE_DEFAULT.encode()
        i18n.current_locale.set(current.decode())

        await self.process_commands(message)

    def run(self):
        """"""
        # stupid sphinx inheriting bug
        super().run(config.TOKEN)

    async def close(self):
        """"""
        self.dispatch("logout")
        await self.wait_for_close()
        for guild in self.guilds:
            if not PREFIXES[guild.id]:
                continue
            await self.db.abyss.guildconfig.update_one(
                {"guild": guild.id},
                {"$set": {"prefixes": list(PREFIXES[guild.id])}})
        self.db.close()
        await self.session.close()
        await super().close()

    async def on_error(self, event, *args, **kwargs):
        to = f""">>> Error occured in event `{event}`
Arguments: {NL.join(map(repr, args))}
KW Arguments: {kwargs}
```py
{traceback.format_exc()}
```"""
        await self.send_error(to)
