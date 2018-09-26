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

from .test_utils import create_game, delete_auto_users, create_users, create_game_from_dump, test_advance_turn, record_name, GameTest

def create_test_game(seed, roles, sequence):
    game = create_game(seed, 'v2', roles)
    game.get_dynamics().inject_event(SpectralSequenceEvent(sequence=sequence, timestamp=get_now()))
    return game

class TestDiavoloAndVisione(GameTest, TestCase):
    roles = [ Guardia, Veggente, Lupo, Diavolo, Negromante ]
    spectral_sequence = [True]

    def test(self):
        self.advance_turn(NIGHT)

        # Test diavolo and kill veggente
        self.usepower(self.diavolo, self.guardia, multiple_role_class={Divinatore, Guardia})
        self.usepower(self.lupo, self.veggente)
        self.advance_turn()

        self.check_event(MultipleRoleKnowledgeEvent, {
            'player': self.diavolo,
            'cause': DEVIL,
            'response': True,
            'multiple_role_class': {Guardia, Divinatore}
        })

        self.check_event(GhostificationEvent, {
            'player': self.veggente,
            'ghost': Delusione
        })

        self.assertTrue(self.veggente.is_mystic)
        self.assertEqual(self.veggente.team, NEGROMANTI)
        self.advance_turn(NIGHT)

        # Retest diavolo and make visione
        self.usepower(self.diavolo, self.guardia, multiple_role_class={Negromante, Lupo, Veggente})
        self.usepower(self.negromante, self.veggente, role_class=Visione)
        self.advance_turn()

        self.check_event(MultipleRoleKnowledgeEvent, {
            'player': self.diavolo,
            'cause': DEVIL,
            'response': False,
            'multiple_role_class': {Lupo, Negromante, Veggente}
        })

        self.check_event(GhostSwitchEvent, {
            'player': self.veggente,
            'cause': NECROMANCER,
            'ghost': Visione,
        })

        self.advance_turn(NIGHT)

        #Now test visione
        self.usepower(self.veggente, self.guardia, multiple_role_class = {Negromante, Veggente, Lupo, Guardia})
        self.advance_turn()

        self.check_event(MultipleRoleKnowledgeEvent, {
            'player': self.veggente,
            'target': self.guardia,
            'cause': VISION_GHOST,
            'response': True,
            'multiple_role_class': {Guardia, Lupo, Negromante, Veggente}
        })

class TestSpectralSequence(GameTest, TestCase):
    roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Diavolo, Negromante ]
    spectral_sequence = [True, False, True, True]

    def test_succession(self):
        self.advance_turn(NIGHT)

        # Kill contadino_a
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn()

        # Check he is Spettro
        self.check_event(GhostificationEvent, {'player': self.contadino_a, 'ghost': Delusione})
        self.assertEqual(self.contadino_a.team, NEGROMANTI)
        self.assertFalse(self.contadino_a.is_mystic)
        self.assertTrue(isinstance(self.contadino_a.role, Delusione))

        self.advance_turn(NIGHT)

        # Kill contadino_b
        self.usepower(self.lupo, self.contadino_b)
        self.advance_turn()

        # Check he is not Spettro
        self.check_event(GhostificationEvent, None)
        self.assertEqual(self.contadino_b.team, POPOLANI)
        self.assertFalse(self.contadino_b.role.ghost)

        self.advance_turn(NIGHT)

        # Kill diavolo: nothing happens
        self.usepower(self.lupo, self.diavolo)
        self.advance_turn()

        self.check_event(GhostificationEvent, None)
        self.assertEqual(self.diavolo.team, LUPI)
        self.assertFalse(self.diavolo.role.ghost)

        self.advance_turn(NIGHT)

        # Kill contadino_c
        self.usepower(self.lupo, self.contadino_c)
        self.advance_turn()

        self.check_event(GhostificationEvent, {'player': self.contadino_c, 'ghost': Delusione})
        self.assertEqual(self.contadino_c.team, NEGROMANTI)
        self.assertTrue(isinstance(self.contadino_c.role, Delusione))

        self.advance_turn(NIGHT)

        # Kill contadino_d
        self.usepower(self.lupo, self.contadino_d)
        self.advance_turn()

        self.check_event(GhostificationEvent, {'player': self.contadino_d, 'ghost': Delusione})
        self.assertEqual(self.contadino_d.team, NEGROMANTI)
        self.assertTrue(isinstance(self.contadino_d.role, Delusione))

        self.advance_turn(NIGHT)

        # Kill contadino_e
        self.usepower(self.lupo, self.contadino_e)
        self.advance_turn()

        self.check_event(GhostificationEvent, None)
        self.assertEqual(self.contadino_e.team, POPOLANI)
        self.assertFalse(self.contadino_e.role.ghost)

class TestVotingSpettri(GameTest, TestCase):
    roles = [ Contadino, Guardia, Veggente, Spia, Messia, Esorcista, Lupo, Stregone, Fattucchiera, Negromante]
    spectral_sequence = [True, True, True]

    def test_permanent_amnesia(self):
        self.advance_turn(NIGHT)

        # Kill veggente
        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        # Make amnesia
        self.usepower(self.negromante, self.veggente, role_class=Amnesia)
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'player': self.veggente, 'cause': NECROMANCER, 'ghost': Amnesia})
        self.advance_turn(NIGHT)

        # Now test amnesia
        self.usepower(self.veggente, self.guardia)
        self.advance_turn(DAY)

        # Now vote
        self.vote(self.guardia, self.guardia)
        self.vote(self.lupo, self.guardia)
        self.vote(self.esorcista, self.guardia)
        self.vote(self.spia, self.guardia)
        self.vote(self.negromante, self.guardia)
        self.advance_turn()

        # Check sunset
        self.check_event(StakeFailedEvent, {'cause': MISSING_QUORUM})
        self.check_event(VoteAnnouncedEvent, None, voter=self.guardia)
        self.assertTrue(self.guardia.alive)
        self.advance_turn(DAY)

        #Recheck
        self.vote(self.guardia, self.guardia)
        self.vote(self.lupo, self.guardia)
        self.vote(self.esorcista, self.guardia)
        self.vote(self.spia, self.guardia)
        self.vote(self.negromante, self.guardia)
        self.advance_turn()

        # Guardia cannot vote still
        self.check_event(StakeFailedEvent, {'cause': MISSING_QUORUM})
        self.check_event(VoteAnnouncedEvent, None, voter=self.guardia)
        self.assertTrue(self.guardia.alive)


class TestDivinatore(GameTest, TestCase):
    roles = [ Negromante, Lupo, Contadino, Divinatore, Espansivo, Fattucchiera]
    spectral_sequence = [True]

    def test_divinatore(self):
        self.soothsayer_proposition(self.divinatore, self.espansivo, Veggente)
        self.soothsayer_proposition(self.divinatore, self.negromante, Guardia)
        self.soothsayer_proposition(self.divinatore, self.lupo, Contadino)
        self.soothsayer_proposition(self.divinatore, self.contadino, Contadino)

        # Check
        events = self.get_events(SoothsayerModelEvent)
        self.assertEqual(len(events), 4)
        for e in events:
            self.assertEqual(e.soothsayer, self.divinatore)

        self.assertEqual({(e.target, e.advertised_role) for e in events}, {
            (self.negromante, Guardia),
            (self.espansivo, Veggente),
            (self.contadino, Contadino),
            (self.lupo, Contadino)
        })

        self.advance_turn()

        # Test power
        self.usepower(self.divinatore, self.lupo, role_class=Lupo)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'target': self.lupo, 'role_class': Lupo})
        self.check_event(NegativeRoleKnowledgeEvent, None)
        self.advance_turn(NIGHT)

        # Not every night...
        self.assertFalse(self.divinatore.can_use_power())
        self.advance_turn(NIGHT)

        # Test again
        self.usepower(self.divinatore, self.lupo, role_class=Contadino)
        self.advance_turn()

        self.check_event(NegativeRoleKnowledgeEvent, {'target': self.lupo, 'role_class': Contadino})
        self.check_event(RoleKnowledgeEvent, None)

class TestAlcolista(GameTest, TestCase):
    roles = [ Guardia, Veggente, Stalker, Lupo, Alcolista, Negromante ]
    spectral_sequence = []

    def test_alcolista(self):
        self.assertTrue(self.alcolista.can_use_power())
        self.usepower(self.alcolista, self.lupo)
        self.usepower(self.stalker, self.alcolista)
        self.advance_turn()

        # Fail
        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.alcolista)
        self.check_event(MovementKnowledgeEvent, {'target': self.alcolista, 'target2': self.lupo})
        self.advance_turn(NIGHT)

        # Test again
        self.usepower(self.alcolista, self.stalker)
        self.usepower(self.lupo, self.guardia)
        self.advance_turn()

        # Fail again
        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.alcolista)
        self.advance_turn(NIGHT)

        self.assertFalse(self.guardia.alive)
        self.usepower(self.alcolista, self.guardia)
        self.advance_turn()

        # And again, even to deads
        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.alcolista)

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

    @record_name
    def test_spia(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Guardia, Spia, Contadino, Voyeur, Investigatore ]
        self.game = create_test_game(1, roles, [])
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [spia] = [x for x in players if isinstance(x.role, Spia)]

        # Vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=guardia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=messia, timestamp=get_now()))

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Now spy
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=spia, target=guardia, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteKnowledgeEvent)]
        self.assertEqual(event.voter, guardia)
        self.assertEqual(event.voted, negromante)
