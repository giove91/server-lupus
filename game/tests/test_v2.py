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

from .test_utils import GameTest

class TestQuorum(GameTest, TestCase):
    roles = [Contadino, Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Lupo, Negromante]
    spectral_sequence = []

    def test_auto_vote(self):
        self.mass_vote([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], None)

    def test_quorum(self):
        self.mass_vote([0, 0, 0, 0, 0, 0], 0)

    def test_almost_quorum(self):
        self.mass_vote([0, 0, 0, 0, 0], None)

    def test_fifty_fifty(self):
        self.mass_vote([0, 1, 0, 1, 0, 1, 0, 1, 0, 1], None)

    def test_sixty_forty(self):
        self.mass_vote([0, 1, 0, 1, 0, 1, 0, 1, 0, 0], 0)


class TestFailures(GameTest, TestCase):
    roles = [Contadino, Stalker, Messia, Trasformista, Lupo, Assassino, Sequestratore, Stregone, Negromante]
    spectral_sequence = []

    def test_sorcered_stalker(self):
        self.usepower(self.stalker, self.lupo)
        self.usepower(self.stregone, self.lupo)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.stalker)
        self.advance_turn(NIGHT)

        self.assertTrue(self.stalker.can_use_power())

    def test_sequestered_stalker(self):
        self.usepower(self.stalker, self.lupo)
        self.usepower(self.sequestratore, self.stalker)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.stalker)
        self.advance_turn(NIGHT)

        self.assertTrue(self.stalker.can_use_power())

    def test_sequestered_assassin(self):
        self.assertFalse(self.assassino.can_use_power())
        self.advance_turn(NIGHT)

        self.usepower(self.assassino, self.lupo)
        self.usepower(self.sequestratore, self.assassino)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.assassino)
        self.advance_turn(NIGHT)

        self.assertTrue(self.assassino.can_use_power())

    def test_sequestered_messia(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.messia, self.contadino)
        self.usepower(self.sequestratore, self.messia)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.messia)
        self.assertFalse(self.contadino.alive)
        self.advance_turn(NIGHT)

        self.usepower(self.messia, self.contadino)
        self.advance_turn()

        self.assertTrue(self.contadino.alive)

    def test_sequestered_trasformista(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.sequestratore, self.trasformista)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.trasformista)
        self.assertIsInstance(self.trasformista.role, Trasformista)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.advance_turn()

        self.assertIsInstance(self.trasformista.role, Contadino)

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
    roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Lupo, Diavolo, Negromante, Negromante ]
    spectral_sequence = [True, False, True, True]

    def test_sequence(self):
        self.advance_turn(NIGHT)

        # Kill contadino_a
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn()

        # Check he is Spettro
        self.check_event(GhostificationEvent, {'player': self.contadino_a, 'ghost': Delusione})
        self.assertEqual(self.contadino_a.team, NEGROMANTI)
        self.assertFalse(self.contadino_a.is_mystic)
        self.assertTrue(isinstance(self.contadino_a.role, Delusione))
        self.check_event(RoleKnowledgeEvent, {'role_class': Negromante, 'cause': GHOST}, player=self.contadino_a, target=self.negromante_a)
        self.check_event(RoleKnowledgeEvent, {'role_class': Negromante, 'cause': GHOST}, player=self.contadino_a, target=self.negromante_b)
        self.check_event(RoleKnowledgeEvent, {'target': self.contadino_a, 'role_class': Delusione, 'cause': SPECTRAL_SEQUENCE}, player=self.negromante_a)
        self.check_event(RoleKnowledgeEvent, {'target': self.contadino_a, 'role_class': Delusione, 'cause': SPECTRAL_SEQUENCE}, player=self.negromante_b)

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

    def test_negromante(self):
        self.advance_turn(NIGHT)

        # Kill contadino_a => becomes spettro
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_a, role_class=Amnesia)
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'player': self.contadino_a, 'ghost': Amnesia})
        self.assertTrue(isinstance(self.contadino_a.role, Amnesia))
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_a, role_class=Confusione)
        self.assertNotIn(Amnesia, self.negromante_a.role.get_targets_role_class())
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'player': self.contadino_a, 'ghost': Confusione})
        self.assertIsInstance(self.contadino_a.role, Confusione)
        self.advance_turn(NIGHT)

        # Kill contadino_b => doesn't become spettro
        self.usepower(self.lupo, self.contadino_b)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_b, role_class=Amnesia)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'player': self.negromante_a, 'success': False})
        self.advance_turn(NIGHT)

        # Kill Negromante
        self.usepower(self.lupo, self.negromante_a)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_b, role_class=Amnesia)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'player': self.negromante_a, 'success': True})
        self.check_event(GhostificationEvent, {'player': self.contadino_b, 'ghost': Amnesia})

        self.advance_turn(NIGHT)
        self.assertFalse(self.negromante_a.can_use_power())

    def test_negromanti_make_same_spettro(self):
        self.advance_turn(NIGHT)

        # Kill contadini
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino_b)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino_c)
        self.advance_turn(NIGHT)

        self.assertEqual(self.contadino_a.team, NEGROMANTI)
        self.assertEqual(self.contadino_b.team, POPOLANI)
        self.assertEqual(self.contadino_c.team, NEGROMANTI)

        # Try to make confusione and visione
        self.usepower(self.negromante_a, target=self.contadino_a, role_class=Confusione)
        self.usepower(self.negromante_b, target=self.contadino_c, role_class=Visione)
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'ghost': Confusione}, player=self.contadino_a)
        self.check_event(GhostSwitchEvent, {'ghost': Visione}, player=self.contadino_c)
        self.advance_turn(NIGHT)

        # Try to make two amnesia
        self.usepower(self.negromante_a, target=self.contadino_a, role_class=Amnesia)
        self.usepower(self.negromante_b, target=self.contadino_c, role_class=Amnesia)
        self.advance_turn()

        good_n = self.get_events(PowerSuccessEvent, success=True)[0].player
        bad_n =self.get_events(PowerSuccessEvent, success=False)[0].player

        amnesia = self.contadino_a if good_n == self.negromante_a else self.contadino_c
        not_amnesia = self.contadino_a if bad_n == self.negromante_a else self.contadino_c

        self.check_event(GhostSwitchEvent, {'player': amnesia, 'ghost': Amnesia})
        self.assertIsInstance(amnesia.role, Amnesia)
        self.assertNotIsInstance(not_amnesia.role, Amnesia)

    def test_spettri_every_other_night(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        # Make Spettro dell'Amnesia
        self.usepower(self.negromante_a, self.contadino_a, role_class=Amnesia)
        self.advance_turn(NIGHT)

        # Use power and then change
        self.usepower(self.contadino_a, self.diavolo)
        self.usepower(self.negromante_a, self.contadino_a, role_class=Confusione)
        self.advance_turn(NIGHT)

        # Cannot use power
        self.assertIsInstance(self.contadino_a.role, Confusione)
        self.assertFalse(self.contadino_a.can_use_power())
        self.advance_turn(NIGHT)

        # Now he can
        self.usepower(self.contadino_a, self.diavolo, role_class=Negromante)
        self.advance_turn(NIGHT)

        # And he can again
        self.assertTrue(self.contadino_a.can_use_power())

class TestVotingPowers(GameTest, TestCase):
    roles = [ Contadino, Guardia, Veggente, Spia, Messia, Esorcista, Lupo, Stregone, Fattucchiera, Negromante]
    spectral_sequence = [True, True, True]

    def test_spia(self):
        self.check_phase(NIGHT)
        self.assertFalse(self.spia.can_use_power())
        self.advance_turn(DAY)

        self.vote(self.messia, self.guardia)
        self.vote(self.guardia, self.negromante)
        self.vote(self.negromante, self.lupo)
        self.vote(self.lupo, self.messia)
        self.advance_turn(NIGHT)

        # Now spy
        self.usepower(self.spia, self.guardia)
        self.advance_turn()

        self.check_event(VoteKnowledgeEvent, {'voter': self.guardia, 'voted': self.negromante, 'player': self.spia})

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

    def test_assoluzione(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Assoluzione)
        self.advance_turn(NIGHT)

        self.usepower(self.contadino, self.negromante)
        self.advance_turn(DAY)

        # Assoluzione is in place
        self.vote(self.veggente, self.negromante)
        self.vote(self.lupo, self.negromante)
        self.vote(self.spia, self.negromante)
        self.vote(self.messia, self.negromante)
        self.vote(self.esorcista, self.negromante)
        self.vote(self.fattucchiera, self.negromante)
        self.vote(self.negromante, self.lupo)
        self.advance_turn()

        self.check_event(StakeFailedEvent, {'cause': MISSING_QUORUM})
        self.check_event(VoteAnnouncedEvent, {'voter': self.negromante, 'voted': self.lupo})
        self.assertTrue(self.negromante.alive)
        self.advance_turn(NIGHT)

        self.assertFalse(self.contadino.can_use_power())
        self.usepower(self.spia, self.veggente)
        self.advance_turn()

        self.check_event(VoteKnowledgeEvent, {'player': self.spia, 'voter': self.veggente, 'voted': None})
        self.advance_turn(DAY)

        # Now assoluzione should be gone
        self.vote(self.veggente, self.negromante)
        self.vote(self.lupo, self.negromante)
        self.vote(self.spia, self.negromante)
        self.vote(self.messia, self.negromante)
        self.vote(self.esorcista, self.negromante)
        self.vote(self.fattucchiera, self.negromante)
        self.vote(self.negromante, self.lupo)
        self.advance_turn()

        self.check_event(PlayerDiesEvent, {'player': self.negromante})
        self.advance_turn()

        self.usepower(self.spia, self.veggente)
        self.advance_turn()

        self.check_event(VoteKnowledgeEvent, {'player': self.spia, 'voter': self.veggente, 'voted': self.negromante})

    def test_diffamazione(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Diffamazione)
        self.advance_turn(NIGHT)

        self.usepower(self.contadino, self.veggente)
        self.advance_turn(SUNSET)

        self.check_event(PlayerDiesEvent, {'player': self.veggente, 'cause': STAKE})
        votes = self.get_events(VoteAnnouncedEvent)
        self.assertEqual(len(votes), 9)
        for vote in votes:
            self.check_event(vote, {'voted': self.veggente})

    def test_diffamazione_and_assoluzione(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Diffamazione)
        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Assoluzione)
        self.advance_turn(NIGHT)

        self.usepower(self.contadino, self.lupo)
        self.usepower(self.veggente, self.negromante)
        self.advance_turn(DAY)

        self.burn(self.negromante)
        self.advance_turn()

        self.check_event(PlayerDiesEvent, {'player': self.lupo, 'cause': STAKE})
        votes = self.get_events(VoteAnnouncedEvent)
        self.assertEqual(len(votes), 8)
        for vote in votes:
            self.check_event(vote, {'voted': self.lupo})

        self.advance_turn()

        self.usepower(self.spia, self.guardia)
        self.advance_turn()

        self.check_event(VoteKnowledgeEvent, {'voter': self.guardia, 'voted': self.lupo, 'player': self.spia})

    def test_amnesia_and_diffamazione(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Diffamazione)
        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Amnesia)
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.guardia)
        self.usepower(self.contadino, self.lupo)
        self.advance_turn(DAY)

        self.autovote()
        self.advance_turn()

        votes = self.get_events(VoteAnnouncedEvent, voted=self.lupo)
        self.assertEqual(len(votes), 2)

        self.check_event(VoteAnnouncedEvent, {'voted': self.lupo}, voter=self.guardia)

class TestRoleKnowledge(GameTest, TestCase):
    roles = [ Negromante, Lupo, Contadino, Divinatore, Investigatore, Espansivo, Diavolo, Fattucchiera]
    spectral_sequence = [True]

    def setUp(self):
        super().setUp()
        self.soothsayer_proposition(self.divinatore, self.espansivo, Veggente)
        self.soothsayer_proposition(self.divinatore, self.negromante, Guardia)
        self.soothsayer_proposition(self.divinatore, self.lupo, Contadino)
        self.soothsayer_proposition(self.divinatore, self.contadino, Contadino)

    def test_divinatore(self):
        # Check soothsayer models
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

    def test_divinatore_with_fattucchiera(self):
        self.advance_turn(NIGHT)
        self.usepower(self.divinatore, self.lupo, role_class=Negromante)
        self.usepower(self.fattucchiera, self.lupo, role_class=Negromante)

        self.advance_turn()
        self.check_event(RoleKnowledgeEvent, {'player': self.divinatore, 'target': self.lupo, 'role_class': Negromante})
        self.check_event(NegativeRoleKnowledgeEvent, None)

        self.advance_turn(NIGHT)
        self.advance_turn(NIGHT)
        self.usepower(self.divinatore, self.lupo, role_class=Lupo)
        self.usepower(self.fattucchiera, self.lupo, role_class=Negromante)

        self.advance_turn()
        self.check_event(NegativeRoleKnowledgeEvent, {'player': self.divinatore, 'target': self.lupo, 'role_class': Lupo})
        self.check_event(RoleKnowledgeEvent, None)

    def test_investigatore_and_fattucchiera(self):
        self.advance_turn(NIGHT)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.investigatore, self.contadino)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.investigatore, 'target': self.contadino, 'role_class': Contadino})
        self.advance_turn(NIGHT)
        self.advance_turn(NIGHT)

        self.usepower(self.investigatore, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Negromante)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.investigatore, 'target': self.contadino, 'role_class': Negromante})

    def test_investigatore_on_spettro(self):
        self.advance_turn(NIGHT)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Amnesia)
        self.advance_turn(NIGHT)

        self.usepower(self.investigatore, self.contadino)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.investigatore, 'target': self.contadino, 'role_class': Contadino})
        self.assertTrue(isinstance(self.contadino.role, Amnesia))

    def test_divinatore_and_investigatore_with_confusione(self):
        self.advance_turn(NIGHT)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Confusione)
        self.advance_turn(NIGHT)

        self.usepower(self.divinatore, self.espansivo, role_class=Negromante)
        self.usepower(self.contadino, self.espansivo, role_class=Negromante)
        self.usepower(self.lupo, self.espansivo)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.divinatore, 'target': self.espansivo, 'role_class': Negromante})
        self.advance_turn(NIGHT)

        self.usepower(self.contadino, self.espansivo, role_class=Negromante)
        self.usepower(self.investigatore, self.espansivo)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.investigatore, 'target': self.espansivo, 'role_class': Negromante})
        self.advance_turn(NIGHT)

        self.assertFalse(self.investigatore.can_use_power())
        self.advance_turn(NIGHT)

        self.usepower(self.investigatore, self.espansivo)
        self.advance_turn()

        self.check_event(RoleKnowledgeEvent, {'player': self.investigatore, 'target': self.espansivo, 'role_class': Espansivo})

class TestTrasformista(GameTest, TestCase):
    roles = [Contadino, Massone, Massone, Trasformista, Messia, Lupo, Fattucchiera, Negromante]
    spectral_sequence = [True]

    def test_trasformista_on_massone(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.massone_a)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.massone_a)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.massone_a, 'role_class': Massone})
        self.assertIsInstance(self.trasformista.role, Massone)
        self.check_event(RoleKnowledgeEvent, None) # Doesn't know other massoni

        self.advance_turn(NIGHT)
        self.assertFalse(self.trasformista.can_use_power())

    def test_trasformista_on_fake_messia(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Divinatore)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.contadino, 'role_class': Messia})
        self.assertIsInstance(trasformista.role, Messia)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.advance_turn()

        # Reiso Deddo
        self.check_event(PlayerResurrectsEvent, {'player': self.contadino})
        self.assertTrue(self.contadino.alive)
        self.advance_turn(NIGHT)

        self.assertFalse(self.trasformista.can_use_power())

    def test_trasformista_on_fake_trasformista(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Trasformista)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.contadino, 'role_class': Trasformista})
        self.assertIsInstance(trasformista.role, Trasformista)
        self.advance_turn(NIGHT)

        # Repeat
        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Trasformista)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.contadino, 'role_class': Trasformista})
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.contadino, 'role_class': Contadino})
        self.assertIsInstance(trasformista.role, Contadino)
        self.advance_turn(NIGHT)

        self.assertFalse(self.trasformista.can_use_power())

    def trasformista_on_fake_lupo(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Lupo)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.trasformista)
        self.check_event(TrasformationEvent, None)
        self.assertIsInstance(self.trasformista.role, Trasformista)
        self.advance_turn(NIGHT)

        # Since he failed, he can retry
        self.assertTrue(trasformista.can_use_power())

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

class TestMovements(GameTest, TestCase):
    roles = [Contadino, Stalker, Voyeur, Guardia, Assassino, Alcolista, Stregone, Sequestratore, Lupo, Negromante]
    spectral_sequence = [True]

    def setUp(self):
        # Automatically make Illusione
        super().setUp()
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Illusione)
        self.advance_turn(NIGHT)

    def test_voyeur_with_illusione(self):
        self.usepower(self.contadino, self.lupo, target2=self.guardia)
        self.usepower(self.voyeur, self.stregone)
        self.usepower(self.lupo, self.stregone)
        self.advance_turn()

        # Check that lupo is seen no more
        self.check_event(NoMovementKnowledgeEvent, {'player': self.voyeur, 'target': self.stregone})
        self.check_event(MovementKnowledgeEvent, None)

    def test_voyeur_sees_himself(self):
        self.usepower(self.contadino, self.voyeur, target2=self.stregone)
        self.usepower(self.voyeur, self.stregone)
        self.advance_turn()

        self.check_event(MovementKnowledgeEvent, {'player': self.voyeur, 'target': self.stregone, 'target2': self.voyeur})


class TestTelepatia(GameTest, TestCase):
    roles = [Contadino, Veggente, Mago, Stalker, Voyeur, Espansivo, Lupo, Diavolo, Alcolista, Negromante]
    spectral_sequence = [True]

    def setUp(self):
        # Automatically make Telepatia
        super().setUp()
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Telepatia)
        self.advance_turn(NIGHT)

    def test_telepatia_on_veggente(self):
        self.usepower(self.veggente, self.lupo)
        self.usepower(self.mago, self.lupo)
        self.usepower(self.contadino, self.veggente)
        self.advance_turn()

        [event1, event2] = self.get_events(TelepathyEvent)
        self.check_event(event1, {'player': self.contadino})
        event = event1.perceived_event
        self.assertIsInstance(event, PowerOutcomeEvent)
        self.check_event(event, {'player': self.veggente, 'success': True})
        self.assertEqual(event.command.target, self.lupo)

        self.check_event(event2, {'player': self.contadino})
        event = event2.perceived_event
        self.assertIsInstance(event, AuraKnowledgeEvent)
        self.check_event(event, {'player': self.veggente, 'target': self.lupo, 'aura': BLACK, 'cause': SEER})
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.diavolo)
        self.assertFalse(self.contadino.can_use_power())
        self.advance_turn()

        self.check_event(TelepathyEvent, None)

    def test_telepatia_on_mago(self):
        self.usepower(self.veggente, self.lupo)
        self.usepower(self.mago, self.lupo)
        self.usepower(self.contadino, self.mago)
        self.advance_turn()

        [_, event] = self.get_events(TelepathyEvent)
        self.check_event(event, {'player': self.contadino})
        event = event.perceived_event
        self.assertIsInstance(event, MysticityKnowledgeEvent)
        self.check_event(event, {'player': self.mago, 'target': self.lupo, 'is_mystic': False, 'cause': MAGE})

    def test_telepatia_on_alcolista(self):
        self.usepower(self.alcolista, self.veggente)
        self.usepower(self.contadino, self.alcolista)
        self.advance_turn()

        [event] = self.get_events(TelepathyEvent)
        self.check_event(event, {'player': self.contadino})
        event = event.perceived_event
        self.check_event(event, {'player': self.alcolista, 'success': False, 'sequestrated': False})
        self.assertEqual(event.command.target, self.veggente)

    def telepatia_on_non_moving_player(self):
        self.usepower(self.contadino, self.alcolista)
        self.advance_turn()

        self.check_event(TelepathyEvent, None)

    def telepatia_on_expansived_player(self):
        self.usepower(self.contadino, self.lupo)
        self.usepower(self.espansivo, self.lupo)
        self.advance_turn()

        [event] = self.get_events(TelepathyEvent)
        self.check_event(event, {'player': self.contadino})
        event = event.perceived_event
        self.assertIsInstance(event, RoleKnowledgeEvent)
        self.check_event(event, {'player': self.lupo, 'target': self.espansivo, 'role_class': Espansivo, 'cause': EXPANSIVE})

    def test_telepatia_on_diavolo(self):
        self.usepower(self.diavolo, self.veggente, multiple_role_class={Veggente, Stalker})
        self.usepower(self.contadino, self.diavolo,)
        self.advance_turn()

        [_, event] = self.get_events(TelepathyEvent)
        self.check_event(event, {'player': self.contadino})
        event = event.perceived_event
        self.assertIsInstance(event, MultipleRoleKnowledgeEvent)
        self.check_event(event, {'player': self.diavolo, 'target': self.veggente, 'response': True, 'multiple_role_class': {Stalker, Veggente}, 'cause': DEVIL})
