"""Spherical astronomy math: calendar/epoch conversion and equatorial->horizontal
coordinates (Alt/Az). Pure math, no ctx/eventbus/app dependencies, so it can be
sanity-checked standalone with plain CPython.
"""
import math


def julian_date(year, month, day, hour, minute, second):
    """Meeus low-precision Julian Date, valid for the Gregorian calendar."""
    y, m = year, month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    ut = hour + minute / 60.0 + second / 3600.0
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5 + ut / 24.0


def epoch_from_calendar(year, month, day, hour, minute, second):
    """Unix epoch seconds, computed without time.mktime (unavailable in the sim)."""
    return (julian_date(year, month, day, hour, minute, second) - 2440587.5) * 86400.0


def jd_from_epoch(epoch_seconds):
    return epoch_seconds / 86400.0 + 2440587.5


def gmst_deg(jd):
    d = jd - 2451545.0
    return (280.46061837 + 360.98564736629 * d) % 360.0


def lst_deg(jd, lon_deg):
    return (gmst_deg(jd) + lon_deg) % 360.0


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def compute_altaz(sin_dec, cos_dec, sin_ra, cos_ra, sin_lst, cos_lst, sin_lat, cos_lat):
    """Alt/Az (degrees) for one star, given cached trig of its RA/Dec, the
    current LST, and the observer's latitude. Avoids extra sin/cos calls by
    deriving H = LST - RA via the angle-subtraction identity."""
    cos_h = cos_lst * cos_ra + sin_lst * sin_ra
    sin_h = sin_lst * cos_ra - cos_lst * sin_ra

    sin_alt = sin_dec * sin_lat + cos_dec * cos_lat * cos_h
    sin_alt = _clamp(sin_alt, -1.0, 1.0)
    alt = math.asin(sin_alt)
    cos_alt = math.cos(alt)

    if cos_alt < 1e-6 or cos_lat < 1e-6:
        return math.degrees(alt), 0.0

    cos_az = (sin_dec - sin_alt * sin_lat) / (cos_alt * cos_lat)
    cos_az = _clamp(cos_az, -1.0, 1.0)
    az = math.acos(cos_az)
    if sin_h > 0:
        az = 2 * math.pi - az

    return math.degrees(alt), math.degrees(az)


_DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def days_in_month(year, month):
    if month == 2 and (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0):
        return 29
    return _DAYS_IN_MONTH[month - 1]
