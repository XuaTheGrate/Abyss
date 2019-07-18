from discord.ext import commands


class I18nHelpCommand(commands.MinimalHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        self.commands_heading = _("Commands")
        self.aliases_heading = _("Aliases:")
        self.no_category = _("No Category")

    def command_not_found(self, string):
        return _("Command '{0}' is not found.").format(string)

    def subcommand_not_found(self, command, string):
        if isinstance(command, commands.Group):
            return _("Command '{0}' has no subcommand named '{1}'.").format(command, string)
        return _("Command '{0}' has no subcommands.").format(command)


def setup(bot):
    bot.help_command = I18nHelpCommand()
