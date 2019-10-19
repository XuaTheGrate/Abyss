from discord.ext import commands

from .utils.paginators import PaginationHandler


class I18nHelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        self.paginator = commands.Paginator(max_size=1985)
        self.commands_heading = "Commands"
        self.aliases_heading = "Aliases:"
        self.no_category = "No Category"
        self.command_attrs = {
            'description': "Provides help for various commands.",
            'cooldown': commands.Cooldown(3, 10, commands.BucketType.channel),
            'name': 'help'
        }

    def command_not_found(self, string):
        return "Command '{0}' is not found.".format(string)

    def subcommand_not_found(self, command, string):
        if isinstance(command, commands.Group):
            return "Command '{0}' has no subcommand named '{1}'.".format(command, string)
        return "Command '{0}' has no subcommands.".format(command)

    def get_opening_note(self):
        return "Use `{0}{1} [command]` for more info on a command.".format(self.clean_prefix, 'help')

    async def send_cog_help(self, cog):  # no cog specific help
        return await self.send_bot_help(self.get_bot_mapping())

    async def send_pages(self):
        pg = PaginationHandler(self.context.bot, self.paginator)
        await pg.start(self.context)

    async def filter_commands(self, cmds, *, sort=False, key=None):
        if sort and key is None:
            key = lambda c: c.name
        it = filter(lambda c: not c.hidden and c.enabled, cmds)
        if not self.verify_checks:
            return sorted(it, key=key) if sort else list(it)

        async def p(cmd):
            try:
                return await cmd.can_run(self.context)
            except commands.CommandError:
                return False

        fin = []
        for cmd in it:
            if await p(cmd):
                fin.append(cmd)
        if sort:
            fin.sort(key=key)
        return fin


def setup(bot):
    bot.help_command = I18nHelpCommand()
