from datetime import datetime, timedelta

import numpy.random as np

from .enums import Weather, SevereWeather, Season
from .lookups import WIND_SPEED_SEASON, WIND_SPEED_WEATHER


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


def _now(d=None):
    now = d or datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def get_current_season(date=None):
    now = _now(date)
    if SPRING_START < now < SPRING_END:
        return Season.SPRING
    if SUMMER_START < now < SUMMER_END:
        return Season.SUMMER
    if AUTUMN_START < now < AUTUMN_END:
        return Season.AUTUMN
    if WINTER_START < now < WINTER_END:
        return Season.WINTER
    raise RuntimeError


def try_severe_weather(season, weather):
    if season is Season.SUMMER and weather is Weather.SUNNY:
        return np.random() < 0.5
    elif season is Season.WINTER and weather is Weather.SNOW:
        return np.random() < 0.45
    elif season is Season.SUMMER and weather is Weather.RAIN:
        return np.random() < 0.37
    return np.random() < 0.1


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

    now = _now(date)
    np.seed(int(now.timestamp()))
    weather = np.choice([w.value for w in Weather], p=chances)
    weather = Weather(weather)

    if weather is not Weather.FOGGY:
        do = try_severe_weather(season, weather)
        if do:
            return SevereWeather(weather.value)

    return weather


def get_wind_speed(date=None):  # KM/H
    now = _now(date)
    max_speed = 20

    season = get_current_season(now)
    max_speed += WIND_SPEED_SEASON[season]

    weather = get_current_weather(now)
    max_speed += WIND_SPEED_WEATHER[weather]

    np.seed(int(now.timestamp()))
    speed = np.randint(1, max(max_speed+1, 2))
    return speed-1
