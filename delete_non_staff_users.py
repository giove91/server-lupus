#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")

import django
django.setup()

from game.models import *
from game.tests import *

def main():
    delete_non_staff_users()

if __name__ == '__main__':
    main()
