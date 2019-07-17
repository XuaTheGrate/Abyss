import os

BASE_DIR = os.path.dirname(__file__)

if __name__ == "__main__":
    from bot.bot import AdventureTwo
    AdventureTwo().run()
