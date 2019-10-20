import io
import multiprocessing
import os
from functools import partial

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

from cogs.utils.enums import ResistanceModifier

BASE = Image.open('assets/statscreen.png').convert('RGBA')

# $$dev eval from cogs.utils import imaging
# p = cogs.utils.player!.Player(**{'owner': 455289384187592704, 'name': 'Kumbhanda',
#  'skills': ['Marin Karin', 'Attack', 'Guard'], 'exp': 125, 'stats': [4, 4, 4, 8, 5],
#   'resistances': [2, 2, 1, 3, 2, 2, 2, 2, 2, 1], 'arcana': 9, 'specialty': 'AILMENT',
#    'stat_points': 0, 'description': None, 'skill_leaf': None, 'ap': 0, 'unsetskills': [],
#     'finished_leaves': [], 'credits': 0, 'location': ['Sample Dungeon', 'Floor 1'],
#      'inventory': {'HEALING': [], 'TRASH': [], 'MATERIAL': [], 'SKILL_CARD': [], 'EQUIPABLE': []}})
# p.owner = "Xua#6666"
# i = await imaging.profile_executor(ctx.bot, p)
# await ctx.send(file=discord.File(i, "test.png"))

NAME_TOP_LEFT = 287
ARCANA_TOP_LEFT = 145


def __download_and_cache(name, data):
    if not os.path.isdir("assets/cache"):
        os.mkdir("assets/cache")
    if os.path.isfile("assets/cache/" + name + ".png"):
        # print(name, "found in cache")
        with open("assets/cache/" + name + ".png", "rb") as file:
            return io.BytesIO(file.read())
    response = requests.post(
        'https://api.remove.bg/v1.0/removebg',
        files={'image_file': data},
        data={'size': 'auto'},
        headers={'X-Api-Key': __import__("config").AI_KEY},
    )
    assert response.status_code == 200, (response.status_code, response.reason, response.text)
    data = response.content
    with open("assets/cache/" + name + ".png", "wb") as file:
        file.write(data)  # todo: improve
    # print(name, "saved to cache")
    return io.BytesIO(data)


RESIST_MAPPING = {
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

    image = BASE.copy()
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=20)
    width, height = draw.textsize(str(player.owner), font=font)
    draw.text(((NAME_TOP_LEFT - width) / 2, 53), str(player.owner), font=font)

    resist_pos = 14
    for rmod in player.resistances.values():
        # print(repr(rmod), resist_mapping[rmod])
        draw.text((resist_pos, 180), RESIST_MAPPING[rmod], font=font, fill=(255, 165, 10, 255))
        resist_pos += 49

    x_axis = 287
    y_axis = 328
    i = 0
    for skill in player.pre_skills:
        # print(s, i, y, x)
        if skill in ('Attack', 'Guard'):
            continue
        draw.text(((x_axis - font.getsize(skill)[0]) / 2, y_axis), skill, font=font,
                  fill=(255, 165, 10, 255))
        i += 1
        y_axis += 27
        if i % 4 == 0:
            x_axis += 582
            y_axis = 328

    font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=30)
    draw.text((146, 83), player.name, font=font, fill=(42, 50, 42, 255))

    draw.text((80, 112), str(player.level), font=font)

    x_axis, _ = font.getsize(player.arcana.name.title())
    # print("font size for", player.arcana.name.title(), ":", x)
    if x_axis > 145:
        font = ImageFont.truetype('assets/FOT-Skip Std B.otf', size=20)
    width, height = font.getsize(player.arcana.name.title())
    draw.text(((ARCANA_TOP_LEFT - width) / 2, 83), player.arcana.name.title(), font=font)

    x_axis = 124
    y_axis = 223
    width = 387
    height = 230
    for skill in (player.strength, player.magic, player.endurance, player.agility, player.luck):
        print(x_axis, y_axis, width, height, skill)
        width = width * (skill / 99)
        print(width)
        draw.rectangle((x_axis, y_axis, width + x_axis, height), fill=(255, 255, 128, 255))
        y_axis += 20
        height += 20

    dim = Image.open(demon_stuff).convert("RGBA")
    image.paste(dim, (510, 5), dim)
    dim.close()

    buffer = io.BytesIO()
    image.save(buffer, 'png')
    buffer.seek(0)
    image.close()
    HANDLES.put(buffer)


def _multiproc_handler(player, demon, *, missing=False):
    __create_profile(player, demon, missing=missing)


HANDLES = multiprocessing.Queue()


async def get_image_url(bot, goto):
    keys = iter(['png', 'jpg', 'jpeg'])
    async with bot.session.get(goto) as get:
        data = await get.read()
    soup = BeautifulSoup(data, "html.parser")
    url = soup.head.find("meta", {"name": "generator"}).meta.find("meta", property="og:image")['content']
    point = -1
    while point < 0:
        point = url.find(next(keys))
    return url[:point + 3]


async def profile_executor(bot, player):
    uri = f"https://megamitensei.fandom.com/wiki/{player.name.title().replace(' ', '_')}"
    async with bot.session.get(await get_image_url(bot, uri)) as get:
        file = io.BytesIO(await get.read())

    file = __download_and_cache(player.name, file)

    process = multiprocessing.Process(target=_multiproc_handler, args=(player, file), daemon=True)
    process.start()

    meth = partial(HANDLES.get, timeout=10)

    try:
        return await bot.loop.run_in_executor(None, meth)
    finally:
        # if process.is_alive():
        # process.terminate()
        file.close()
