# -*- coding: utf-8 -*-

import datetime

from constants import *

def advance_to_time(current_datetime, target_time):
    """Return a datetime object that is strictly greater than
    current_datetime and has date part equal to target_time. All
    objects are supposed to be timezone-aware.

    The result is undefined (probably an exception will be thrown) if
    the result happens to be in the double or missing time interval
    that occur when changing DST."""
    current_datetime = current_datetime.astimezone(REF_TZINFO)
    date = current_datetime.date()
    time = current_datetime.timetz()
    target_date = date
    if time >= target_time:
        target_date = date + datetime.timedelta(days=1)

    return datetime.datetime.combine(target_date, target_time)
