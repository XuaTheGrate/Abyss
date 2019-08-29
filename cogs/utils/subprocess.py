import asyncio
import subprocess
import aiostream


async def formatter(stream, err=False):
    async for line in stream:
        if err:
            yield '[stderr] '+line.decode().strip('\n')
        else:
            yield line.decode().strip('\n')


class Subprocess:
    def __init__(self, loop, *, filter_error=False):
        self._process = None
        self._stream_handlers = []
        self.loop = loop
        self._close = 0
        self._stream = None
        self._filter = filter_error

    @classmethod
    async def init(cls, cmd, *args, loop=None, filter_error=False):
        loop = loop or asyncio.get_event_loop()
        self = cls(loop, filter_error=filter_error)
        self._process = await asyncio.create_subprocess_exec(cmd, *args, loop=loop, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        streams = [formatter(self._process.stdout), formatter(self._process.stderr, self._filter)]
        self._stream = aiostream.stream.merge(*streams)
        return self

    def __aiter__(self):
        return self._stream.__aiter__()
