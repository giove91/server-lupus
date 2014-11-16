#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")

import django
django.setup()

from game.models import *
from game.tests import *
from game.utils import *
from game.constants import *

def main():
    for line in sys.stdin:
        name, email, username, gender = line.strip().split('\t')
        first_name, last_name = name.split(' ', 1)
        u = User(first_name=first_name, last_name=last_name, email=email, username=username, password='ciaociao')
        u.save()
        profile = Profile(gender=gender)
        u.profile = profile
        profile.save()
        u.save()

if __name__ == '__main__':
    main()
