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
from game.events import *

def main():
    g = Game.get_running_game()
    t = g.current_turn
    assert t.phase == CREATION
    for line in sys.stdin:
        line = line.split('#')[0].strip()
        if line == '':
            continue
        e = InitialPropositionEvent(turn=t, timestamp=t.begin, text=line)
        e.save()

if __name__ == '__main__':
    main()
