#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import datetime
import random

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")

import django
django.setup()

from .game.models import *
from .game.tests import *
from .game.utils import *
from .game.constants import *
from .game.letter_renderer import *

def main():
    game = Game.get_running_game()
    players = game.get_players()
    from .game.my_random import WichmannHill
    random = WichmannHill()
    random.seed(int(sys.argv[1]))
    for player in players:
        lr = LetterRenderer(player, random)
        lr.render_all()

if __name__ == '__main__':
    main()
