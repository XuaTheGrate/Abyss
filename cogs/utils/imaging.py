import asyncio
import io
from functools import wraps

from PIL import Image


def async_executor():
    def inner(func):
        @wraps(func)
        def inside(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_in_executor(None, func, *args, **kwargs)
        return inside
    return inner


@async_executor()
def remove_whitespace(img: io.BytesIO) -> io.BytesIO:
    im = Image.open(img).convert('RGBA')
    lx, ly = im.size
    for x in range(lx):
        for y in range(ly):
            r, g, b, a = im.getpixel((x, y))
            if 16777215 - ((r+1)*(g+1)*(b+1)) < 1000000:
                im.putpixel((x, y), (0, 0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, 'png')
    buf.seek(0)
    im.close()
    return buf
