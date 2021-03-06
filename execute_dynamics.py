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
from game.dynamics import *

def main():
    set_debug_dynamics(True)

    game = Game.get_running_game()
    game.get_dynamics()

if __name__ == '__main__':
    main()
