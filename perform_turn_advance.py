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
    game = Game.get_running_game()

    # Fail without creating the turn if there are errors in the
    # dynamics
    game.get_dynamics()

    if 'set_end' in sys.argv[1:]:
        turn = game.current_turn
        if turn.end is None:
            turn.end = get_now()
            turn.save()

    game.advance_turn()

if __name__ == '__main__':
    main()
