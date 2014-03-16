#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")
from game.models import *
from game.tests import *
from game.utils import *
from game.constants import *

def main():
    start_moment = advance_to_time(get_now(), FIRST_PHASE_BEGIN_TIME)
    game = create_game_from_dump(json.load(sys.stdin), start_moment)
    print >> sys.stdout, game.pk

if __name__ == '__main__':
    main()
