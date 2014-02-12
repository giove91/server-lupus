# -*- coding: utf-8 -*-

import datetime

# FIXME: it probably failes when crossing DST
def advance_to_time(current_datetime, target_time):
    date = current_datetime.date()
    time = current_datetime.timetz()
    target_date = date
    if time >= target_time:
        target_date = date + datetime.timedelta(days=1)

    return datetime.datetime.combine(target_date, target_time)
