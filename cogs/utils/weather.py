import random
from datetime import datetime

from .enums import Weather, SevereWeather, Season
from .lookups import WIND_SPEED_SEASON, WIND_SPEED_WEATHER


def get_year():
    return datetime.utcnow().timetuple().tm_yday


VARIATE = [  # base chances
    0.33,  # sunny
    0.45,  # cloudy
    0.15,  # rain
    0.05,  # snow
    0.02   # fog
]

SPRING = range(80, 172)
SUMMER = range(172, 264)
AUTUMN = range(264, 355)


def _now(d=None):
    if not d:
        return get_year()
    return d.timetuple().tm_yday


def get_current_season(date=None):
    now = _now(date)
    if now in SPRING:
        return Season.SPRING
    if now in SUMMER:
        return Season.SUMMER
    if now in AUTUMN:
        return Season.AUTUMN
    return Season.WINTER


def try_severe_weather(season, weather, state=None):
    rng = state or random
    if season is Season.SUMMER and weather is Weather.SUNNY:
        return rng.random() < 0.5
    elif season is Season.WINTER and weather is Weather.SNOW:
        return rng.random() < 0.45
    elif season is Season.SUMMER and weather is Weather.RAIN:
        return rng.random() < 0.37
    return rng.random() < 0.1


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

    now = date or datetime.utcnow()
    dt = datetime(now.year, now.month, now.day)
    nrand = random.Random(int(dt.timestamp()))
    weather = nrand.choices([w.value for w in Weather], cum_weights=chances)[0]
    weather = Weather(weather)

    if weather is not Weather.FOGGY:
        do = try_severe_weather(season, weather, state=nrand)
        if do:
            return SevereWeather(weather.value)

    return weather


def get_wind_speed(date=None):  # KM/H
    now = date or datetime.utcnow()
    dt = datetime(now.year, now.month, now.day)
    min_speed = 1
    max_speed = 20

    season = get_current_season(now)
    min_speed += WIND_SPEED_SEASON[season]
    max_speed += WIND_SPEED_SEASON[season]

    weather = get_current_weather(now)
    min_speed += WIND_SPEED_WEATHER[weather]
    max_speed += WIND_SPEED_WEATHER[weather]

    nrand = random.Random(int(dt.timestamp()))
    speed = nrand.randint(max(min_speed + 1, 1), max(max_speed + 1, 1))
    return speed-1
