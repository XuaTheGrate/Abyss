from discord.ext import commands


# ᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻ
smoltext = str.maketrans({'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ᶦ',
                          'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'q': 'ᵠ', 'r': 'ʳ',
                          's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ'})


class Shitpost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['smoltext', 'smol', 'small'])
    async def smalltext(self, ctx, *, text: commands.clean_content):
        """ᵗᵘʳⁿˢ ʸᵒᵘʳ ᵗᵉˣᵗ ᶦⁿᵗᵒ ˢᵐᵃˡˡ ᵗᵉˣᵗ"""
        await ctx.send(text.lower().translate(smoltext))


def setup(bot):
    bot.add_cog(Shitpost(bot))
