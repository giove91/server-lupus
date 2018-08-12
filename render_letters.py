#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Uso:
$ ./render_letters.py <game_name>
Crea e compila le lettere da mandare ai giocatori.
"""

import sys
import os
import json
import datetime
import random

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")

import django
django.setup()

from game.models import *
from game.tests import *
from game.utils import *
from game.constants import *
from game.letter_renderer import *

def main():
    game = Game.objects.get(name=sys.argv[1])
    players = game.get_players()
    for player in players:
        lr = LetterRenderer(player)
        lr.render_all()

if __name__ == '__main__':
    main()
