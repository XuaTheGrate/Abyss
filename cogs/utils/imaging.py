import asyncio
import io
import sys
import json
import os

from PIL import Image, ImageDraw, ImageFont

if __name__ == '__main__':
    from objects import Player, Skill
    import lookups
else:
    from .objects import Player, Skill
    from . import lookups

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
    return buffer


async def profile_executor(bot, player):
    uri = await bot.redis.get(f"demon:{player.name.replace(' ', '_').title()}")
    if uri:
        uri = uri.decode()
        async with bot.session.get(uri) as get:
            with open(f"input/{player.owner.id}.png", "wb") as f:
                f.write(await get.read())
    else:
        bot.send_error(f"no url for {player.name}, defaultig to MISSINGNO.")
        os.system(f"cp assets/MISSINGNO.png input/{player.owner.id}.png")

    ply = player.to_json()
    ply['__debug'] = str(player.owner)

    shell = await asyncio.create_subprocess_exec(sys.executable,
                                                 '/home/xua/adventure2/cogs/utils/imaging.py',
                                                 json.dumps(player.to_json()),
                                                 stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)

    out, err = await asyncio.wait_for(shell.communicate(), timeout=10)
    if out:
        bot.send_error(out.decode())
    if err:
        raise RuntimeError(err.decode())
    try:
        shell.terminate()
        shell.kill()
    except ProcessLookupError:
        pass
    with open(f"output/{player.owner.id}.png", 'rb') as f:
        try:
            return io.BytesIO(f.read())
        finally:
            os.remove(f"output/{player.owner.id}.png")


if __name__ == '__main__':
    _, rawr = sys.argv
    player = Player(**json.loads(rawr))
    print(rawr)
    print(repr(player))
    with open(f"input/{player._owner_id}.png", "rb") as f:
        image = io.BytesIO(f.read())
    im = Image.open(__ws(image)).convert('RGBA')
    data = __create_profile(player, im)
    with open(f"output/{player._owner_id}.png", "wb") as f:
        f.write(data.getvalue())
    os.remove(f"input/{player._owner_id}.png")

