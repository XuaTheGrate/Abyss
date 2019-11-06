from discord.ext import commands

# ᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ
smoltext = str.maketrans({'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ᶦ',
                          'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'q': 'ᵠ', 'r': 'ʳ',
                          's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ'})

upsidedown = str.maketrans({
    'a': '?',
    'b': 'q',
    'c': '?',
    'd': 'p',
    'e': '?',
    'f': '?',
    'g': '?',
    'h': '?',
    'i': '?',
    'j': '?',
    'k': '?',
    'l': 'l',
    'm': '?',
    'n': 'u',
    'o': 'o',
    'p': 'd',
    'q': 'b',
    'r': '?',
    's': 's',
    't': '?',
    'u': 'n',
    'v': '?',
    'w': '?',
    'x': 'x',
    'y': '?',
    'z': 'z',
    'A': '?',
    'B': 'q',
    'C': '?',
    'D': 'p',
    'E': '?',
    'F': '?',
    'G': '?',
    'H': 'H',
    'I': 'I',
    'J': '?',
    'K': '?',
    'L': '?',
    'M': 'W',
    'N': 'N',
    'O': 'O',
    'P': '?',
    'Q': 'Q',
    'R': '?',
    'S': 'S',
    'T': '┴',
    'U': '∩',
    'V': '?',
    'W': 'M',
    'X': 'X',
    'Y': '?',
    'Z': 'Z',
    '0': '0',
    '1': '?',
    '2': '?',
    '3': '?',
    '4': '?',
    '5': '?',
    '6': '9',
    '7': '?',
    '8': '8',
    '9': '6'
})


class Shitpost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['smoltext', 'smol', 'small'])
    async def smalltext(self, ctx, *, text: commands.clean_content):
        """ᵗᵘʳⁿˢ ʸᵒᵘʳ ᵗᵉˣᵗ ᶦⁿᵗᵒ ˢᵐᵃˡˡ ᵗᵉˣᵗ"""
        await ctx.send(text.lower().translate(smoltext))

    @commands.command(aliases=['udtext', 'aussietext', 'oztext', 'australianize'])
    async def upsidedowntext(self, ctx, *, text: commands.clean_content):
        """uʍop ǝpᴉsdn ʇxǝʇ ɹnoʎ sǝʞɐɯ"""
        await ctx.send(text.translate(upsidedown))

    @commands.command()
    async def mock(self, ctx, *, thing: commands.clean_content):
        await ctx.send(f"haha null byte sucks big {thing}")


def setup(bot):
    bot.add_cog(Shitpost(bot))
