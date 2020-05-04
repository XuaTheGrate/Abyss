import sys

from .bot import Abyss

if __name__ == '__main__':
    bot = Abyss(debug=sys.argv[-1] == '--debug')
    bot.loop.run_until_complete(bot.run_setup())
    bot.prepare_extensions()
    bot.run()
