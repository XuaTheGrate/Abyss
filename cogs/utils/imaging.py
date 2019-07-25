import asyncio
import io
import sys
from functools import wraps

from PIL import Image, ImageDraw, ImageFont


BASE = Image.open('assets/statscreen.png').convert('RGBA')
font = ImageFont.truetype('assets/tahoma.ttf', size=50)


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
    return __ws(img)


def __ws(img):
    im = Image.open(img).convert('RGBA')
    im = im.resize((im.size[0] // 2, im.size[1] // 2), Image.BILINEAR)
    lx, ly = im.size
    for x in range(lx):
        for y in range(ly):
            r, g, b, a = im.getpixel((x, y))
            if 16777215 - ((r + 1) * (g + 1) * (b + 1)) < 1000000:
                im.putpixel((x, y), (0, 0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, 'png')
    buf.seek(0)
    im.close()
    return buf


def get_rotated_text(text, rotation=9.46):
    im = Image.new('RGBA', tuple(x*2 for x in font.getsize(text)), 0)
    d = ImageDraw.Draw(im)
    d.text((1, 1), text, font=font)
    im = im.rotate(rotation)
    # buf = io.BytesIO()
    # im.save(buf, 'png')
    # buf.seek(0)
    # im.close()
    # pasteable = Image.open(__ws(buf)).convert('RGBA')
    return im


@async_executor()
def create_profile(player, demon_stuff):
    im = BASE.copy()
    text = get_rotated_text(str(player.owner))
    im.paste(text, (50, 10), text)
    im.paste(demon_stuff, (600, 100), demon_stuff)
    buffer = io.BytesIO()
    im.save(buffer, 'png')
    im.close()
    buffer.seek(0)
    return buffer
