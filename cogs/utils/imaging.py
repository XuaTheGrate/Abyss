import io
import multiprocessing
from functools import partial

from PIL import Image, ImageDraw, ImageFont

BASE = Image.open('assets/statscreen.png').convert('RGBA')
FONT = ImageFont.truetype('assets/tahoma.ttf', size=50)
SMOL = ImageFont.truetype('assets/tahomabd.ttf', size=30)


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


def __get_rotated_text(text, rotation=9.46, colour=(255, 255, 255, 255), font=FONT):
    im = Image.new('RGBA', tuple(x*2 for x in font.getsize(text)), 0)
    d = ImageDraw.Draw(im)
    d.text((1, 1), text, font=font, fill=colour)
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
    im.paste(text, (50, 20), text)
    text.close()

    demon_name = __get_rotated_text(player.name)
    im.paste(demon_name, (100, 75), demon_name)
    demon_name.close()

    pos = ((im.size[0] - demon_stuff.size[0])-20, (im.size[1]//2 - demon_stuff.size[1]//2))
    # print(f"HI IM DEBUG {pos}")
    im.paste(demon_stuff, pos, demon_stuff)
    demon_stuff.close()

    st = __get_rotated_text(str(player.strength), 0.0, (0, 0, 0, 255), SMOL)
    st = st.resize((st.size[0], st.size[1]+15), resample=Image.BILINEAR)
    im.paste(st, (725, 465), st)
    st.close()

    ma = __get_rotated_text(str(player.magic), 0.0, (0, 0, 0, 255), SMOL)
    ma = ma.resize((ma.size[0], ma.size[1]+15), resample=Image.BILINEAR)
    im.paste(ma, (735, 500), ma)
    ma.close()

    en = __get_rotated_text(str(player.endurance), 0.0, (0, 0, 0, 255), SMOL)
    en = en.resize((en.size[0], en.size[1]+15), resample=Image.BILINEAR)
    im.paste(en, (725, 535), en)
    en.close()
    
    ag = __get_rotated_text(str(player.agility), 0.0, (0, 0, 0, 255), SMOL)
    ag = ag.resize((ag.size[0], ag.size[1] + 15), resample=Image.BILINEAR)
    im.paste(ag, (735, 570), ag)
    ag.close()

    lu = __get_rotated_text(str(player.luck), 0.0, (0, 0, 0, 255), SMOL)
    lu = lu.resize((lu.size[0], lu.size[1] + 15), resample=Image.BILINEAR)
    im.paste(lu, (725, 605), lu)
    lu.close()

    lvl = __get_rotated_text(str(player.level))
    im.paste(lvl, (230, 135), lvl)
    lvl.close()

    exp = __get_rotated_text(str(player.exp_to_next_level()))
    im.paste(exp, (395, 115), exp)
    exp.close()

    buffer = io.BytesIO()
    im.save(buffer, 'png')
    buffer.seek(0)
    im.close()
    handles.put(buffer)


def _multiproc_handler(player, demon):
    dimg = __ws(demon)
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

    meth = partial(handles.get, timeout=10)

    try:
        return await bot.loop.run_in_executor(None, meth)
    finally:
        # if process.is_alive():
            # process.terminate()
        pass
