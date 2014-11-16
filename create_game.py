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
    if 'observe_timings' in sys.argv[1:]:
        start_moment = advance_to_time(get_now(), FIRST_PHASE_BEGIN_TIME)
    else:
        start_moment = get_now()

    game = Game(running=True)
    game.save()
    game.initialize(start_moment)

    for user in User.objects.all():
        if user.is_staff:
            continue
        player = Player.objects.create(user=user, game=game)
        player.save()

    dynamics = game.get_dynamics()
    first_turn = dynamics.current_turn

    event = SeedEvent(seed=int(sys.argv[-1]))
    event.timestamp = first_turn.begin
    dynamics.inject_event(event)

    for line in sys.stdin:
        event = AvailableRoleEvent(role_name=line.strip())
        event.timestamp = first_turn.begin
        dynamics.inject_event(event)

    return game

if __name__ == '__main__':
    main()
