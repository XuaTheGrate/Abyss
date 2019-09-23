import io
import multiprocessing
import os
from functools import partial

import requests
from PIL import Image, ImageDraw, ImageFont

from cogs.utils.enums import ResistanceModifier

BASE = Image.open('assets/statscreen.png').convert('RGBA')

"""
$$dev eval from cogs.utils import imaging
p = cogs.utils.player!.Player(**{'owner': 455289384187592704, 'name': 'Kumbhanda', 'skills': ['Marin Karin', 'Attack', 'Guard'], 'exp': 125, 'stats': [4, 4, 4, 8, 5], 'resistances': [2, 2, 1, 3, 2, 2, 2, 2, 2, 1], 'arcana': 9, 'specialty': 'AILMENT', 'stat_points': 0, 'description': None, 'skill_leaf': None, 'ap': 0, 'unsetskills': [], 'finished_leaves': [], 'credits': 0, 'location': ['Sample Dungeon', 'Floor 1'], 'inventory': {'HEALING': [], 'TRASH': [], 'MATERIAL': [], 'SKILL_CARD': [], 'EQUIPABLE': []}})
p.owner = "Xua#6666"
i = await imaging.profile_executor(ctx.bot, p)
await ctx.send(file=discord.File(i, "test.png"))
"""

nx = 287
ax = 145


def __download_and_cache(name, data):
    if not os.path.isdir("assets/cache"):
        os.mkdir("assets/cache")
    if os.path.isfile("assets/cache/" + name + ".png"):
        # print(name, "found in cache")
        with open("assets/cache/" + name + ".png", "rb") as f:
            return io.BytesIO(f.read())
    response = requests.post(
        'https://api.remove.bg/v1.0/removebg',
        files={'image_file': data},
        data={'size': 'auto'},
        headers={'X-Api-Key': __import__("config").AI_KEY},
    )
    assert response.status_code == 200, (response.status_code, response.reason, response.text)
    data = response.content
    with open("assets/cache/" + name + ".png", "wb") as f:
        f.write(data)  # todo: improve
    # print(name, "saved to cache")
    return io.BytesIO(data)


resist_mapping = {
    ResistanceModifier.NORMAL: ' - ',
    ResistanceModifier.WEAK: 'Wk ',
    ResistanceModifier.RESIST: 'Str',
    ResistanceModifier.ABSORB: 'Abs',
    ResistanceModifier.IMMUNE: 'Nul',
    ResistanceModifier.REFLECT: 'Rpl'
}


def __create_profile(player, demon_stuff, *, missing=False):
    if not missing:
        demon_stuff = __download_and_cache(player.name, demon_stuff)
    # print(player.resistances)

    im = BASE.copy()
    draw = ImageDraw.Draw(im)

    font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=20)
    w, h = draw.textsize(str(player.owner), font=font)
    draw.text(((nx - w) / 2, 53), str(player.owner), font=font)

    mp = 14
    for rmod in player.resistances.values():
        # print(repr(rmod), resist_mapping[rmod])
        draw.text((mp, 180), resist_mapping[rmod], font=font, fill=(255, 165, 10, 255))
        mp += 49

    x = 287
    y = 328
    i = 0
    for s in player._skills:
        # print(s, i, y, x)
        if s in ('Attack', 'Guard'):
            continue
        draw.text(((x - font.getsize(s)[0]) / 2, y), s, font=font,
                  fill=(255, 165, 10, 255))
        i += 1
        y += 27
        if i % 4 == 0:
            x += 582
            y = 328

    font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=30)
    draw.text((146, 83), player.name, font=font, fill=(42, 50, 42, 255))

    draw.text((80, 112), str(player.level), font=font)

    x, _ = font.getsize(player.arcana.name.title())
    # print("font size for", player.arcana.name.title(), ":", x)
    if x > 145:
        font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=20)
    w, h = font.getsize(player.arcana.name.title())
    draw.text(((ax - w) / 2, 83), player.arcana.name.title(), font=font)

    dim = Image.open(demon_stuff).convert("RGBA")
    im.paste(dim, (510, 5), dim)
    dim.close()

    buffer = io.BytesIO()
    im.save(buffer, 'png')
    buffer.seek(0)
    im.close()
    handles.put(buffer)


def _multiproc_handler(player, demon, *, missing=False):
    __create_profile(player, demon, missing=missing)


handles = multiprocessing.Queue()


async def profile_executor(bot, player):
    uri = await bot.redis.get(f"demon:{player.name.replace(' ', '_').title()}")
    ms = False
    if uri:
        uri = uri.decode()
        async with bot.session.get(uri) as get:
            file = io.BytesIO(await get.read())
    else:
        bot.send_error(f"no url for {player.name}, defaulting to MISSINGNO.")
        with open("assets/MISSINGNO.png", 'rb') as f:
            file = io.BytesIO(f.read())
        ms = True

    process = multiprocessing.Process(target=_multiproc_handler, args=(player, file), kwargs={"missing": ms},
                                      daemon=True)
    process.start()

    meth = partial(handles.get, timeout=10)

    try:
        return await bot.loop.run_in_executor(None, meth)
    finally:
        # if process.is_alive():
        # process.terminate()
        file.close()
        pass
