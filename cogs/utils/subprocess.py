import asyncio
import subprocess
import aiostream


async def formatter(stream, err=False):
    async for line in stream:
        if err:
            yield '[stderr] '+line.decode('utf-8').strip('\n')
        else:
            yield line.decode('utf-8').strip('\n')


class Subprocess:
    def __init__(self, loop, *, filter_error=False):
        self.process = None
        self._stream_handlers = []
        self.loop = loop
        self._close = 0
        self._streams = None
        self._filter = filter_error

    # noinspection PyTypeChecker
    @classmethod
    async def init(cls, cmd, *args, loop=None, filter_error=False):
        loop = loop or asyncio.get_event_loop()
        self = cls(loop, filter_error=filter_error)
        self.process = await asyncio.create_subprocess_exec(cmd, *args, loop=loop, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._streams = [formatter(self.process.stdout), formatter(self.process.stderr, self._filter)]
        return self

    async def stream(self, callback, async_=False):
        async with aiostream.stream.merge(*self._streams).stream() as chunks:
            async for batch in chunks:
                fn = callback(batch)
                if async_:
                    await fn
