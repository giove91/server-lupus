# -*- coding: utf-8 -*-

import datetime

from .constants import *

def advance_to_time(current_datetime, target_time, allowed_weekdays=None):
    """Return the smallest datetime object that is strictly greater than
    current_datetime and has time part equal to target_time. All
    objects are supposed to be timezone-aware.

    An exception will be thrown if the result happens to be in the
    double or missing time interval that occur when changing DST.

    """
    assert current_datetime is not None
    current_datetime = REF_TZINFO.normalize(current_datetime)
    date = current_datetime.date()
    time = current_datetime.time()
    target_date = date
    if time >= target_time:
        target_date = date + datetime.timedelta(days=1)
    if allowed_weekdays is not None:
        if allowed_weekdays == []:
            return None
        while target_date.weekday() not in allowed_weekdays:
            target_date += datetime.timedelta(days=1)
    target_datetime = datetime.datetime.combine(target_date, target_time)
    assert target_datetime.tzinfo is None
    target_datetime = REF_TZINFO.localize(target_datetime, is_dst=None)
    return target_datetime

def get_now():
    return REF_TZINFO.normalize(datetime.datetime.now(tz=REF_TZINFO))

def dir_dict(list_):
    return dict(list(list_) + [(None, None)])

def rev_dict(list_):
    return dict([(y, x) for (x, y) in list(list_) + [(None, None)]])
