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
from game.roles.v2 import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time

from datetime import timedelta, datetime, time

from .test_utils import create_game, delete_auto_users, create_users, create_game_from_dump, test_advance_turn, record_name

def create_test_game(seed, roles, sequence):
    game = create_game(seed, 'v2', roles)
    game.get_dynamics().inject_event(SpectralSequenceEvent(sequence=sequence, timestamp=get_now()))
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
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=guardia, multiple_role_class = {Divinatore, Guardia}))
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=veggente))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.cause, DEVIL)
        self.assertEqual(event.response, True)
        self.assertEqual(event.multiple_role_class, {Guardia, Divinatore})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, veggente)
        self.assertEqual(event.ghost, Delusione)
        self.assertEqual(veggente.team, NEGROMANTI)
        self.assertTrue(veggente.is_mystic)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Retest diavolo and make visione
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=guardia, multiple_role_class = {Negromante, Lupo, Veggente}))
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=veggente, role_class = Visione))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.cause, DEVIL)
        self.assertEqual(event.response, False)
        self.assertEqual(event.multiple_role_class, {Lupo, Negromante, Veggente})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertEqual(event.ghost, Visione)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Now test visione
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=guardia, multiple_role_class = {Negromante, Lupo, Veggente, Guardia}))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, guardia)
        self.assertEqual(event.cause, VISION_GHOST)
        self.assertEqual(event.response, True)
        self.assertEqual(event.multiple_role_class, {Guardia, Lupo, Negromante, Veggente})


    @record_name
    def test_spectral_succession(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Diavolo, Negromante ]
        self.game = create_test_game(1, roles, [True, False, True, True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [c1, c2, c3, c4, c5] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]

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
        self.assertEqual(event.ghost, Delusione)
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

        # Kill diavolo - nothing happens
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=diavolo))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(diavolo.team, LUPI)
        self.assertFalse(diavolo.role.ghost)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 3
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c3))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]

        self.assertEqual(event.player, c3)
        self.assertEqual(event.ghost, Delusione)
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
        self.assertEqual(event.ghost, Delusione)
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
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=veggente, role_class = Amnesia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertEqual(event.ghost, Amnesia)

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
        dynamics.inject_event(SoothsayerModelEvent(target=cacciatore, advertised_role=Veggente, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=negromante1, advertised_role=Guardia, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=lupo1, advertised_role=Contadino, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=contadino, advertised_role=Contadino, soothsayer=divinatore, timestamp=ref_timestamp))
        
        # Check
        events = [event for event in dynamics.debug_event_bin if isinstance(event, SoothsayerModelEvent)]
        self.assertEqual(len(events), 4)
        for e in events:
            self.assertEqual(e.soothsayer, divinatore)
        
        info = [(e.target, e.advertised_role) for e in events]
        self.assertTrue((negromante1, Guardia) in info)
        self.assertTrue((cacciatore, Veggente) in info)
        self.assertTrue((lupo1, Contadino) in info)
        self.assertTrue((contadino, Contadino) in info)

        test_advance_turn(self.game)

        # Test power
        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo1, role_class=Lupo))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        [] = [event for event in dynamics.debug_event_bin if isinstance(event, NegativeRoleKnowledgeEvent)]

        self.assertEqual(event.target, lupo1)
        self.assertEqual(event.role_class, Lupo)

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

        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo1, role_class=Contadino))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NegativeRoleKnowledgeEvent)]

        self.assertEqual(event.target, lupo1)
        self.assertEqual(event.role_class, Contadino)

    @record_name
    def test_alcolista(self):
        roles = [ Guardia, Veggente, Stalker, Lupo, Alcolista, Negromante ]
        self.game = create_test_game(2204, roles, [True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [alcolista] = [x for x in players if isinstance(x.role, Alcolista)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]

        test_advance_turn(self.game)

        self.assertTrue(alcolista.can_use_power())
        dynamics.inject_event(CommandEvent(player=alcolista, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=stalker, type=USEPOWER, target=alcolista))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Fail
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == alcolista]
        self.assertFalse(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(event.target, alcolista)
        self.assertEqual(event.target2, lupo)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertTrue(alcolista.can_use_power())
        dynamics.inject_event(CommandEvent(player=alcolista, type=USEPOWER, target=stalker))
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=guardia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Fail again
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == alcolista]
        self.assertFalse(event.success)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertTrue(alcolista.can_use_power())
        self.assertFalse(guardia.alive)
        dynamics.inject_event(CommandEvent(player=alcolista, type=USEPOWER, target=guardia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # And again
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == alcolista]
        self.assertFalse(event.success)

    @record_name
    def test_fattucchiera_and_confusione(self):
        roles = [ Guardia, Veggente, Lupo, Fattucchiera, Divinatore, Mago, Diavolo, Negromante ]
        self.game = create_test_game(2204, roles, [True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [divinatore] = [x for x in players if isinstance(x.role, Divinatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [mago] = [x for x in players if isinstance(x.role, Mago)]

        # Inserting Soothsayer propositions
        ref_timestamp = get_now()
        dynamics.inject_event(SoothsayerModelEvent(target=negromante, advertised_role=Veggente, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=negromante, advertised_role=Guardia, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=lupo, advertised_role=Contadino, soothsayer=divinatore, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(target=lupo, advertised_role=Lupo, soothsayer=divinatore, timestamp=ref_timestamp))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Make party at lupo's home
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=guardia))
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=lupo, multiple_role_class={Veggente, Messia, Stalker}))
        dynamics.inject_event(CommandEvent(player=mago, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo, role_class=Messia))
        dynamics.inject_event(CommandEvent(player=fattucchiera, type=USEPOWER, target=lupo, role_class=Messia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) if event.player == divinatore]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_class, Messia)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent) if event.player == diavolo]
        self.assertEqual(event.target, lupo)
        self.assertTrue(event.response)
        self.assertEqual(event.multiple_role_class, {Veggente, Messia, Stalker})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent) if event.player == veggente]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, WHITE)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent) if event.player == mago]
        self.assertEqual(event.target, lupo)
        self.assertTrue(event.is_mystic)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertTrue(fattucchiera.can_use_power())
        self.assertFalse(divinatore.can_use_power())

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Make another party, but don't invite Fattucchiera
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=guardia, role_class=Confusione))
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=lupo, multiple_role_class={Veggente, Messia, Stalker}))
        dynamics.inject_event(CommandEvent(player=mago, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo, role_class=Messia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Check that lupo has been sgamato
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NegativeRoleKnowledgeEvent) if event.player == divinatore]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_class, Messia)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent) if event.player == diavolo]
        self.assertEqual(event.target, lupo)
        self.assertFalse(event.response)
        self.assertEqual(event.multiple_role_class, {Veggente, Messia, Stalker})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent) if event.player == veggente]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, BLACK)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent) if event.player == mago]
        self.assertEqual(event.target, lupo)
        self.assertFalse(event.is_mystic)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Now confusione sneaks in
        dynamics.inject_event(CommandEvent(player=veggente, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=diavolo, type=USEPOWER, target=lupo, multiple_role_class={Veggente, Messia, Stalker}))
        dynamics.inject_event(CommandEvent(player=mago, type=USEPOWER, target=lupo))
        dynamics.inject_event(CommandEvent(player=divinatore, type=USEPOWER, target=lupo, role_class=Messia))
        dynamics.inject_event(CommandEvent(player=fattucchiera, type=USEPOWER, target=lupo, role_class=Messia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Now lupo is the new Messia (again)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) if event.player == divinatore]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_class, Messia)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MultipleRoleKnowledgeEvent) if event.player == diavolo]
        self.assertEqual(event.target, lupo)
        self.assertTrue(event.response)
        self.assertEqual(event.multiple_role_class, {Veggente, Messia, Stalker})

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent) if event.player == veggente]
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, WHITE)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent) if event.player == mago]
        self.assertEqual(event.target, lupo)
        self.assertTrue(event.is_mystic)

    @record_name
    def test_negromante(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Negromante, Negromante ]
        self.game = create_test_game(1, roles, [False, True, False, True, True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [c1, c2, c3, c4, c5] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 1: no spettri for negromante today!
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c1))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        self.assertEqual(c1.team, POPOLANI)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Negromante cannot do anything, so while he fails lupo kills him
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=negromante))
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=c1, role_class=Amnesia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]
        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == negromante]

        self.assertFalse(event.success)
        self.assertEqual(c1.team, POPOLANI)
        self.assertFalse(negromante.alive)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Now negromante is dead, and he's stronger than ever!
        dynamics.inject_event(CommandEvent(player=negromante, type=USEPOWER, target=c1, role_class=Amnesia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        [] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]

        self.assertEqual(event.player, c1)
        self.assertEqual(event.ghost, Amnesia)
        self.assertEqual(c1.team, NEGROMANTI)
        self.assertTrue(isinstance(c1.role, Amnesia))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # ... or not
        self.assertFalse(negromante.can_use_power())

    @record_name
    def test_negromanti_make_same_spettro(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Negromante, Negromante ]
        self.game = create_test_game(1, roles, [True, True])
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [c1, c2, c3, c4, c5] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [n1, n2] = [x for x in players if isinstance(x.role, Negromante)]

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 1
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c1))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        self.assertEqual(c1.team, NEGROMANTI)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Kill contadino 2
        dynamics.inject_event(CommandEvent(player=lupo, type=USEPOWER, target=c2))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        self.assertEqual(c2.team, NEGROMANTI)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Try to make two amnesie
        dynamics.inject_event(CommandEvent(player=n1, type=USEPOWER, target=c1, role_class=Amnesia))
        dynamics.inject_event(CommandEvent(player=n2, type=USEPOWER, target=c2, role_class=Amnesia))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [e1, e2] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertNotEqual(e1.success, e2.success)

        [_] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostSwitchEvent)]

        self.assertEqual({c1.role.__class__, c2.role.__class__}, {Amnesia, Delusione})

    @record_name
    def test_voyeur_with_illusione(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Guardia, Contadino, Voyeur ]
        self.game = create_test_game(1, roles, [True])
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, role_class=Illusione, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(contadino.role.ghost)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=guardia, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check that lupo is seen no more
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]

    @record_name
    def test_spettri_every_other_night(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Guardia, Contadino, Voyeur ]
        self.game = create_test_game(1, roles, [True])
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]

        # Advance to second night and kill guardia
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=guardia, timestamp=get_now()))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Make Spettro dell'Amnesia

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=guardia, role_class=Amnesia, timestamp=get_now()))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Use power and the change

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=guardia, role_class=Confusione, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=messia, timestamp=get_now()))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertFalse(guardia.can_use_power())

    @record_name
    def test_investigatore(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Guardia, Contadino, Voyeur, Investigatore ]
        self.game = create_test_game(1, roles, [True, False])
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]

        # Advance to second night and kill guardia
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=guardia, timestamp=get_now()))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Investigate

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=investigatore, target=guardia, timestamp=get_now()))
        dynamics.debug_event_bin = []

        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]

        self.assertEqual(event.target, guardia)
        self.assertEqual(event.player, investigatore)
        self.assertEqual(event.role_class, Guardia)
        self.assertTrue(isinstance(guardia.role, Delusione))
        self.assertEqual(guardia.team, NEGROMANTI)
