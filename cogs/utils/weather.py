from datetime import datetime, timedelta

import numpy.random as np

from .enums import Weather, SevereWeather, Season


_CURRENT_YEAR = datetime.utcnow().year

VARIATE = [  # base chances
    0.33,  # sunny
    0.45,  # cloudy
    0.15,  # rain
    0.05,  # snow
    0.02   # fog
]

SPRING_START = datetime(_CURRENT_YEAR, 3, 20)
SPRING_END = SUMMER_START = datetime(_CURRENT_YEAR, 6, 21)
SUMMER_END = AUTUMN_START = datetime(_CURRENT_YEAR, 9, 23)
AUTUMN_END = WINTER_START = datetime(_CURRENT_YEAR, 12, 22)
WINTER_END = SPRING_START + timedelta(days=365)


def _now():
    _now = datetime.utcnow()
    return datetime(_now.year, _now.month, _now.day)


def get_current_season():
    now = _now()
    if SPRING_START < now < SPRING_END:
        return Season.SPRING
    if SUMMER_START < now < SUMMER_END:
        return Season.SUMMER
    if AUTUMN_START < now < AUTUMN_END:
        return Season.AUTUMN
    if WINTER_START < now < WINTER_END:
        return Season.WINTER
    raise RuntimeError


# noinspection PyArgumentList
def get_current_weather(date=None):
    season = get_current_season()
    chances = VARIATE.copy()

    if season is Season.SPRING:
        chances[0] -= 0.1  # less sun
        chances[1] += 0.1  # more cloud
        chances[3] -= 0.04  # less snow
        chances[4] += 0.04  # more fog
    elif season is Season.SUMMER:
        chances[1] -= 0.3  # much less cloud
        chances[2] += 0.35  # much more rain
        chances[3] = 0.0  # no snow
    elif season is Season.AUTUMN:
        chances[3] = 0.1  # no fog or rare snow
        chances[4] = 0.0
        chances[2] += 0.06  # more rain
    elif season is Season.WINTER:
        chances[0] -= 0.3  # much less sun
        chances[1] += 0.15  # slightly more clouds
        chances[2] = 0.01  # rare rain
        chances[3] += 0.29  # more snow

    now = date or _now()
    np.seed(int(now.timestamp()))
    weather = np.choice([w.value for w in Weather], p=chances)
    weather = Weather(weather)
    if weather is not Weather.FOGGY and np.random() < 0.1:
        return SevereWeather(weather.value)
    return weather
