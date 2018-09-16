import sys
import datetime
import json
import os
import collections
import pytz
from functools import wraps

from django.utils import timezone

from django.test import TestCase

from game.models import *
from game.roles.negromanti_lupus_8 import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time

from datetime import timedelta, datetime, time

from .test_utils import create_game, delete_auto_users, create_users, create_game_from_dump, test_advance_turn, record_name

def create_test_game(seed, roles, sequence):
    game = create_game(seed, 'negromanti_lupus_8', roles)
    game.get_dynamics().inject_event(SpectralSequenceEvent(sequence=sum([x*2**i for i, x in enumerate(sequence)])
, timestamp=get_now()))
    return game

class GameTests(TestCase):

    def setUp(self):
        self._name = None

    def tearDown(self):
        # Save a dump of the test game
        if 'game' in self.__dict__:
            with open(os.path.join('test_dumps', '%s.json' % (self._name)), 'w') as fout:
                pass #dump_game(self.game, fout)

        # Destroy the leftover dynamics without showing the slightest
        # sign of mercy
        kill_all_dynamics()

    @record_name
    def test_diavolo_and_visione(self):
        roles = [ Guardia, Veggente, Lupo, Diavolo, Negromante ]
        self.game = create_test_game(2204, roles, [True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Test diavolo and kill veggente
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=guardia, target_role_bisection = {Divinatore.name, Guardia.name}))
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=veggente))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleBisectionKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.cause, DEVIL)
        self.assertEqual(event.response, True)
        self.assertEqual(event.role_bisection, {"Guardia del corpo", "Divinatore"})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, veggente)
        self.assertEqual(event.ghost, Delusione.name)
        self.assertEqual(veggente.team, NEGROMANTI)
        self.assertTrue(veggente.is_mystic)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Retest diavolo and make visione
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=guardia, target_role_bisection = {"Negromante", "Lupo", "Veggente"}))
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=veggente, target_role_name = Visione.name))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleBisectionKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.cause, DEVIL)
        self.assertEqual(event.response, False)
        self.assertEqual(event.role_bisection, {"Lupo", "Negromante", "Veggente"})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertEqual(event.ghost, Visione.name)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Now test visione
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=guardia, target_role_bisection = {"Negromante", "Lupo", "Veggente", "Guardia del corpo"}))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleBisectionKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, guardia)
        self.assertEqual(event.cause, VISION_GHOST)
        self.assertEqual(event.response, True)
        self.assertEqual(event.role_bisection, {"Guardia del corpo", "Lupo", "Negromante", "Veggente"})

