#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")

import django
django.setup()

from game.models import *

def main():
    game = Game.get_running_game()
    dump_game(game, sys.stdout)
    print >> sys.stdout

if __name__ == '__main__':
    main()
