#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lupus.settings")
from game.models import *
from game.events import *

def main():
    data = {'players': [],
            'turns': []}
    game = Game.get_running_game()
    for player in Player.objects.filter(game=game):
        data['players'].append({'username': player.user.username})

    for turn in Turn.objects.filter(game=game).order_by('date', 'phase'):
        turn_data = {'events': []}
        for event in Event.objects.filter(turn=turn).order_by('timestamp', 'pk'):
            event = event.as_child()
            if not event.AUTOMATIC:
                turn_data['events'].append(event.to_dict())
        data['turns'].append(turn_data)

    json.dump(data, sys.stdout, indent=4)
    print >> sys.stdout

if __name__ == '__main__':
    main()
