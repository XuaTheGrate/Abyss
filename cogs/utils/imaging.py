import io
import multiprocessing
import sys
import json
import os

from PIL import Image, ImageDraw, ImageFont

BASE = Image.open('assets/statscreen.png').convert('RGBA')
font = ImageFont.truetype('assets/tahoma.ttf', size=50)


def __remove_whitespace(img: io.BytesIO) -> io.BytesIO:
    return __ws(img)


def __ws(img):
    im = Image.open(img).convert('RGBA')
    im.thumbnail((im.size[0] // 3, im.size[1] // 3), Image.BILINEAR)
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


def __get_rotated_text(text, rotation=9.46):
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


def __create_profile(player, demon_stuff):
    im = BASE.copy()
    text = __get_rotated_text(str(player.owner))
    im.paste(text, (50, 10), text)
    pos = ((im.size[0] - demon_stuff.size[0]), (im.size[1]//2 - demon_stuff.size[1]//2))
    print(f"HI IM DEBUG {pos}")
    im.paste(demon_stuff, pos, demon_stuff)
    buffer = io.BytesIO()
    im.save(buffer, 'png')
    im.close()
    buffer.seek(0)
    im.close()
    text.close()
    demon_stuff.close()
    handles.put(buffer)


def _multiproc_handler(player, demon):
    dimg = Image.open(demon).convert('RGBA')
    dimg = __ws(dimg)
    dimg = Image.open(dimg).convert('RGBA')
    __create_profile(player, dimg)


handles = multiprocessing.Queue()


async def profile_executor(bot, player):
    uri = await bot.redis.get(f"demon:{player.name.replace(' ', '_').title()}")
    if uri:
        uri = uri.decode()
        async with bot.session.get(uri) as get:
            file = io.BytesIO(await get.read())
    else:
        bot.send_error(f"no url for {player.name}, defaulting to MISSINGNO.")
        with open("assets/MISSINGNO.png", 'rb') as f:
            file = io.BytesIO(f.read())

    ply = player.to_json()
    ply['__debug'] = str(player.owner)

    process = multiprocessing.Process(target=_multiproc_handler, args=(player, file), daemon=True)
    process.start()

    try:
        return await bot.loop.run_in_executor(None, handles.get)
    finally:
        process.terminate()
