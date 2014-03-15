#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")
from game.models import *
from game.tests import *

def main():
    game = create_game_from_dump(json.load(sys.stdin))
    print >> sys.stdout, game.pk

if __name__ == '__main__':
    main()
