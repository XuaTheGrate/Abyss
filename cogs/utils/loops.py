import asyncio
import inspect

from discord.backoff import ExponentialBackoff
from discord.ext import tasks
from discord.utils import maybe_coroutine


def loop(*, predicate=None, **kwargs):
    def decorator(func):
        if predicate:
            if not inspect.isfunction(predicate):
                raise ValueError("predicate must be a function")
            return PredicateLoop(func, predicate=predicate, **kwargs)
        return tasks.Loop(func, **kwargs)
    return decorator


class PredicateLoop(tasks.Loop):
    def __init__(self, func, *, predicate, seconds=0, hours=0, minutes=0, count=None, reconnect=False, loop=None):
        loop = loop or asyncio.get_event_loop()
        super().__init__(func, seconds=seconds, hours=hours, minutes=minutes,
                         count=count, reconnect=reconnect, loop=loop)
        self.predicate = predicate

    async def _loop(self, *args, **kwargs):
        backoff = ExponentialBackoff()
        await self._call_loop_function('before_loop')
        try:
            while await maybe_coroutine(self.predicate, *args, **kwargs):
                try:
                    await self.coro(*args, **kwargs)
                except self._valid_exception:
                    if not self.reconnect:
                        raise
                    await asyncio.sleep(backoff.delay())
                else:
                    if self._stop_next_iteration:
                        return
                    self._current_loop += 1
                    if self._current_loop == self.count:
                        break

                    await asyncio.sleep(self._sleep)
        except asyncio.CancelledError:
            self._is_being_cancelled = True
            raise
        except Exception as e:
            self._has_failed = True
            self._exception = e
            raise
        finally:
            await self._call_loop_function('after_loop')
            self._is_being_cancelled = False
            self._current_loop = 0
            self._stop_next_iteration = False
            self._has_failed = False
