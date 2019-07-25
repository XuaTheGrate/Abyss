import asyncio
import io
from functools import wraps

from PIL import Image, ImageDraw, ImageFont


BASE = Image.open('assets/statscreen.png').convert('RGBA')


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
    im = im.resize((im.size[0]//8, im.size[1]//8))
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


@async_executor()
def create_profile(player, demon_stuff):
    im = BASE.copy()
    draw = ImageDraw.Draw(im)
    draw.text((100, 50), str(player.owner))
    im.paste(demon_stuff, (250, 125), demon_stuff)
    buffer = io.BytesIO()
    im.save(buffer, 'png')
    im.close()
    buffer.seek(0)
    return buffer
