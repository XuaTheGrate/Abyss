import asyncio
import subprocess


async def stream_handler(self, stream):
    async for line in stream:
        await self._stream.put(line.decode().strip('\n'))
    # stream was closed
    # await self._stream.put(None)


class Subprocess:
    def __init__(self, loop):
        self._process = None
        self._stream = asyncio.Queue(loop=loop)
        self._stream_handlers = []
        self.loop = loop
        self._close = 0

    @classmethod
    async def init(cls, cmd, *args, loop=None):
        loop = loop or asyncio.get_event_loop()
        self = cls(loop)
        self._process = await asyncio.create_subprocess_exec(cmd, *args, loop=loop, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._stream_handlers.append(loop.create_task(stream_handler(self, self._process.stdout)))
        self._stream_handlers.append(loop.create_task(stream_handler(self, self._process.stderr)))
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._process.returncode is not None:
            raise StopAsyncIteration
        try:
            n = await asyncio.wait_for(self._stream.get(), timeout=30)
        except asyncio.TimeoutError:
            n = None
        if not n:
            self._close += 1
            return
        if self._close == 2:
            list(map(asyncio.Task.cancel, self._stream_handlers))
            raise StopAsyncIteration
        return n
