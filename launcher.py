import asyncio
from datetime import datetime

import discord
import logging
import multiprocessing
import os
import random
import signal
import sys
import time

import requests

# from bot_mp import ClusterBot
from bot.bot import Abyss
from config import DEBUG_WEBHOOK, TOKEN, SPLASHES

log = logging.getLogger("Cluster#Launcher")
log.setLevel(logging.DEBUG)
hdlr = logging.StreamHandler()
hdlr.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
fhdlr = logging.FileHandler("cluster-Launcher.log", encoding='utf-8')
fhdlr.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
log.handlers = [hdlr, fhdlr]


CLUSTER_NAMES = (
    'Alpha', 'Beta', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel',
    'India', 'Juliett', 'Kilo', 'Mike', 'November', 'Oscar', 'Papa', 'Quebec',
    'Romeo', 'Sierra', 'Tango', 'Uniform', 'Victor', 'Whisky', 'X-ray', 'Yankee', 'Zulu'
)
NAMES = iter(CLUSTER_NAMES)

webhook_logger = discord.Webhook.from_url(DEBUG_WEBHOOK, adapter=discord.RequestsWebhookAdapter())


def get_shard_count():
    data = requests.get('https://discordapp.com/api/v7/gateway/bot', headers={
        "Authorization": "Bot " + TOKEN,
        "User-Agent": "DiscordBot (https://github.com/Rapptz/discord.py 1.3.0a) Python/3.7 aiohttp/3.6.1"
    })
    data.raise_for_status()
    content = data.json()
    log.info(f"Successfully got shard count of {content['shards']} ({data.status_code, data.reason})")
    # return 16
    return content['shards']


class Launcher:
    def __init__(self, loop, *, ipc=False):
        print(random.choice(SPLASHES).strip('\n'))
        self.cluster_queue = []
        self.clusters = []

        self.fut = None
        self.loop = loop
        self.alive = True

        self.keep_alive = None
        self.init = time.perf_counter()

        self.start_ipc = ipc
        self.ipc = None

    def info(self, message):
        embed = discord.Embed(colour=discord.Colour.green(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def warn(self, message):
        embed = discord.Embed(colour=discord.Colour.gold(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def error(self, message):
        embed = discord.Embed(colour=discord.Colour.red(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def start(self):
        self.info("[Launcher] Starting up")
        self.fut = asyncio.ensure_future(self.startup(), loop=self.loop)

        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            self.info("[Launcher] Received KeyboardInterrupt")
            self.shutdown()
        finally:
            self.cleanup()

    def _cleanup(self):
        tasks = asyncio.all_tasks(self.loop)
        for t in tasks:
            t.cancel()
        self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        for t in tasks:
            if t.cancelled():
                continue
            if t.exception():
                t.print_stack()

        if hasattr(self.loop, 'shutdown_asyncgens'):  # 3.6+
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        if hasattr(self.loop, 'shutdown_default_executor'):  # 3.8+
            self.loop.run_until_complete(self.loop.shutdown_default_executor())

    def cleanup(self):
        self.info("[Launcher] Cleaning up tasks")
        self._cleanup()
        self.loop.stop()
        if sys.platform == 'win32':
            print("press ^C again")
        self.loop.close()

    def task_complete(self, task):
        if task.cancelled():
            return
        if task.exception():
            if isinstance(task.exception(), KeyboardInterrupt):
                return
            task.print_stack()
            self.keep_alive = self.loop.create_task(self.rebooter())
            self.keep_alive.add_done_callback(self.task_complete)

    async def startup(self):
        if self.start_ipc:
            log.info("IPC server starting up")
            import ipc  # pylint: disable=import-outside-toplevel
            self.ipc = multiprocessing.Process(target=ipc.start, daemon=True)
            self.ipc.start()

        shards = list(range(get_shard_count()))
        size = [shards[x:x + 4] for x in range(0, len(shards), 4)]
        log.info(f"Preparing {len(size)} clusters")
        self.info(f"[Launcher] Starting {len(size)}C / {len(shards)}S")
        for shard_ids in size:
            self.cluster_queue.append(Cluster(self, next(NAMES), shard_ids, len(shards)))

        await self.start_cluster()
        self.keep_alive = self.loop.create_task(self.rebooter())
        self.keep_alive.add_done_callback(self.task_complete)
        log.info(f"Startup completed in {time.perf_counter() - self.init:.2f}s")
        self.info(f"Startup completed in {time.perf_counter() - self.init:.2f}s")

    def shutdown(self):
        self.info("Shutting down clusters")
        log.info("Shutting down clusters")
        self.alive = False
        if self.keep_alive:
            self.keep_alive.cancel()
        for cluster in self.clusters:
            cluster.stop()
        if self.ipc and self.ipc.is_alive():
            os.kill(self.ipc.pid, signal.SIGINT)

    async def rebooter(self):
        while self.alive:
            # log.info("Cycle!")
            if not self.clusters and self.alive:
                self.alive = False
                self.warn("[Launcher] found all clusters dead")
                log.warning("All clusters appear to be dead")
                raise KeyboardInterrupt

            if self.ipc and not self.ipc.is_alive():
                log.critical("IPC websocket server dead, require reboot")
                self.ipc = None

            to_remove = []
            for cluster in self.clusters:
                if not cluster.process.is_alive():
                    if cluster.process.exitcode != 0:
                        # ignore safe exits
                        self.warn(f'[Cluster#{cluster.name}] Exited with status {cluster.process.exitcode}, restarting')
                        log.info(f"Cluster#{cluster.name} exited with code {cluster.process.exitcode}, restarting")
                        await cluster.start()
                    else:
                        self.warn(f"[Launcher] Found Cluster#{cluster.name} dead with status 0.")
                        log.info(f"Cluster#{cluster.name} found dead")
                        to_remove.append(cluster)
                        cluster.stop()  # ensure stopped
            for rem in to_remove:
                self.clusters.remove(rem)
            await asyncio.sleep(5)

    async def start_cluster(self):
        if self.cluster_queue:
            cluster = self.cluster_queue.pop(0)
            self.info(f"[Launcher] Starting Cluster#{cluster.name}")
            log.info(f"Starting Cluster#{cluster.name}")
            await cluster.start()
            log.info("Done!")
            self.clusters.append(cluster)
            await self.start_cluster()
        else:
            log.info("All clusters launched")
            self.info("[Launcher] Successfully launched all clusters")


class Cluster:
    def __init__(self, launcher, name, shard_ids, max_shards):
        self.launcher = launcher
        self.process = None
        self.kwargs = dict(
            shard_ids=shard_ids,
            shard_count=max_shards,
            cluster_name=name
        )
        self.name = name
        self.log = logging.getLogger(f"Cluster#{name}")
        self.log.setLevel(logging.DEBUG)
        hdlr = logging.StreamHandler()
        hdlr.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
        fhdlr = logging.FileHandler("cluster-Launcher.log", encoding='utf-8')
        fhdlr.setFormatter(logging.Formatter("[%(asctime)s %(name)s/%(levelname)s] %(message)s"))
        self.log.handlers = [hdlr, fhdlr]
        self.log.info(f"Initialized with shard ids {shard_ids}, total shards {max_shards}")

    def info(self, message):
        embed = discord.Embed(colour=discord.Colour.green(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def warn(self, message):
        embed = discord.Embed(colour=discord.Colour.gold(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def error(self, message):
        embed = discord.Embed(colour=discord.Colour.red(), title=message, timestamp=datetime.utcnow())
        webhook_logger.send(embed=embed)

    def wait_close(self):
        return self.process.join()

    async def start(self, *, force=False):
        if self.process and self.process.is_alive():
            if not force:
                self.warn(f"[Cluster#{self.name}] Attempted to restart while running")
                self.log.warning("Start called with already running cluster, pass `force=True` to override")
                return
            self.log.info("Terminating existing process")
            self.process.terminate()
            self.process.close()

        stdout, stdin = multiprocessing.Pipe()
        kw = self.kwargs
        kw['pipe'] = stdin
        self.process = multiprocessing.Process(target=Abyss, kwargs=kw, daemon=True)
        self.process.start()
        self.log.info(f"Process started with PID {self.process.pid}")

        if await self.launcher.loop.run_in_executor(None, stdout.recv) == 1:
            stdout.close()
            self.log.info("Process started successfully")
            self.info(f"[Cluster#{self.name}] Successfully loaded")

        return True

    def stop(self, sign=signal.SIGINT):
        self.info(f"[Cluster#{self.name}] Requested to close with signal {sign!r}")
        self.log.info(f"Shutting down with signal {sign!r}")
        try:
            os.kill(self.process.pid, sign)
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    Launcher(loop).start()
