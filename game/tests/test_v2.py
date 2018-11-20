import sys
import datetime
import json
import os
import collections
import pytz
from functools import wraps

from django.utils import timezone

from django.test import TestCase, Client

from game.models import *
from game.roles.v2 import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time

from datetime import timedelta, datetime, time

from .test_utils import GameTest

class TestWebInterface(GameTest, TestCase):
    roles = [Contadino, Veggente, Stalker, Lupo, Diavolo, Negromante]
    spectral_sequence = [True]

    def test_simple_target(self):
        self.advance_turn(NIGHT)

        c = Client()
        c.force_login(self.veggente.user)
        response = c.get('/game/test/usepower/')
        self.assertEqual(response.context['form'].fields.keys(), {'target'})

        response = c.post('/game/test/usepower/', {'target': self.lupo.user.pk})
        self.assertEqual(response.status_code, 200)

        self.advance_turn()
        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'target': self.lupo})

    def test_double_target(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Illusione)
        self.advance_turn(NIGHT)

        c = Client()
        c.force_login(self.contadino.user)
        response = c.get('/game/test/usepower/')
        self.assertEqual(response.context['form'].fields.keys(), {'target', 'target2'})

        response = c.post('/game/test/usepower/', {'target': self.veggente.user.pk, 'target2':self.lupo.user.pk})
        self.assertEqual(response.status_code, 200)

        self.usepower(self.stalker, self.veggente)

        self.advance_turn()
        self.check_event(MovementKnowledgeEvent, {'player': self.stalker, 'target': self.veggente, 'target2': self.lupo})

    def test_role_target(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        c = Client()
        c.force_login(self.negromante.user)
        response = c.get('/game/test/usepower/')
        self.assertEqual(response.context['form'].fields.keys(), {'target', 'role_class'})

        response = c.post('/game/test/usepower/', {'target': self.contadino.user.pk, 'role_class': Confusione.as_string()})
        self.assertEqual(response.status_code, 200)

        self.advance_turn()
        self.check_event(GhostSwitchEvent, {'player': self.contadino, 'ghost': Confusione})
    def test_multiple_role_target(self):
        c = Client()
        c.force_login(self.diavolo.user)
        response = c.get('/game/test/usepower/')
        self.assertEqual(response.context['form'].fields.keys(), {'target', 'multiple_role_class'})

        response = c.post('/game/test/usepower/', {'target': self.veggente.user.pk, 'multiple_role_class': [Negromante.as_string(), Veggente.as_string()]})
        self.assertEqual(response.status_code, 200)

        self.advance_turn()
        self.check_event(MultipleRoleKnowledgeEvent, {'player': self.diavolo, 'response': True, 'multiple_role_class': {Veggente, Negromante}})

    def test_vote(self):
        self.advance_turn(DAY)

        c = Client()
        c.force_login(self.contadino.user)
        response = c.post('/game/test/vote/', {'target': self.veggente.user.pk})
        self.advance_turn()

        self.check_event(VoteAnnouncedEvent, {'voter': self.contadino, 'voted': self.veggente})
        self.advance_turn()

        response = c.get('/game/test/status/')
        self.assertFalse(response.context['display_votes'])
        self.assertFalse(response.context['display_mayor'])

    def test_cancel_vote(self):
        self.advance_turn(DAY)

        self.vote(self.contadino, self.veggente)
        c = Client()
        c.force_login(self.contadino.user)
        response = c.post('/game/test/vote/', {'target': None})
        self.advance_turn()

        self.check_event(VoteAnnouncedEvent, None)

    def test_personal_events(self):
        self.usepower(self.veggente, self.lupo)
        self.advance_turn(DAY)

        c = Client()
        c.force_login(self.veggente.user)
        response = c.get('/game/test/status/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(dict(response.context['events'])[self.game.current_turn.prev_turn()]['standard'], [])

        response = c.get('/game/test/personalinfo/')
        self.assertEqual(dict(response.context['events'])[self.game.current_turn.prev_turn()]['standard'], ['Hai utilizzato con successo la tua abilità su %s.' % self.lupo.full_name, 'Scopri che %s ha aura nera.' % self.lupo.full_name])

        c.force_login(self.lupo.user)
        response = c.get('/game/test/personalinfo/')
        self.assertEqual(dict(response.context['events'])[self.game.current_turn.prev_turn()]['standard'], [])

    def test_force_victory(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.negromante)
        self.advance_turn(DAY)

        c = Client()
        c.force_login(self.master.user)
        c.get('/game/test/as_gm/')
        response = c.get('/game/test/forcevictory/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].fields['winners'].choices, [(LUPI, 'Lupi'), (POPOLANI, 'Popolani')])

        response = c.post('/game/test/forcevictory/', {'winners': [POPOLANI]})
        self.advance_turn()

        self.assertEqual(self.dynamics.winners, {POPOLANI})

    def test_comment(self):
        c = Client()
        c.force_login(self.lupo.user)
        c.post('/game/test/comment/', {'text': 'Sono un lupo cattivissimo bwahahah'})

        comment = Comment.objects.get()
        self.assertEqual(comment.user, self.lupo.user)
        self.assertEqual(comment.text, 'Sono un lupo cattivissimo bwahahah')

        response = c.get('/game/test/comment/')
        self.assertIn(comment, response.context['old_comments'])

        c.force_login(self.contadino.user)
        response = c.get('/game/test/comment/')
        self.assertNotIn(comment, response.context['old_comments'])


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

class TestMultipleRoleKnowledge(GameTest, TestCase):
    roles = [ Guardia, Veggente, Lupo, Diavolo, Negromante ]
    spectral_sequence = [True]

    def test_diavolo(self):
        # Test diavolo
        self.usepower(self.diavolo, self.guardia, multiple_role_class={Divinatore, Guardia})
        self.advance_turn()

        self.check_event(MultipleRoleKnowledgeEvent, {
            'player': self.diavolo,
            'cause': DEVIL,
            'response': True,
            'multiple_role_class': {Guardia, Divinatore}
        })

        self.advance_turn(NIGHT)

        # Retest
        self.usepower(self.diavolo, self.guardia, multiple_role_class={Negromante, Lupo, Veggente})
        self.advance_turn()

        self.check_event(MultipleRoleKnowledgeEvent, {
            'player': self.diavolo,
            'cause': DEVIL,
            'response': False,
            'multiple_role_class': {Lupo, Negromante, Veggente}
        })

class TestSpectralSequence(GameTest, TestCase):
    roles = [ Contadino, Contadino, Contadino, Contadino, Contadino, Contadino, Sciamano, Lupo, Diavolo, Negromante, Negromante, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma]
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
        self.assertTrue(isinstance(self.contadino_a.dead_power, Delusione))
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
        self.assertFalse(self.contadino_b.specter)

        self.advance_turn(NIGHT)

        # Kill diavolo: nothing happens
        self.usepower(self.lupo, self.diavolo)
        self.advance_turn()

        self.check_event(GhostificationEvent, None)
        self.assertEqual(self.diavolo.team, LUPI)
        self.assertIsInstance(self.diavolo.dead_power, NoPower)
        self.assertFalse(self.diavolo.specter)

        self.advance_turn(NIGHT)

        # Kill contadino_c
        self.usepower(self.lupo, self.contadino_c)
        self.advance_turn()

        self.check_event(GhostificationEvent, {'player': self.contadino_c, 'ghost': Delusione})
        self.assertEqual(self.contadino_c.team, NEGROMANTI)
        self.assertTrue(isinstance(self.contadino_c.dead_power, Delusione))

        self.advance_turn(NIGHT)

        # Kill contadino_d
        self.usepower(self.lupo, self.contadino_d)
        self.advance_turn()

        self.check_event(GhostificationEvent, {'player': self.contadino_d, 'ghost': Delusione})
        self.assertEqual(self.contadino_d.team, NEGROMANTI)
        self.assertTrue(isinstance(self.contadino_d.dead_power, Delusione))

        self.advance_turn(NIGHT)

        # Kill contadino_e
        self.usepower(self.lupo, self.contadino_e)
        self.advance_turn()

        self.check_event(GhostificationEvent, None)
        self.assertEqual(self.contadino_e.team, POPOLANI)
        self.assertIsInstance(self.contadino_e.dead_power, NoPower)

    def test_negromante(self):
        self.advance_turn(NIGHT)

        # Kill contadino_a => becomes spettro
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_a, role_class=Amnesia)
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'player': self.contadino_a, 'ghost': Amnesia})
        self.assertTrue(isinstance(self.contadino_a.dead_power, Amnesia))
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_a, role_class=Confusione)
        self.assertNotIn(Amnesia, self.negromante_a.power.get_targets_role_class())
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'player': self.contadino_a, 'ghost': Confusione})
        self.assertIsInstance(self.contadino_a.dead_power, Confusione)
        self.advance_turn(NIGHT)

        # Kill contadino_b => doesn't become spettro
        self.usepower(self.lupo, self.contadino_b)
        self.advance_turn(NIGHT)

        self.assertNotIn(self.contadino_b, self.negromante_a.power.get_targets())
        self.advance_turn(NIGHT)

        # Kill Negromante
        self.usepower(self.lupo, self.negromante_a)
        self.advance_turn(NIGHT)

        self.assertFalse(self.negromante_a.alive)
        self.assertIsInstance(self.negromante_a.dead_power, Spettrificazione)
        self.assertTrue(self.negromante_a.can_use_power())
        self.usepower(self.negromante_a, self.contadino_b, role_class=Amnesia)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'player': self.negromante_a, 'success': True})
        self.check_event(GhostificationEvent, {'player': self.contadino_b, 'ghost': Amnesia})
        self.advance_turn(NIGHT)

        # Kill contadini
        self.usepower(self.lupo, self.contadino_c)
        self.advance_turn(NIGHT)
        self.usepower(self.lupo, self.contadino_d)
        self.advance_turn(NIGHT)
        self.usepower(self.lupo, self.contadino_e)
        self.advance_turn(NIGHT)

        self.assertEqual(self.contadino_e.team, POPOLANI)
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

        # Try to make confusione and telepatia
        self.usepower(self.negromante_a, target=self.contadino_a, role_class=Confusione)
        self.usepower(self.negromante_b, target=self.contadino_c, role_class=Telepatia)
        self.advance_turn()

        self.check_event(GhostSwitchEvent, {'ghost': Confusione}, player=self.contadino_a)
        self.check_event(GhostSwitchEvent, {'ghost': Telepatia}, player=self.contadino_c)
        self.advance_turn(NIGHT)

        # Try to make two amnesia
        self.usepower(self.negromante_a, target=self.contadino_a, role_class=Amnesia)
        self.usepower(self.negromante_b, target=self.contadino_c, role_class=Amnesia)
        self.advance_turn()

        good_n = self.get_events(PowerOutcomeEvent, success=True)[0].player
        bad_n =self.get_events(PowerOutcomeEvent, success=False)[0].player

        amnesia = self.contadino_a if good_n == self.negromante_a else self.contadino_c
        not_amnesia = self.contadino_a if bad_n == self.negromante_a else self.contadino_c

        self.check_event(GhostSwitchEvent, {'player': amnesia, 'ghost': Amnesia})
        self.assertIsInstance(amnesia.dead_power, Amnesia)
        self.assertNotIsInstance(not_amnesia.dead_power, Amnesia)

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
        self.assertIsInstance(self.contadino_a.dead_power, Confusione)
        self.assertFalse(self.contadino_a.can_use_power())
        self.advance_turn(NIGHT)

        # Now he can
        self.usepower(self.contadino_a, self.diavolo, role_class=Negromante)
        self.advance_turn(NIGHT)

        # And he can again
        self.assertTrue(self.contadino_a.can_use_power())

    def test_morte_can_act_no_more(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        # Make Spettro della morte
        self.usepower(self.negromante_a, self.contadino_a, role_class=Morte)
        self.advance_turn(NIGHT)

        # Use power and then change
        self.usepower(self.contadino_a, self.diavolo)
        self.usepower(self.negromante_a, self.contadino_a, role_class=Confusione)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': True}, player=self.contadino_a)
        self.check_event(PlayerDiesEvent, {'player': self.diavolo})
        self.check_event(GhostSwitchEvent, None, cause=NECROMANCER)
        self.check_event(UnGhostificationEvent, {'player': self.contadino_a})
        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.negromante_a)
        self.assertIsInstance(self.contadino_a.dead_power, NoPower)
        self.assertFalse(self.contadino_a.specter)
        self.advance_turn(NIGHT)

        # Morte can be reassigned
        self.usepower(self.lupo, self.contadino_b)
        self.advance_turn(NIGHT)
        self.usepower(self.lupo, self.contadino_c)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_c, role_class=Morte)
        self.advance_turn()

        self.assertIsInstance(self.contadino_c.dead_power, Morte)

    def test_fantasma(self):
        self.advance_turn(NIGHT)
        powers = {Amnesia, Assoluzione, Confusione, Delusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia}
        for phantom in [x for x in self.players if isinstance(x.role, Fantasma)]:
            self.usepower(self.lupo, phantom)
            self.advance_turn()

            self.check_event(GhostificationEvent, {'player': phantom})
            powers.remove(phantom.dead_power.__class__)
            self.advance_turn(NIGHT)

        self.assertEqual(powers, set())
        self.assertIsInstance(phantom.dead_power, Delusione)

    def test_sciamano(self):
        self.advance_turn(NIGHT)
        self.usepower(self.lupo, self.contadino_a)
        self.advance_turn(NIGHT)

        self.assertTrue(self.contadino_a.specter)
        self.usepower(self.negromante_a, self.contadino_a, role_class=Amnesia)
        self.advance_turn(NIGHT)

        self.assertIsInstance(self.contadino_a.dead_power, Amnesia)
        self.usepower(self.contadino_a, self.contadino_b)
        self.usepower(self.sciamano, self.contadino_a)
        self.usepower(self.negromante_a, self.contadino_a, role_class=Occultamento)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': True}, player=self.sciamano)
        self.check_event(PowerOutcomeEvent, {'success': True, 'power': Amnesia}, player=self.contadino_a)
        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.negromante_a)
        self.check_event(GhostSwitchEvent, {'player': self.contadino_a, 'cause': SHAMAN, 'ghost': Delusione})
        self.assertIsInstance(self.contadino_a.dead_power, Delusione)
        self.assertTrue(self.contadino_b.has_permanent_amnesia)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante_a, self.contadino_a, role_class=Amnesia)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': True}, player=self.negromante_a)


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
        self.advance_turn(NIGHT)

        #Now kill and resurrect guardia
        self.usepower(self.lupo, self.guardia)
        self.advance_turn(NIGHT)

        self.usepower(self.messia, self.guardia)
        self.advance_turn(DAY)

        # Still has amnesia
        self.assertTrue(self.guardia.has_permanent_amnesia)

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
        self.assertTrue(isinstance(self.contadino.dead_power, Amnesia))

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
    roles = [Contadino, Massone, Massone, Trasformista, Messia, Lupo, Fattucchiera, Diavolo, Negromante]
    spectral_sequence = []

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
        self.usepower(self.fattucchiera, self.contadino, role_class=Messia)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.contadino, 'role_class': Messia})
        self.assertIsInstance(self.trasformista.role, Messia)
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
        self.assertIsInstance(self.trasformista.role, Trasformista)
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
        self.assertIsInstance(self.trasformista.role, Contadino)
        self.advance_turn(NIGHT)

        self.assertFalse(self.trasformista.can_use_power())

    def test_trasformista_on_fake_lupo(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.contadino)
        self.usepower(self.fattucchiera, self.contadino, role_class=Lupo)
        self.advance_turn()

        self.check_event(PowerOutcomeEvent, {'success': False}, player=self.trasformista)
        self.check_event(TransformationEvent, None)
        self.assertIsInstance(self.trasformista.role, Trasformista)
        self.advance_turn(NIGHT)

        # Since he failed, he can retry
        self.assertTrue(self.trasformista.can_use_power())

    def test_trasformista_on_diavolo_with_fattucchiera(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.diavolo)
        self.advance_turn(NIGHT)

        self.usepower(self.trasformista, self.diavolo)
        self.usepower(self.fattucchiera, self.diavolo, role_class=Messia)
        self.advance_turn()

        self.check_event(TransformationEvent, {'player': self.trasformista, 'target': self.diavolo, 'role_class': Messia})
        self.assertIsInstance(self.trasformista.role, Messia)

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

class TestAuraMisticityKnowledge(GameTest, TestCase):
    roles = [Contadino, Veggente, Mago, Lupo, Fattucchiera, Negromante]
    spectral_sequence = [True]

    def setUp(self):
        # Automatically make Confusione
        super().setUp()
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.contadino, role_class=Confusione)
        self.advance_turn(NIGHT)

    def test_veggente(self):
        self.usepower(self.veggente, self.fattucchiera)
        self.advance_turn()

        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'target': self.fattucchiera, 'aura': WHITE})
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.lupo)
        self.advance_turn()

        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'target': self.lupo, 'aura': BLACK})
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.lupo)
        self.usepower(self.fattucchiera, self.lupo, role_class=Contadino)
        self.advance_turn()

        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'target': self.lupo, 'aura': WHITE})
        self.advance_turn(NIGHT)

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
        self.usepower(self.contadino, self.lupo, target2=None)
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

    def test_sequestratore(self):
        # Sequestratore on moving player
        self.usepower(self.sequestratore, self.alcolista)
        self.usepower(self.alcolista, self.sequestratore)
        self.advance_turn()

        self.check_event(MovementKnowledgeEvent, {'player': self.sequestratore, 'target': self.alcolista, 'target2': None})
        self.advance_turn(NIGHT)

        # Sequestratore on non moving player
        self.usepower(self.sequestratore, self.alcolista)
        self.advance_turn()

        self.check_event(NoMovementKnowledgeEvent, {'player': self.sequestratore, 'target': self.alcolista})

    def test_sequestratore_with_illusione(self):
        self.usepower(self.contadino, self.alcolista, target2=None)
        self.usepower(self.stalker, self.alcolista)
        self.usepower(self.sequestratore, self.alcolista)
        self.usepower(self.alcolista, self.negromante)
        self.advance_turn()

        self.check_event(MovementKnowledgeEvent, {'player': self.sequestratore, 'target': self.alcolista, 'target2': None})
        self.check_event(NoMovementKnowledgeEvent, {'player': self.stalker, 'target': self.alcolista})

    def test_illusione_on_self(self):
        self.usepower(self.contadino, self.guardia, target2=self.contadino)
        self.usepower(self.stalker, self.guardia)
        self.advance_turn()

        self.check_event(MovementKnowledgeEvent, {'player': self.stalker, 'target': self.guardia, 'target2': self.contadino})

    def test_assassino_and_illusione(self):
        killed = set()
        for x in range(2):
            # Lowest number that works.
            # May produce error if messing with random generator, in that case it must be invcreased.

            self.seed = x
            self.restart()

            self.usepower(self.assassino, self.stalker)
            self.usepower(self.voyeur, self.stalker)
            self.usepower(self.contadino, self.alcolista, target2=self.stalker)

            self.advance_turn()
            events = self.get_events(PlayerDiesEvent)
            killed.add(events[0].player.role.__class__ if events else None)
            self.tearDown()

        self.assertEqual(killed, {None, Voyeur})

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
        self.check_event(event, {'player': self.alcolista, 'success': False})
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

class TestVita(GameTest, TestCase):
    roles = [Contadino, Veggente, Mago, Messia, Stalker, Voyeur, Esorcista, Lupo, Diavolo, Alcolista, Negromante]
    spectral_sequence = [True, False, True]

    def test_vita_on_veggente(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Vita)
        self.advance_turn()

        self.check_event(PlayerResurrectsEvent, {'player': self.veggente})
        self.assertIsInstance(self.veggente.role, Veggente)
        self.assertIsInstance(self.veggente.dead_power, Vita)
        self.assertEqual(self.veggente.team, NEGROMANTI)
        self.assertTrue(self.veggente.alive)
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.lupo)
        self.advance_turn()

        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'aura': BLACK})

    def test_vita_dies_and_respawns(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Vita)
        self.advance_turn(DAY)

        self.burn(self.veggente)
        self.advance_turn()

        self.check_event(VoteAnnouncedEvent, {'voted': self.veggente}, voter=self.veggente)
        self.check_event(PlayerDiesEvent, {'player': self.veggente})
        self.check_event(GhostSwitchEvent, {'player': self.veggente, 'ghost': Delusione, 'cause': LIFE_GHOST})
        self.assertIsInstance(self.veggente.role, Veggente)
        self.assertIsInstance(self.veggente.dead_power, Delusione)
        self.advance_turn()

        self.usepower(self.negromante, self.veggente, role_class=Vita)
        self.advance_turn()

        self.check_event(PlayerResurrectsEvent, {'player': self.veggente})

    def test_vita_changes_power(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Vita)
        self.advance_turn()

        self.check_event(PlayerResurrectsEvent, {'player': self.veggente})
        self.assertTrue(self.veggente.alive)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Morte)
        self.advance_turn()

        self.check_event(PlayerDiesEvent, {'player': self.veggente, 'cause': LIFE_GHOST})
        self.check_event(GhostSwitchEvent, {'player': self.veggente, 'ghost': Morte, 'cause': NECROMANCER})
        self.assertIsInstance(self.veggente.dead_power, Morte)

    def test_esorcista_on_vita(self):
        # L'esorcista blocca i poteri, non le abilità. Quindi non ha effetto su vita.
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.veggente, role_class=Vita)
        self.advance_turn(NIGHT)

        self.usepower(self.veggente, self.lupo)
        self.usepower(self.esorcista, self.lupo)
        self.advance_turn()

        self.check_event(AuraKnowledgeEvent, {'player': self.veggente, 'aura': BLACK})

    def test_vita_on_unused_messia(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.messia)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.messia, role_class=Vita)
        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.messia, self.contadino)
        self.advance_turn()

        self.check_event(PlayerResurrectsEvent, {'player': self.contadino})

    def test_vita_on_used_messia(self):
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.veggente)
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.contadino)
        self.advance_turn(NIGHT)

        self.usepower(self.messia, self.contadino)
        self.advance_turn()

        self.check_event(PlayerResurrectsEvent, {'player': self.contadino})
        self.advance_turn(NIGHT)

        self.usepower(self.lupo, self.messia)
        self.advance_turn(NIGHT)

        self.usepower(self.negromante, self.messia, role_class=Vita)
        self.advance_turn(NIGHT)

        self.assertFalse(self.messia.can_use_power())
