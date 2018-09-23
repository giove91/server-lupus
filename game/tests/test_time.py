
import sys
import datetime
import json
import os
import collections
import pytz
from functools import wraps

from django.utils import timezone

from django.test import TestCase

from game.constants import *
from game.utils import get_now, advance_to_time

from datetime import timedelta, datetime, time

class AdvanceTimeTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_advance(self):
        now = datetime(2015, 11, 11, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 11, 18, 0, 0), is_dst=None))

    def test_wrapped_advance(self):
        now = datetime(2015, 11, 11, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 12, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance(self):
        now = datetime(2015, 3, 28, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance(self):
        now = datetime(2015, 10, 24, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))

    def test_simple_advance_with_useless_skip(self):
        now = datetime(2015, 11, 11, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 11, 18, 0, 0), is_dst=None))

    def test_wrapped_advance_with_useless_skip(self):
        now = datetime(2015, 11, 11, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 12, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance_with_useless_skip(self):
        now = datetime(2015, 3, 28, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance_with_useless_skip(self):
        now = datetime(2015, 10, 24, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, )
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))

    def test_simple_advance_with_real_skip(self):
        now = datetime(2015, 11, 13, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 15, 18, 0, 0), is_dst=None))

    def test_wrapped_advance_with_real_skip(self):
        now = datetime(2015, 11, 12, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 15, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance_with_real_skip(self):
        now = datetime(2015, 3, 26, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance_with_real_skip(self):
        now = datetime(2015, 10, 22, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, allowed_weekdays=[0, 1, 2, 3, 6])
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))
