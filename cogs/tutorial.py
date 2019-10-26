import asyncio

from discord.ext import commands

from cogs.utils.battle import Enemy, WildBattle


class Tutorial(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def tutorial(self, ctx):
        """Shows you a tutorial on how to use various functions."""
        conf = self.bot.loop.create_task(ctx.confirm("To begin, you'll need a player."
                                                     " If you already have a player, click the <:tickYes:568613200728293435>,"
                                                     " otherwise, type `$create`."))
        k = self.bot.loop.create_task(self.bot.wait_for(
            'command_completion', check=lambda c: c.command.name == 'create' and c.author == ctx.author))
        await asyncio.wait([conf, k], loop=self.bot.loop, timeout=180, return_when=asyncio.FIRST_COMPLETED)
        if not conf.done() and not k.done():
            conf.cancel()
            k.cancel()
            await ctx.send("Tutorial timed out, run `$tutorial` again to start over.")
            return

        if conf.done():
            k.cancel()
            if not await ctx.confirm("Send `$status`, click the \u270b button, then click the <:tickYes:568613200728293435>.",
                                     timeout=180):
                return  # time out 2: electric boogaloo
        elif k.done():
            # ran the $create command
            conf.cancel()
        else:
            # ?????????
            raise AssertionError
        ctx.player = player = self.bot.players.players[ctx.author.id]
        self.bot.get_cog("Exploration").debug.append(ctx.author.id)
        if not await ctx.confirm(
                "Now that your player has been created, lets try it out. Type `$search` to look around."
                "\n\nFrom now own, click <:tickYes:568613200728293435> to advance the tutorial, "
                "or click <:tickNo:568613146152009768> to stop the tutorial.",
                timeout=180):
            return
        if not await ctx.confirm(
                "Don't worry about the chests for the time being, but do notice the treasures and doors.\n"
                "The treasures are what gets you the items you want.\nThey can have materials, healing items "
                "and may even contain the extremely rare Treasure Demon.\nYou can open one with `$open-treasure`.\n"
                "Do note that these are limited, once you open every treasure in this area, you cannot open any more"
                " until it has passed midnight (UTC).\n\n"
                "As for the doors, you can interact with these to travel to other parts of the dungeon.",
                timeout=180):
            return
        if not await ctx.confirm("Alright, now for the core part of the game, the battling system. "
                                 "I'm going to stick you into a battle against Arsene, one of the easier demons in this area.",
                                 timeout=180):
            return
        bt_cog = self.bot.get_cog('BattleSystem')
        data = await self.bot.db.abyss.encounters.find_one({"name": "Arsene"})
        en = await Enemy(**data).populate_skills(self.bot)
        bt_cog.battles[ctx.author.id] = bt = WildBattle(player, ctx, en, ambush=True)
        await asyncio.sleep(3)
        if not await ctx.confirm(
                "Click on the \u2753 to read some instructions. You can read the faq after the tutorial."
                " Once done, click the tick.",
                timeout=180):
            return
        if not await ctx.confirm("Alright, so lets attack it. Click on the \u2694 to view your active skills. "
                                 "We don't really need to worry about any of the others, so lets go with `Attack`. "
                                 "Type `attack` and send it, then select `Arsene` as a target. Click the tick to continue.",
                                 timeout=180):
            return
        if not await ctx.confirm("If you haven't already, you can finish off the Arsene to gain some sweet experience. "
                                 "Otherwise, you can click the \N{RUNNER} button to run away. Click the tick to continue, finally.",
                                 timeout=180):
            return
        await ctx.send(
            "And that about does it for the tutorial. If you still have questions, be sure to check the help and faq "
            "commands. If your question isn't there, please join the support server where I can answer.\n\n"
            "Thanks for playing!")

    @tutorial.after_invoke
    async def finalizer(self, ctx):
        try:
            self.bot.get_cog("Maps").debug.remove(ctx.author.id)
        except ValueError:
            pass


def setup(bot):
    bot.add_cog(Tutorial(bot))
