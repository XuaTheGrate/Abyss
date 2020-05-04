import logging
from logging.handlers import TimedRotatingFileHandler


def inject():
    import os
    try:
        os.mkdir("logs")
    except FileExistsError:
        pass
    finally:
        del os
    log = logging.getLogger("Abyss")
    fmt = "[%(asctime)s %(name)s/%(levelname)s]: %(message)s"
    datefmt = "%H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file = TimedRotatingFileHandler("logs/abyss.log", when="D", encoding='UTF-8', delay=True)
    file.setFormatter(formatter)
    log.handlers = [stream, file]

    dlog = logging.getLogger("discord")
    dlog.setLevel(logging.INFO)
    file = TimedRotatingFileHandler("discord.log", when="D", encoding='UTF-8', delay=True)
    file.setFormatter(formatter)
    dlog.handlers = [file]
