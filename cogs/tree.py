
import discord
import json
from discord.ext import commands

from .utils import i18n, lookups
from .utils.objects import SkillTree


class SkillTreeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.skill_tree = None

        with open("skilltree.json") as f:
            self._skill_tree = json.load(f)

        try:
            self.do_cuz_ready()
        except AttributeError:
            pass

    def do_cuz_ready(self):
        self.skill_tree = SkillTree(self._skill_tree, self.bot)

    @commands.group(aliases=['skilltree', 'skill-tree'])
    async def tree(self, ctx):
        """Base skill tree command. Does nothing alone."""
        pass

    @tree.command(aliases=['progress'])
    async def status(self, ctx):
        """Gets the progress of your current skill tree."""
        if not ctx.player:
            return await ctx.send(_("You don't own a player."))

        if not ctx.player.leaf:
            return await ctx.send(_("No leaf has been selected. Use `{.prefix}tree activate <leaf>` to start a new")
                                  .format(ctx))

        embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[ctx.player.leaf.name])
        embed.title = ctx.player.leaf.name.title()
        d = [_('Unlockable skills:\n')]
        for skill in ctx.player.leaf.skills:
            d.append(f"{lookups.TYPE_TO_EMOJI[skill.type.name.lower()]} {skill.name}")
        embed.description = '\n'.join(d)
        embed.set_footer(text=f'{ctx.player.ap_points} AP/{ctx.player.leaf.cost//1000} AP')
        await ctx.send(embed=embed)

    @tree.command()
    async def unlocked(self, ctx):
        """Views all leaves you have unlocked (not completed)."""
        if not ctx.player:
            return await ctx.send(_("You don't own a player."))
        leaves = [k+':0' for k in self.skill_tree.branches]
        while True:
            for leaf in leaves.copy():
                if leaf in ctx.player.finished_leaves:
                    leaves.remove(leaf)
                    leaves.extend(self.skill_tree.branches[leaf.split(':')[0]].leaves[leaf])
                    break
            else:
                break
        leaves = [self.skill_tree.branches[k[:-2]].leaves[k] for k in leaves]
        embed = discord.Embed(colour=lookups.TYPE_TO_COLOUR[ctx.player.specialty.name.lower()])
        embed.title = _("Available leaves ready for completion")
        embed.description = '\n'.join(
            f'{lookups.TYPE_TO_EMOJI[l.name.split(":")[0]]} {l.name}: {l.cost} AP' for l in leaves
        )
        embed.set_footer(text=_("You cannot activate a leaf if you already have one active."))
        await ctx.send(embed=embed)

    @tree.command()
    async def activate(self, ctx, *, name=None):
        if not name:
            return await ctx.invoke(self.unlocked)
        await ctx.send("todo")


def setup(bot):
    bot.add_cog(SkillTreeCog(bot))
