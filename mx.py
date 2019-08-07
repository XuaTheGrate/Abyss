from haishoku.haishoku import Haishoku
import requests
import io

import webcolors

def closest_colour(requested_colour):
    min_colours = {}
    for key, name in webcolors.css3_hex_to_names.items():
        r_c, g_c, b_c = webcolors.hex_to_rgb(key)
        rd = (r_c - requested_colour[0]) ** 2
        gd = (g_c - requested_colour[1]) ** 2
        bd = (b_c - requested_colour[2]) ** 2
        min_colours[(rd + gd + bd)] = name
    return min_colours[min(min_colours.keys())]

def get_colour_name(requested_colour):
    try:
        closest_name = actual_name = webcolors.rgb_to_name(requested_colour)
    except ValueError:
        closest_name = closest_colour(requested_colour)
        actual_name = None
    return actual_name, closest_name


data = requests.get("https://cdn.discordapp.com/emojis/604534890641227776.png?v=1",
    headers={"User-Agent": "DiscordBot (https://github.com/Rapptz/discord.py 1.2.3) Python/3.6 aiohttp/3.5.4"}).content
file = io.BytesIO(data)

for _, (r, g, b) in Haishoku.getPalette(file):
    print(f"0x{f'{r:x}':0>2}{f'{g:x}':0>2}{f'{b:x}':0>2}", get_colour_name((r, g, b)))


for xx in range(0, 1000, 100):
    for yy in range(0, 1000, 100):
        nimg = Image.new('RGB', (100, 100))
        for x in range(100):
            for y in range(100):
                xxx, yyy = xx+x, yy+y
                px = img.getpixel((xxx, yyy))
                nimg.putpixel((x,y), px)
        buf = io.BytesIO()
        nimg.save(buf, 'png')
        nimg.close()
        buf.seek(0)
        dom = Haishoku.getDominant(buf)
        for x in range(100):
            for y in range(100):
                xxx, yyy = xx+x, yy+y
                img.putpixel((xxx, yyy), dom)
