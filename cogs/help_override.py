import os

from discord.ext import commands

from .utils import i18n


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

    def get_opening_note(self):
        return _("Use `{prefix}{command_name} [command]` for more info on a command.")

    async def send_command_help(self, command):
        self.paginator.add_line(self.get_command_signature(command), empty=True)
        locale = await self.context.bot.redis.get(f"locale:{self.context.author.id}")
        if not locale:
            locale = 'en_US'
        else:
            locale = locale.decode()
        if not os.path.isfile(f"cogs/help/{locale}/{command.qualified_name.replace(' ', '_')}"):
            cmdhelp = command.help
            self.context.bot.logger.warning(f"no translation for {locale}")
        else:
            with open(f"cogs/help/{locale}/{command.qualified_name.replace(' ', '_')}") as f:
                cmdhelp = f.read().strip()
        if not cmdhelp:
            cmdhelp = ""
        for line in cmdhelp.split('\n'):
            self.paginator.add_line(line.strip())
        self.paginator.add_line("")
        self.paginator.add_line(self.get_opening_note())
        await self.send_pages()


def setup(bot):
    bot.help_command = I18nHelpCommand()
