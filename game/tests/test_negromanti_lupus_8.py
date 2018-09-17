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


    @record_name
    def test_spectral_succession(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Negromante ]
        self.game = create_test_game(1, roles, [True, False, True, True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [c1, c2, c3, c4, c5] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 1
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c1))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, c1)
        self.assertEqual(event.ghost, Delusione.name)
        self.assertEqual(c1.team, NEGROMANTI)
        self.assertFalse(c1.is_mystic)
        self.assertTrue(isinstance(c1.role, Delusione))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 2
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c2))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(c2.team, POPOLANI)
        self.assertFalse(c2.role.ghost)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 3
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c3))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, c3)
        self.assertEqual(event.ghost, Delusione.name)
        self.assertEqual(c3.team, NEGROMANTI)
        self.assertFalse(c3.is_mystic)
        self.assertTrue(isinstance(c3.role, Delusione))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 4
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c4))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, c4)
        self.assertEqual(event.ghost, Delusione.name)
        self.assertEqual(c4.team, NEGROMANTI)
        self.assertFalse(c4.is_mystic)
        self.assertTrue(isinstance(c4.role, Delusione))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 5
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c5))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(c5.team, POPOLANI)
        self.assertFalse(c5.role.ghost)

    @record_name
    def test_permanent_amnesia(self):
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

        # Kill veggente
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=veggente))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Make amnesia
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=veggente, target_role_name = Amnesia.name))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertEqual(event.ghost, Amnesia.name)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Now test amnesia
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=guardia))

        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=guardia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=guardia, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, MISSING_QUORUM)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertTrue(event.voter == lupo)
        self.assertTrue(event.voted == guardia)
        self.assertTrue(guardia.alive)

        #Recheck
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertEqual(self.game.current_turn.phase, DAY)
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=guardia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=guardia, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, MISSING_QUORUM)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertTrue(event.voter == lupo)
        self.assertTrue(event.voted == guardia)
        self.assertTrue(guardia.alive)

    @record_name
    def test_divinatore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Divinatore ]
        self.game = create_test_game(1, roles, [])
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo1, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [negromante1, negromante2] = [x for x in players if isinstance(x.role, Negromante)]
        [divinatore] = [x for x in players if isinstance(x.role, Divinatore)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        dynamics.debug_event_bin = []

        # Inserting Soothsayer propositions
        ref_timestamp = get_now()
        dynamics.inject_event(SoothsayerModelEvent(target=cacciatore, advertised_role=Veggente.name, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=negromante1, advertised_role=Guardia.name, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=lupo1, advertised_role=Contadino.name, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=contadino, advertised_role=Contadino.name, soothsayer=divinatore, timestamp=ref_timestamp))
        
        # Check
        events = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(len(events), 4)
        for e in events:
            self.assertEqual(e.player, divinatore)
        
        info = [(e.target, e.role_name) for e in events]
        self.assertTrue((negromante1, Guardia.name) in info)
        self.assertTrue((cacciatore, Veggente.name) in info)
        self.assertTrue((lupo1, Contadino.name) in info)
        self.assertTrue((contadino, Contadino.name) in info)

        test_advance_turn(self.game)

        # Test power
        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo1, target_role_name=Lupo.name))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        [] = [event for event in dynamics.debug_event_bin if isinstance(event, NegativeRoleKnowledgeEvent)]

        self.assertEqual(event.target, lupo1)
        self.assertEqual(event.role_name, Lupo.name)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Not every night...
        self.assertFalse(divinatore.can_use_power())

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Test again

        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo1, target_role_name=Contadino.name))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NegativeRoleKnowledgeEvent)]

        self.assertEqual(event.target, lupo1)
        self.assertEqual(event.role_name, Contadino.name)
