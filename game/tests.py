
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
from game.roles import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time

from datetime import timedelta, datetime, time


class AdvanceTimeTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_simple_advance(self):
        now = datetime(2015, 11, 11, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 11, 18, 0, 0), is_dst=None))

    def test_wrapped_advance(self):
        now = datetime(2015, 11, 11, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 12, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance(self):
        now = datetime(2015, 3, 28, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance(self):
        now = datetime(2015, 10, 24, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))

    def test_simple_advance_with_useless_skip(self):
        now = datetime(2015, 11, 11, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 11, 18, 0, 0), is_dst=None))

    def test_wrapped_advance_with_useless_skip(self):
        now = datetime(2015, 11, 11, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 12, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance_with_useless_skip(self):
        now = datetime(2015, 3, 28, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance_with_useless_skip(self):
        now = datetime(2015, 10, 24, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))

    def test_simple_advance_with_real_skip(self):
        now = datetime(2015, 11, 13, 16, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 15, 18, 0, 0), is_dst=None))

    def test_wrapped_advance_with_real_skip(self):
        now = datetime(2015, 11, 12, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 11, 15, 18, 0, 0), is_dst=None))

    def test_enter_dst_advance_with_real_skip(self):
        now = datetime(2015, 3, 26, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 3, 29, 18, 0, 0), is_dst=None))

    def test_exit_dst_advance_with_real_skip(self):
        now = datetime(2015, 10, 22, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 10, 25, 18, 0, 0), is_dst=None))

    def test_wrapped_advance_through_immacolate_bridge(self):
        now = datetime(2015, 12, 3, 20, 0, 0, tzinfo=REF_TZINFO)
        when = time(18, 0, 0)
        later = advance_to_time(now, when, day_end_skip=True)
        self.assertEqual(later, REF_TZINFO.localize(datetime(2015, 12, 8, 18, 0, 0), is_dst=None))


def create_users(n):
    users = []
    for i in xrange(n):
        user = User.objects.create(username='pk%d' % (i), first_name='Paperinik', last_name='%d' % (i), email='paperinik.%d@sns.it' % (i), password='ciaociao')
        profile = Profile.objects.create(user=user, gender=MALE)
        profile.save()
        user.set_password('ciaociao')
        user.save()
        users.append(user)
    return users


def delete_auto_users():
    for user in User.objects.all():
        if user.username.startswith('pk'):
            user.delete()


def delete_non_staff_users():
    for user in User.objects.all():
        if not user.is_staff:
            user.delete()


def delete_games():
    for game in Game.objects.all():
        game.delete()


def create_test_game(seed, roles):
    game = Game(running=True)
    game.save()
    game.initialize(get_now())

    users = create_users(len(roles))
    for user in users:
        if user.is_staff:
            raise Exception()
        player = Player.objects.create(user=user, game=game)
        player.save()

    first_turn = game.get_dynamics().current_turn

    event = SeedEvent(seed=seed)
    event.timestamp = first_turn.begin
    game.get_dynamics().inject_event(event)

    for i in xrange(len(game.get_dynamics().players)):
        event = AvailableRoleEvent(role_name=roles[i%len(roles)].__name__)
        event.timestamp = first_turn.begin
        game.get_dynamics().inject_event(event)

    return game


def create_game_from_dump(data, start_moment=None):
    if start_moment is None:
        start_moment = get_now()

    game = Game(running=True)
    game.save()
    game.initialize(start_moment)

    for player_data in data['players']:
        user = User.objects.create(username=player_data['username'],
                                   first_name=player_data.get('first_name', ''),
                                   last_name=player_data.get('last_name', ''),
                                   password=player_data.get('password', ''),
                                   email=player_data.get('email', ''))
        profile = Profile.objects.create(user=user, gender=player_data.get('gender', ''))
        profile.save()
        user.save()
        player = Player.objects.create(user=user, game=game)
        player.save()

    # Here we canonicalize the players, so this has to happen after
    # all users and players have been inserted in the database;
    # therefore, this loop cannot be merged with the previous one
    players_map = {None: None}
    for player in game.get_players():
        assert player.user.username not in players_map
        players_map[player.user.username] = player

    # Now we're ready to reply turns and events
    first_turn = True
    for turn_data in data['turns']:
        if not first_turn:
            test_advance_turn(game)
        else:
            first_turn = False
        current_turn = game.current_turn
        for event_data in turn_data['events']:
            event = Event.from_dict(event_data, players_map)
            if current_turn.phase in FULL_PHASES:
                event.timestamp = get_now()
            else:
                event.timestamp = current_turn.begin
            #print >> sys.stderr, "Injecting event of type %s" % (event.subclass)
            game.get_dynamics().inject_event(event)

    return game


def test_advance_turn(game):
    turn = game.current_turn
    turn.end = get_now()
    turn.save()
    game.advance_turn()


def record_name(f):
    @wraps(f)
    def g(self):
        self._name = f.__name__
        return f(self)

    return g


class GameTests(TestCase):

    def setUp(self):
        self._name = None

    def tearDown(self):
        # Save a dump of the test game
        if 'game' in self.__dict__:
            with open(os.path.join('test_dumps', '%s.json' % (self._name)), 'w') as fout:
                dump_game(self.game, fout)

        # Destroy the leftover dynamics without showing the slightest
        # sign of mercy
        kill_all_dynamics()

    @record_name
    def test_event_before_turn(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]

        # Advance to day and cast a vote; but set the event with a
        # timestamp earlier than the beginning of the turn
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        event = CommandEvent(player=cacciatore, type=VOTE, target=ipnotista, timestamp=get_now() - timedelta(minutes=10))
        dynamics.inject_event(event)

        # Check that this produces an error
        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_event_before_turn_rebooting_dynamics(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]

        # Advance to day and cast a vote; but set the event with a
        # timestamp earlier than the beginning of the turn
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        event = CommandEvent(player=cacciatore, type=VOTE, target=ipnotista, timestamp=get_now() - timedelta(minutes=10))
        dynamics.inject_event(event)

        # Do not advance turn, but reboot dynamics and check that the
        # assertion is violated immediately (i.e., when entering the
        # turn with the violation, not when finishing it)
        kill_all_dynamics()

        with self.assertRaises(AssertionError):
            dynamics = self.game.get_dynamics()

    @record_name
    def test_event_after_turn(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        self.assertEqual(self.game.current_turn.phase, CREATION)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]

        # Advance to day and cast a vote; but set the event with a
        # timestamp earlier than the beginning of the turn
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        event = CommandEvent(player=cacciatore, type=VOTE, target=ipnotista, timestamp=get_now() + timedelta(minutes=10))
        dynamics.inject_event(event)

        # Check that this produces an error
        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_game_setup(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        self.game = create_test_game(2204, roles)

        self.assertEqual(self.game.current_turn.phase, CREATION)
        self.assertEqual(self.game.mayor.user.username, 'pk4')

    @record_name
    def test_turn_advance(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        self.game = create_test_game(2204, roles)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertEqual(self.game.current_turn.phase, DAY)

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        self.assertEqual(self.game.current_turn.phase, DAWN)

    def load_game_helper(self, filename):
        with open(os.path.join('dumps', filename)) as fin:
            data = json.load(fin)
        game = create_game_from_dump(data)
        return game

    def voting_helper(self, roles, mayor_votes, stake_votes, expected_mayor, expect_to_die, appointed_mayor=None, expected_final_mayor=None):
        if mayor_votes is not None:
            self.assertEqual(len(roles), len(mayor_votes))
        if stake_votes is not None:
            self.assertEqual(len(roles), len(stake_votes))

        # The seed is chosen so that the first player is the mayor
        game = create_test_game(1, roles)
        dynamics = game.get_dynamics()
        players = game.get_players()
        initial_mayor = game.mayor

        self.assertEqual(game.mayor.pk, players[0].pk)

        test_advance_turn(game)

        # During the night the mayor may appoint a successor
        if appointed_mayor is not None:
            event = CommandEvent(player=players[0], type=APPOINT, target=players[appointed_mayor], timestamp=get_now())
            dynamics.inject_event(event)

        test_advance_turn(game)
        test_advance_turn(game)

        self.assertEqual(game.current_turn.phase, DAY)

        # Push votes
        for i, player in enumerate(players):
            if stake_votes is not None:
                if stake_votes[i] is not None:
                    event = CommandEvent(player=player, type=VOTE, target=players[stake_votes[i]], timestamp=get_now())
                else:
                    event = CommandEvent(player=player, type=VOTE, target=None, timestamp=get_now())
                dynamics.inject_event(event)

            if mayor_votes is not None:
                if mayor_votes[i] is not None:
                    event = CommandEvent(player=player, type=ELECT, target=players[mayor_votes[i]], timestamp=get_now())
                else:
                    event = CommandEvent(player=player, type=ELECT, target=None, timestamp=get_now())
                dynamics.inject_event(event)
        # Trigger the vote counting
        dynamics.debug_event_bin = []
        test_advance_turn(game)

        # Check the results
        mayor_after_election = None
        if expected_mayor is not None:
            [mayor_event] = [event for event in dynamics.debug_event_bin if isinstance(event, SetMayorEvent) and event.cause == ELECT]
            self.assertEqual(mayor_event.player.pk, players[expected_mayor].pk)
            if expect_to_die is None or expect_to_die != expected_mayor:
                self.assertTrue(players[expected_mayor].is_mayor())
            mayor_after_election = players[expected_mayor]
        else:
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, SetMayorEvent) and event.cause == ELECT], [])
            mayor_after_election = initial_mayor

        mayor_dead = False
        if expect_to_die is not None:
            [kill_event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
            self.assertEqual(kill_event.cause, STAKE)
            self.assertEqual(kill_event.player.pk, players[expect_to_die].pk)
            self.assertFalse(players[expect_to_die].canonicalize().alive)
            if players[expect_to_die].pk == mayor_after_election.pk:
                mayor_dead = True
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)], [])
        else:
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
            [stake_failed_event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
            self.assertEqual(stake_failed_event.cause, MISSING_QUORUM)

        # FIXME: here expected_final_mayor changes type!
        if expected_final_mayor is None:
            expected_final_mayor = mayor_after_election
            if mayor_dead:
                if appointed_mayor is not None:
                    expected_final_mayor = players[appointed_mayor]
                else:
                    expected_final_mayor = None
        else:
            expected_final_mayor = players[expected_final_mayor]

        if expected_final_mayor is not None:
            self.assertEqual(game.mayor.pk, expected_final_mayor.pk)

        dynamics.debug_event_bin = None

        return game

    @record_name
    def test_stake_vote_unanimity(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 ]
        self.game = self.voting_helper(roles, None, votes, None, 1)

    @record_name
    def test_stake_vote_absolute_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 3, 3, 3, 3, 3, 3, 1, 1, 2, None ]
        self.game = self.voting_helper(roles, None, votes, None, 3)

    @record_name
    def test_stake_vote_relative_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 3, 3, 3, 3, 1, 1, 1, 2, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, 3)

    @record_name
    def test_stake_vote_tie_with_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 5, 5, 5, 1, 1, 1, 3, 4, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, 5)

    @record_name
    def test_stake_vote_tie_without_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 2, 0, 0, 1, 1, 1, 0, 4, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, 0)

    @record_name
    def test_stake_vote_no_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, None, None, None, None, None, None, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, None)

    @record_name
    def test_stake_vote_half_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 1, 1, 1, 1, 1, None, None, None, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, 1)

    @record_name
    def test_stake_vote_mayor_not_voting(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ None, 1, 1, 1, 1, 1, 1, None, None, None ]
        self.game = self.voting_helper(roles, None, votes, None, 1)

    @record_name
    def test_stake_vote_appointment(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        stake_votes = [ 0, 0, 0, 0, 0, 0, None, None, None, None ]
        self.game = self.voting_helper(roles, None, stake_votes, None, 0, appointed_mayor=1, expected_final_mayor=1)


    @record_name
    def test_election_unanimity(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
        self.game = self.voting_helper(roles, votes, None, 0, None)

    @record_name
    def test_election_absolute_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 1, 1, 2, None ]
        self.game = self.voting_helper(roles, votes, None, 0, None)

    @record_name
    def test_election_relative_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 1, 1, 1, 2, None, None ]
        self.game = self.voting_helper(roles, votes, None, None, None)

    @record_name
    def test_election_tie_with_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 1, 1, 1, 3, 4, None, None ]
        self.game = self.voting_helper(roles, votes, None, None, None)

    @record_name
    def test_election_tie_without_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 2, 0, 0, 1, 1, 1, 0, 4, None, None ]
        self.game = self.voting_helper(roles, votes, None, None, None)

    @record_name
    def test_election_no_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, None, None, None, None, None, None, None, None ]
        self.game = self.voting_helper(roles, votes, None, None, None)

    @record_name
    def test_election_half_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, None, None, None, None, None ]
        self.game = self.voting_helper(roles, votes, None, None, None)

    @record_name
    def test_election_mayor_not_voting(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ None, 0, 0, 0, 0, 0, 0, None, None, None ]
        self.game = self.voting_helper(roles, votes, None, 0, None)


    @record_name
    def test_composite_election_same_mayor(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        mayor_votes = [ 1, 1, 1, 1, 2, 2, 0, 0, 0, 0 ]
        stake_votes = [ 2, 3, 2, 3, 2, 3, None, None, None, None ]
        self.game = self.voting_helper(roles, mayor_votes, stake_votes, None, 2)

    @record_name
    def test_composite_election_change_mayor(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        mayor_votes = [ 1, 1, 1, 1, 1, 1, 0, 0, 0, 0 ]
        stake_votes = [ 2, 3, 2, 3, 2, 3, None, None, None, None ]
        self.game = self.voting_helper(roles, mayor_votes, stake_votes, 1, 3)

    @record_name
    def test_composite_election_appointment(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        mayor_votes = [ 1, 1, 1, 1, 1, 1, 0, 0, 0, 0 ]
        stake_votes = [ 1, 1, 1, 1, 1, 1,  None, None, None, None ]
        self.game = self.voting_helper(roles, mayor_votes, stake_votes, 1, 1, appointed_mayor=8, expected_final_mayor=4)


    @record_name
    def test_missing_negromanti(self):
        roles = [ Contadino, Contadino, Lupo, Lupo ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_missing_negromanti2(self):
        roles = [ Contadino, Contadino, Lupo, Lupo, Fantasma ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_missing_lupi(self):
        roles = [ Contadino, Contadino, Negromante, Negromante ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_missing_lupi2(self):
        roles = [ Contadino, Contadino, Negromante, Negromante, Fattucchiera ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_missing_popolani(self):
        roles = [ Negromante, Negromante, Lupo, Lupo ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        with self.assertRaises(AssertionError):
            test_advance_turn(self.game)

    @record_name
    def test_nothing_missing(self):
        roles = [ Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        test_advance_turn(self.game)


    @record_name
    def test_espansivo(self):
        roles = [ Espansivo, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=players[0], target=players[1], timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, players[1])
        self.assertEqual(event.target, players[0])
        self.assertEqual(event.cause, EXPANSIVE)

        dynamics.debug_event_bin = None

    @record_name
    def test_cacciatore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, lupo)
        self.assertEqual(event.cause, HUNTER)
        self.assertFalse(lupo.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_double_cacciatore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, lupo)
        self.assertEqual(event.cause, HUNTER)
        self.assertFalse(lupo.alive)

        dynamics.debug_event_bin = None

        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Cacciatore cannot strike twice
        test_advance_turn(self.game)
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=lupo2, timestamp=get_now()))
        self.assertTrue(lupo2.alive)

    @record_name
    def test_early_cacciatore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]

        # Cacciatore cannot strike during first night
        test_advance_turn(self.game)
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=lupo, timestamp=get_now()))
        self.assertTrue(lupo.alive)

    @record_name
    def test_early_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

        # Lupo cannot strike during first night
        test_advance_turn(self.game)
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        self.assertTrue(cacciatore.alive)

    @record_name
    def test_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_lupo_with_guardia(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=cacciatore, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_lupo_with_wrong_guardia(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=lupo2, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_lupi_with_guardia(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo2, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=cacciatore, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo2]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_lupo_on_non_popolano(self): # Lupus7 update (old test_lupo_on_negromante)
        roles = [ Cacciatore, Negromante, Negromante, Ipnotista, Lupo, Lupo, Diavolo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=negromante, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(negromante.alive)

        # Advance to third night and retry
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(ipnotista.alive)

        # Advance to fourth night and retry
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=diavolo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(diavolo.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_sequestrated_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_doubly_sequestrated_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore, sequestratore2] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore2, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_chain_sequestrated_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore, sequestratore2] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore2, target=sequestratore, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_unsequestrated_lupo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo2, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None
    
    @record_name
    def test_sequestrated_espansivo(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore, Espansivo ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [espansivo] = [x for x in players if isinstance(x.role, Espansivo)]

        # Advance to night and use powers
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=espansivo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=espansivo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == espansivo]
        self.assertFalse(event.success)
        
        # Advance to night and try to use Espansivo power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(espansivo.can_use_power())
        self.assertTrue(sequestratore.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=espansivo, target=lupo, timestamp=get_now()))
    
    @record_name
    def test_lupi(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo2, target=cacciatore, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo2]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_disjoint_lupi(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo2, target=contadino, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo2]
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_disjoint_lupi_with_sequestratore(self): # Update Lupus7
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo2, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo2]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        self.assertFalse(contadino.alive)
        
    @record_name
    def test_lupi_with_sequestratore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo2, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo2]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(cacciatore.alive)

        dynamics.debug_event_bin = None

    @record_name
    def test_negromante(self):
        roles = [ Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to first day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Put Contadino to stake
        for player in players:
            dynamics.inject_event(CommandEvent(type=VOTE, player=player, target=contadino, timestamp=get_now()))

        # Advance to sunset and check death
        test_advance_turn(self.game)
        self.assertFalse(contadino.alive)
        self.assertTrue(negromante.alive)

        # Advance to night and ghostify Contadino
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))

        # Advance to dawn
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, AMNESIA)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro))
    
    @record_name
    def test_ipnotista(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to night
        test_advance_turn(self.game)
        
        # Use Ipnotista power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=contadino, timestamp=get_now()))
        
        # Advance to day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and (event.voter == contadino or event.voter == ipnotista)]
        for event in events:
            self.assertEqual(event.voted, negromante)
        self.assertTrue(negromante.alive)
        
        # Advance to second night
        test_advance_turn(self.game)
        self.assertFalse(ipnotista.can_use_power())
        
        # Advance to second day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote (Ipnotista does not vote)
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=ipnotista, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and (event.voter == contadino or event.voter == ipnotista)]
        self.assertEqual(events, [])

    def test_ipnotista_resurrected(self): # Update Lupus7
        # We need two Ipnotisti, otherwise the Ipnotista
        # becomes a Spettro and nothing works anymore
        roles = [ Ipnotista, Ipnotista, Negromante, Lupo,  Contadino, Cacciatore, Cacciatore, Messia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista1, ipnotista2] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [cacciatore1, cacciatore2] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use ipnotista2 power, kill ipnotista1
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista2, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore1, target=ipnotista1, timestamp=get_now()))
        
        # Advance to day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and (event.voter == contadino or event.voter == ipnotista2)]
        for event in events:
            self.assertEqual(event.voted, negromante)
        self.assertTrue(negromante.alive)
        
        # Advance to second night and kill ipnotista2
        test_advance_turn(self.game)
        self.assertFalse(ipnotista2.can_use_power())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore2, target=ipnotista2, timestamp=get_now()))
        
        test_advance_turn(self.game)
        self.assertFalse(ipnotista2.alive)
        
        # Advance to second day and check that contadino is not controlled
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(event.voter, contadino)
        self.assertEqual(event.voted, lupo)
        
        # Advance to third night and resurrect ipnotista2
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=ipnotista2, timestamp=get_now()))
        
        test_advance_turn(self.game)
        self.assertTrue(ipnotista2.alive)
        
        # Advance to third day and check votes
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=contadino, timestamp=get_now()))
        
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertEqual(event.voted, contadino)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TallyAnnouncedEvent)]
        self.assertEqual(event.voted, contadino)
        self.assertEqual(event.vote_num, 2)
    
    @record_name
    def test_ipnotista_after_exile(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to night
        test_advance_turn(self.game)
        
        # Use Ipnotista power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=contadino, timestamp=get_now()))
        
        # Advance to day and kill Negromante
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, negromante)
        self.assertFalse(negromante.canonicalize().alive)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(len(events), 2)
        self.assertEqual(set([e.player for e in events]), set([negromante, ipnotista]))
        
        self.assertEqual(contadino.canonicalize().hypnotist, None)
        
        # Advance to second night
        test_advance_turn(self.game)
        self.assertFalse(ipnotista.canonicalize().can_use_power())
        
        # Advance to second day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        self.assertFalse(ipnotista.canonicalize().can_vote())
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(event.voter, contadino)
        self.assertEqual(event.voted, lupo)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TallyAnnouncedEvent)]
        self.assertEqual(event.voted, lupo)
        self.assertEqual(event.vote_num, 1)
    
    @record_name 
    def test_fantasma(self): # Lupus7 update
        for i in xrange(20):
            # Since this test is repeasted many times, we have to
            # destroy it and delete all users before testing again
            if 'game' in self.__dict__ and self.game is not None:
                self.game.delete()
                self.game = None
            delete_auto_users()

            roles = [ Fantasma, Negromante, Lupo, Contadino ]
            phantom_roles = [AMNESIA, CONFUSIONE, ILLUSIONE, IPNOSI, OCCULTAMENTO, VISIONE]
            
            self.game = create_test_game(i, roles)
            dynamics = self.game.get_dynamics()
            players = self.game.get_players()

            [fantasma]   = [x for x in players if isinstance(x.role, Fantasma)]
            [negromante] = [x for x in players if isinstance(x.role, Negromante)]
            [lupo]       = [x for x in players if isinstance(x.role, Lupo)]

            # Advance to day
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            
            # Kill Fantasma
            dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=fantasma, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=VOTE, player=fantasma,   target=fantasma, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=VOTE, player=lupo,       target=fantasma, timestamp=get_now()))
            
            # Advance to sunset
            dynamics.debug_event_bin = []
            test_advance_turn(self.game)
            
            # Check result
            self.assertFalse(fantasma.alive)
            [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
            self.assertEqual(event.player, fantasma)
            
            [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
            self.assertEqual(event.player, fantasma)
            self.assertEqual(event.cause, PHANTOM)
            self.assertTrue(isinstance(fantasma.role, Spettro))
            self.assertTrue(event.ghost in phantom_roles)
            
            [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == GHOST]
            self.assertEqual(event.player, fantasma)
            self.assertEqual(event.target, negromante)
            self.assertEqual(event.role_name, 'Negromante')
            
            [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == PHANTOM]
            self.assertEqual(event.player, negromante)
            self.assertEqual(event.target, fantasma)
            self.assertEqual(event.role_name, 'Spettro')

    @record_name
    def test_veggente_medium_investigatore_diavolo(self):
        roles = [ Veggente, Medium, Investigatore, Negromante, Lupo, Lupo, Contadino, Contadino, Diavolo ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [medium] = [x for x in players if isinstance(x.role, Medium)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        self.assertTrue(veggente.can_use_power())
        self.assertTrue(medium.can_use_power())
        self.assertTrue(investigatore.can_use_power())
        self.assertEqual(medium.role.get_targets(), [])
        self.assertEqual(investigatore.role.get_targets(), [])
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=diavolo, target=lupo, timestamp=get_now()))
        self.assertFalse(lupo in medium.role.get_targets())
        self.assertFalse(lupo in investigatore.role.get_targets())
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, BLACK)
        self.assertEqual(event.cause, SEER)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_name, Lupo.__name__)
        self.assertEqual(event.cause, DEVIL)
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=lupo, timestamp=get_now()))
        
        # Advance to night
        test_advance_turn(self.game)
        self.assertFalse(lupo.alive)
        test_advance_turn(self.game)
        
        # Use powers
        self.assertFalse(lupo in veggente.role.get_targets())
        self.assertFalse(lupo in diavolo.role.get_targets())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=medium, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=investigatore, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.player, investigatore)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, BLACK)
        self.assertEqual(event.cause, DETECTIVE)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, medium)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_name, lupo.role.__class__.__name__)
        self.assertEqual(event.cause, MEDIUM)
    
    @record_name
    def test_diavolo_on_negromante_faction(self): # Lupus7 new
        roles = [ Contadino, Lupo, Diavolo, Diavolo, Diavolo, Negromante, Fantasma ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [d1, d2, d3] = [x for x in players if isinstance(x.role, Diavolo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [fantasma] = [x for x in players if isinstance(x.role, Fantasma)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=d1, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=d2, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=d3, target=fantasma, timestamp=get_now()))

        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == d1]
        self.assertTrue(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == d2]
        self.assertFalse(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == d3]
        self.assertFalse(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, d1)
        self.assertEqual(event.target, contadino)
        self.assertEqual(event.role_name, Contadino.__name__)
        self.assertEqual(event.cause, DEVIL)
        
    @record_name
    def test_fattucchiera_with_veggente(self):
        roles = [ Veggente, Medium, Investigatore, Negromante, Lupo, Lupo, Contadino, Fattucchiera ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [medium] = [x for x in players if isinstance(x.role, Medium)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, WHITE)
        self.assertEqual(event.cause, SEER)

    @record_name
    def test_multiple_fattucchiere_with_veggente(self):
        roles = [ Veggente, Medium, Investigatore, Negromante, Lupo, Lupo, Fattucchiera, Fattucchiera, Fattucchiera, Fattucchiera ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [medium] = [x for x in players if isinstance(x.role, Medium)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [f1, f2, f3, f4] = [x for x in players if isinstance(x.role, Fattucchiera)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=f1, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=f2, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=f3, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=f4, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, negromante)
        self.assertEqual(event.aura, WHITE)
        self.assertEqual(event.cause, SEER)

    @record_name
    def test_veggente_with_confusione_and_fattucchiera(self): # Lupus7 new
        roles = [ Negromante, Lupo, Fattucchiera, Contadino, Veggente]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
       
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=contadino, timestamp=get_now()))

        # Advance to night create confusione
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=CONFUSIONE, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, target2=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=veggente, timestamp=get_now()))

        # Advance to dawn and check apparent aura
        # Aura should be the real one
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.aura, WHITE)
        
        # Advance to night and use power, with reversed fattucchiera
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, target2=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=negromante, timestamp=get_now()))

        # Check apparent aura
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.aura, BLACK)

    @record_name
    def test_fattucchiera_aura(self): # Lupus7 new
        roles = [ Negromante, Lupo, Fattucchiera, Contadino, Veggente]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
       
        # Advance to night and test aura
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=fattucchiera, timestamp=get_now()))

        # Advance to dawn and check aura
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        
        self.assertEqual(event.target, fattucchiera)
        self.assertEqual(event.aura, WHITE)
        
    @record_name
    def test_trasformista_with_lupo(self):
        roles = [ Trasformista, Messia, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(lupo in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=lupo, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(lupo.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(trasformista.role, Trasformista))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])

    @record_name
    def test_trasformista_with_messia(self):
        roles = [ Trasformista, Messia, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill messia
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(messia in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=messia, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(messia.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(trasformista.role, Trasformista))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])

    @record_name
    def test_trasformista_with_stalker(self):
        roles = [ Trasformista, Stalker, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill stalker
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(stalker in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=stalker, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(stalker.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=stalker, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertTrue(event.success)
        
        self.assertTrue(isinstance(trasformista.role, Stalker))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertEqual(event.target, stalker)
        self.assertEqual(event.role_name, Stalker.__name__)
        
        self.assertEqual(trasformista.team, POPOLANI)
        self.assertEqual(trasformista.aura, WHITE)
        self.assertFalse(trasformista.is_mystic)
        
    @record_name
    def test_trasformista_with_ipnotista(self): # Lupus7 new
        roles = [ Trasformista, Ipnotista, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(ipnotista in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=ipnotista, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(ipnotista.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(trasformista.role, Trasformista))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])
        
    @record_name
    def test_trasformista_with_diavolo(self): # Lupus7 new
        roles = [ Trasformista, Diavolo, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(diavolo in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=diavolo, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=diavolo, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(diavolo.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=diavolo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(trasformista.role, Trasformista))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])
    
    @record_name
    def test_trasformista_with_negromante(self): # Lupus7 new
        roles = [ Trasformista, Messia, Investigatore, Negromante, Negromante, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill negromante
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(negromante in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=negromante, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(negromante.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(trasformista.role, Trasformista))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])

    # Tests not needed anymore (Trasformista cannot become Ipnotista on Lupus7)
    # ~ @record_name
    # ~ def test_trasformista_with_fattucchiera(self):
        # ~ roles = [ Trasformista, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        # ~ self.game = create_test_game(1, roles)
        # ~ dynamics = self.game.get_dynamics()
        # ~ players = self.game.get_players()
        
        # ~ [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        # ~ [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        # ~ [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        # ~ [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        # ~ [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        # ~ [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # ~ # Advance to day and kill fattucchiera
        # ~ test_advance_turn(self.game)
        
        # ~ self.assertTrue(trasformista.can_use_power())
        # ~ self.assertFalse(fattucchiera in trasformista.role.get_targets())
        
        # ~ test_advance_turn(self.game)
        # ~ test_advance_turn(self.game)
        
        # ~ dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=fattucchiera, timestamp=get_now()))
        # ~ dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        # ~ dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fattucchiera, timestamp=get_now()))
        # ~ dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fattucchiera, timestamp=get_now()))
        # ~ dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=fattucchiera, timestamp=get_now()))
        
        # ~ # Advance to night and use power
        # ~ test_advance_turn(self.game)
        # ~ self.assertFalse(fattucchiera.alive)
        # ~ test_advance_turn(self.game)
        
        # ~ dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=fattucchiera, timestamp=get_now()))
        
        # ~ # Advance to dawn and check
        # ~ dynamics.debug_event_bin = []
        # ~ test_advance_turn(self.game)
        # ~ [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        # ~ self.assertEqual(event.player, trasformista)
        # ~ self.assertTrue(event.success)
        
        # ~ self.assertTrue(isinstance(trasformista.role, Fattucchiera))
        
        # ~ [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        # ~ self.assertEqual(event.player, trasformista)
        # ~ self.assertEqual(event.target, fattucchiera)
        # ~ self.assertEqual(event.role_name, Fattucchiera.__name__)
        
        # ~ self.assertEqual(trasformista.team, POPOLANI)
        # ~ self.assertEqual(trasformista.aura, BLACK)
        # ~ self.assertTrue(trasformista.is_mystic)

    @record_name
    def test_trasformista_with_ghostified_investigatore(self):
        roles = [ Trasformista, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill investigatore
        test_advance_turn(self.game)
        
        self.assertTrue(trasformista.can_use_power())
        self.assertFalse(investigatore in trasformista.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=investigatore, timestamp=get_now()))
        
        # Advance to night and ghostify investigatore
        test_advance_turn(self.game)
        self.assertFalse(investigatore.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=investigatore, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to second night and use power
        test_advance_turn(self.game)
        self.assertTrue(isinstance(investigatore.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=investigatore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertTrue(event.success)
        
        self.assertTrue(isinstance(trasformista.role, Investigatore))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        self.assertEqual(event.player, trasformista)
        self.assertEqual(event.target, investigatore)
        self.assertEqual(event.role_name, Investigatore.__name__)
        
        self.assertEqual(trasformista.team, POPOLANI)
        self.assertEqual(trasformista.aura, WHITE)
        self.assertFalse(trasformista.is_mystic)
        
    @record_name
    def test_necrofilo_with_diavolo(self): # Lupus7 new
        roles = [ Necrofilo, Diavolo, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill diavolo
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(diavolo in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=diavolo, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=diavolo, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(diavolo.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=diavolo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertTrue(event.success)
        self.assertTrue(isinstance(necrofilo.role, Diavolo))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertEqual(event.target, diavolo)
        self.assertEqual(event.role_name, Diavolo.__name__)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, diavolo)
        self.assertEqual(event.target, necrofilo)
        self.assertEqual(event.role_name, Necrofilo.__name__)
        
        self.assertEqual(necrofilo.team, LUPI)
        self.assertEqual(necrofilo.aura, BLACK)
        self.assertTrue(necrofilo.is_mystic)
        
    @record_name
    def test_necrofilo_with_lupo(self): # Lupus7 new
        roles = [ Necrofilo, Diavolo, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(lupo in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=diavolo, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=lupo, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(lupo.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertTrue(event.success)
        self.assertTrue(isinstance(necrofilo.role, Lupo))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.role_name, Lupo.__name__)
        
        self.assertEqual(necrofilo.team, LUPI)
        self.assertEqual(necrofilo.aura, BLACK)
        self.assertFalse(necrofilo.is_mystic)
        
    @record_name
    def test_necrofilo_with_ipnotista(self): # Lupus7 new
        roles = [ Necrofilo, Ipnotista, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill ipnotista
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(ipnotista in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=ipnotista, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(ipnotista.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(necrofilo.role, Necrofilo))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])
        
    @record_name
    def test_necrofilo_with_veggente(self): # Lupus7 new
        roles = [ Necrofilo, Veggente, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(veggente in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=veggente, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(veggente.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=veggente, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(necrofilo.role, Necrofilo))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)], [])
        
    @record_name
    def test_messia_with_fattucchiera(self):
        roles = [ Messia, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill fattucchiera
        test_advance_turn(self.game)
        
        self.assertTrue(messia.can_use_power())
        self.assertFalse(fattucchiera in messia.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=fattucchiera, timestamp=get_now()))
        
        # Advance to night and revive fattucchiera
        test_advance_turn(self.game)
        self.assertFalse(fattucchiera.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertTrue(fattucchiera.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)]
        self.assertEqual(event.player, fattucchiera)
        
        # Kill fattucchiera again
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=fattucchiera, timestamp=get_now()))
        
        test_advance_turn(self.game)
        self.assertFalse(fattucchiera.alive)
        
        # Fail a second resurrection
        test_advance_turn(self.game)
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=fattucchiera, timestamp=get_now()))

    @record_name
    def test_messia_with_cacciatore(self):
        roles = [ Messia, Cacciatore, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to second night and use cacciatore power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=contadino, timestamp=get_now()))
        
        # Advance to second day and kill cacciatore
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=cacciatore, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=cacciatore, timestamp=get_now()))
        
        # Advance to third night and revive cacciatore
        test_advance_turn(self.game)
        self.assertFalse(cacciatore.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=cacciatore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertTrue(cacciatore.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)]
        self.assertEqual(event.player, cacciatore)
        
        # Advance to fourth night and check that cacciatore can't use his power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertTrue(cacciatore.alive)
        self.assertFalse(cacciatore.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=investigatore, timestamp=get_now()))

    @record_name
    def test_double_messia_with_cacciatore(self):
        roles = [ Messia, Messia, Cacciatore, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [messia, messia2] = [x for x in players if isinstance(x.role, Messia)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to first night and use cacciatore power
        test_advance_turn(self.game)
        
        # Advance to first day and kill cacciatore
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia2, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=cacciatore, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=cacciatore, timestamp=get_now()))
        
        # Advance to second night and revive cacciatore
        test_advance_turn(self.game)
        self.assertFalse(cacciatore.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia2, target=cacciatore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertTrue(cacciatore.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)]
        self.assertEqual(event.player, cacciatore)

    @record_name
    def test_messia_and_negromante_faq2(self):
        roles = [ Messia, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill investigatore
        test_advance_turn(self.game)
        
        self.assertTrue(messia.can_use_power())
        self.assertFalse(investigatore in messia.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=investigatore, timestamp=get_now()))
        
        # Advance to night and use both powers on investigatore
        test_advance_turn(self.game)
        self.assertFalse(investigatore.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=investigatore, target_ghost=AMNESIA, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=investigatore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertTrue(investigatore.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)]
        self.assertEqual(event.player, investigatore)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante]
        self.assertFalse(event.success)
        self.assertTrue(isinstance(investigatore.role, Investigatore))
        self.assertEqual(investigatore.team, POPOLANI)

    @record_name
    def test_stalker(self):
        roles = [ Stalker, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(event.target, fattucchiera)
        self.assertEqual(event.target2, lupo)
        self.assertEqual(event.player, stalker)
        self.assertEqual(event.cause, STALKER)
        
        # Advance to second night and check that power cannot be used
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(stalker.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=lupo, timestamp=get_now()))

    @record_name
    def test_stalker_with_fixed_player(self):
        roles = [ Stalker, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)], [])

    @record_name
    def test_voyeur(self):
        roles = [ Voyeur, Guardia, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino, Esorcista ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        # Only guardia and esorcista are discovered
        self.assertEqual(len(events), 3)
        for event in events:
            self.assertEqual(event.player, voyeur)
            self.assertTrue(event.target2 == guardia or event.target2 == esorcista or event.target2 == fattucchiera)
            self.assertEqual(event.target, contadino)
            self.assertEqual(event.cause, VOYEUR)
        
        # Advance to second night and check that power cannot be used
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(voyeur.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=lupo, timestamp=get_now()))

    @record_name
    def test_voyeur_and_stalker_with_failures(self):
        roles = [ Voyeur, Stalker, Guardia, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Sequestratore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create Spettro dell'Occultamento
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, timestamp=get_now()))
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=investigatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=guardia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent) and event.player == stalker]
        self.assertEqual(event.target, fattucchiera)
        self.assertEqual(event.target2, lupo)
        self.assertEqual(event.cause, STALKER)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent) and event.player == voyeur]
        self.assertEqual(len(events), 1)
        [event] = events
        self.assertEqual(event.target2, lupo)
        self.assertEqual(event.target, investigatore)
        self.assertEqual(event.cause, VOYEUR)

    @record_name
    def test_avvocato(self):
        roles = [ Avvocato, Negromante, Lupo, Lupo, Sequestratore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [avvocato] = [x for x in players if isinstance(x.role, Avvocato)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to night and use power
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=avvocato, target=lupo, timestamp=get_now()))
        
        # Advance to day and try to kill lupo
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=avvocato, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(lupo.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, ADVOCATE)
        
        # Advance to second night and check can_use_power()
        test_advance_turn(self.game)
        self.assertFalse(avvocato.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=avvocato, target=lupo, timestamp=get_now()))
    
    @record_name
    def test_avvocato2(self):
        roles = [ Avvocato, Negromante, Lupo, Lupo, Sequestratore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [avvocato] = [x for x in players if isinstance(x.role, Avvocato)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to night and use power
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=avvocato, target=lupo, timestamp=get_now()))
        
        # Advance to day and try to kill lupo
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=avvocato, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(lupo.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, ADVOCATE)
        
        # Advance to second night and check can_use_power()
        test_advance_turn(self.game)
        self.assertFalse(avvocato.can_use_power())
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=avvocato, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check that lupo dies
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertFalse(lupo.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.cause, STAKE)
        self.assertEqual(event.player, lupo)
    
    @record_name
    def test_avvocato_with_tie(self):
        roles = [ Avvocato, Negromante, Lupo, Lupo, Sequestratore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [avvocato] = [x for x in players if isinstance(x.role, Avvocato)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to night and use power
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=avvocato, target=lupo, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=avvocato, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=lupo, timestamp=get_now()))
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to sunset and check (lupo is "randomly" chosen to be the one to be killed)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(lupo.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, ADVOCATE)

    @record_name
    def test_esorcista_with_occultamento(self):
        roles = [ Negromante, Lupo, Lupo, Sequestratore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == esorcista]
        self.assertTrue(event.success)
        
        # Advance to fourth night and try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(esorcista.can_use_power())

    @record_name
    def test_esorcista_with_morte(self):
        roles = [ Negromante, Lupo, Lupo, Sequestratore, Esorcista, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=sequestratore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=sequestratore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == veggente]
        self.assertFalse(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == esorcista]
        self.assertTrue(event.success)
        self.assertTrue(sequestratore.alive)

    @record_name
    def test_custode(self): #Lupus7 new
        roles = [ Custode, Negromante, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [custode] = [x for x in players if isinstance(x.role, Custode)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day
        test_advance_turn(self.game)
        self.assertFalse(contadino in negromante.role.get_targets())
        self.assertFalse(contadino in custode.role.get_targets())
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill contadino
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=custode, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        
        # Advance to night
        test_advance_turn(self.game)
        self.assertFalse(contadino.alive)
        test_advance_turn(self.game)
        
        # Negromante and custode act on contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=VISIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=custode, target=contadino, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        self.assertFalse(contadino.alive)
        self.assertTrue(isinstance(contadino.role, Contadino))
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, QuantitativeMovementKnowledgeEvent)]
        self.assertEqual(event.visitors, 1)
        
        # Custode cannot use her power in consecutive nights; negromante can
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertTrue(negromante.can_use_power())
        self.assertFalse(custode.can_use_power())

    @record_name
    def test_sciamano(self):
        roles = [ Negromante, Lupo, Lupo, Sciamano, Esorcista, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sciamano] = [x for x in players if isinstance(x.role, Sciamano)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=sciamano, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(negromante in sciamano.role.get_targets())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=esorcista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sciamano, target=veggente, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == veggente]
        self.assertFalse(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == sciamano]
        self.assertTrue(event.success)
        self.assertTrue(esorcista.alive)
        
        # Advance to fourth night and try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(sciamano.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=sciamano, target=veggente, timestamp=get_now()))

    @record_name
    def test_voyeur_with_spettro(self):
        roles = [ Negromante, Lupo, Lupo, Sciamano, Voyeur, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [sciamano] = [x for x in players if isinstance(x.role, Sciamano)]
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=sciamano, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(negromante in sciamano.role.get_targets())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check (voyeur cannot see ghosts)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == voyeur]
        self.assertTrue(event.success)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)], [])

    @record_name
    def test_amnesia(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=messia, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, MISSING_QUORUM)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.voter == lupo or event.voter == messia)
            self.assertTrue(event.voted == messia)
        self.assertTrue(messia.alive)

    @record_name
    def test_amnesia_and_ipnotista(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night, create ghost and use ipnotista power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=negromante, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=messia, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, MISSING_QUORUM)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.voter == lupo or event.voter == ipnotista)
            self.assertTrue(event.voted == messia)
        self.assertTrue(messia.alive)
        
        # Advance to night and use amnesia power on ipnotista
        test_advance_turn(self.game)
        self.assertTrue(contadino.can_use_power())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, contadino)
        self.assertTrue(event.success)

        # Now vote
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))

        # And all votes go into oblivion
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(event.cause, MISSING_QUORUM)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 0)

    @record_name
    def test_stalker_with_illusione(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino, Stalker ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(event.player, stalker)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.target2, ipnotista)
        self.assertEqual(event.cause, STALKER)
        
        # Advance to fourth night and try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(contadino.can_use_power())

    @record_name
    def test_voyeur_with_illusione(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino, Voyeur ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(event.player, voyeur)
        self.assertEqual(event.target, ipnotista)
        self.assertEqual(event.target2, lupo)
        self.assertEqual(event.cause, VOYEUR)

    @record_name
    def test_voyeur_with_illusione2(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino, Voyeur ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(event.player, voyeur)
        self.assertEqual(event.target, messia)
        self.assertEqual(event.target2, lupo)
        self.assertEqual(event.cause, VOYEUR)
        
    @record_name
    def test_corruzione_on_messia(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Veggente, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
   
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertTrue(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)]
        self.assertEqual(event.player, messia)
        self.assertTrue(isinstance(messia.role, Negromante))
        self.assertEqual(messia.team, NEGROMANTI)
        
        # TODO: Check RoleKnowledgeEvent
        
    @record_name
    def test_corruzione_on_medium(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Medium, Contadino, Contadino, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [medium] = [x for x in players if isinstance(x.role, Medium)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=medium, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertFalse(event.success)
        
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)], [])
        self.assertTrue(isinstance(medium.role, Medium))

    @record_name
    def test_corruzione_on_guardia(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Guardia, Veggente, Veggente, Ipnotista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [veggente, veggente2] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=guardia, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=guardia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertFalse(event.success)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)]
        self.assertEqual(len(events),0)
        self.assertEqual(guardia.team, POPOLANI)

        # Retry on Veggente
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=veggente2, timestamp=get_now()))

    @record_name
    def test_corruzione_on_stregone(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Stregone, Contadino, Contadino, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [stregone] = [x for x in players if isinstance(x.role, Stregone)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stregone, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=stregone, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertFalse(event.success)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)]
        self.assertEqual(len(events),0)
        self.assertEqual(stregone.team, LUPI)

    @record_name
    def test_corruzione_on_fattucchiera(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Fattucchiera, Contadino, Contadino, Veggente]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertFalse(event.success)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)]
        self.assertEqual(len(events),0)
        self.assertEqual(fattucchiera.team, LUPI)
        
    @record_name
    def test_corruzione(self): # Lupus7 new
        roles = [ Negromante, Lupo, Lupo, Mago, Contadino, Contadino, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [mago] = [x for x in players if isinstance(x.role, Mago)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=mago, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and try to create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(contadino.alive)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=CORRUZIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=veggente, timestamp=get_now()))        
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        events = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(events, [])
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, veggente)
        self.assertFalse(veggente.alive)
        
        # Advance to night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=mago, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertTrue(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, CorruptionEvent)]
        self.assertEqual(event.player, mago)
        self.assertTrue(isinstance(mago.role, Negromante))
        self.assertEqual(mago.team, NEGROMANTI)
        
        # TODO: Check RoleKnowledgeEvent

    @record_name
    def test_morte(self): # Update Lupus7
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino, Guardia, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=contadino, timestamp=get_now()))
        
        # Advance to second night and try to create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=MORTE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=veggente, timestamp=get_now()))        
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        events = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(events, [])
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, veggente)
        self.assertFalse(veggente.alive)
        
        # Advance to night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, messia)
        self.assertEqual(event.cause, DEATH_GHOST)
        
        # Advance to night and try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(veggente.can_use_power())
                
        # Advance to night and try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertTrue(veggente.can_use_power())

    @record_name
    def test_morte_with_lupo(self): # Update Lupus7
        roles = [ Negromante, Lupo, Lupo, Messia, Diavolo, Veggente, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=diavolo, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertFalse(event.success)
        self.assertTrue(lupo.alive)
        
        # Advance two nights and try on diavolo  
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=diavolo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertFalse(event.success)
        self.assertTrue(diavolo.alive)

    @record_name
    def test_occultamento(self):
        roles = [ Negromante, Lupo, Lupo, Stalker, Ipnotista, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        self.assertEqual( len([event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]), 1 )
        self.assertTrue(ipnotista.alive)

    @record_name
    def test_occultamento_with_esorcista(self): # Update Lupus7
        roles = [ Negromante, Lupo, Cacciatore, Esorcista, Ipnotista, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, ipnotista)
        self.assertEqual(event.cause, HUNTER)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        self.assertFalse(ipnotista.alive)

    @record_name
    def test_visione(self): # Lupus7 update
        roles = [ Negromante, Lupo, Lupo, Stalker, Ipnotista, Contadino, Guardia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=VISIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.target, ipnotista)
        self.assertEqual(event.role_name, Ipnotista.__name__)
        self.assertEqual(event.cause, VISION_GHOST)

        # Retry with lupo
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(len(events),0)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertFalse(event.success)

    @record_name
    def test_exile_lupi(self):
        roles = [ Negromante, Lupo, Stalker, Ipnotista, Contadino, Rinnegato ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [rinnegato] = [x for x in players if isinstance(x.role, Rinnegato)]
        
        # Advance to day and kill lupo
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        self.assertFalse(lupo.alive)
        self.assertFalse(lupo.active)
        self.assertFalse(rinnegato.active)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.player == lupo or event.player == rinnegato)
            self.assertEqual(event.cause, TEAM_DEFEAT)

    @record_name
    def test_exile_negromanti(self):
        roles = [ Negromante, Lupo, Stalker, Ipnotista, Contadino, Rinnegato ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [rinnegato] = [x for x in players if isinstance(x.role, Rinnegato)]
        
        # Advance to day and kill negromante
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        self.assertFalse(negromante.alive)
        self.assertFalse(negromante.active)
        self.assertFalse(ipnotista.active)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.player == negromante or event.player == ipnotista)
            self.assertEqual(event.cause, TEAM_DEFEAT)

    def test_ghostify_before_exile(self): # Update Lupus7
        roles = [ Negromante, Lupo, Cacciatore, Contadino, Contadino ]

        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

         # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=cacciatore, target=negromante, timestamp=get_now()))

        test_advance_turn(self.game)

        self.assertFalse(contadino.alive) # He's dead

        test_advance_turn(self.game)

        # Now kill negromante who is ghostifying contadino

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=negromante, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Negromante should fail
        self.assertFalse(negromante.active)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player==negromante]
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].success)
        self.assertTrue(isinstance(contadino.role, Contadino))
        self.assertEqual(contadino.team, POPOLANI)

    @record_name
    def test_victory_lupi(self):
        roles = [ Negromante, Lupo, Cacciatore, Ipnotista, Contadino, Rinnegato ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [rinnegato] = [x for x in players if isinstance(x.role, Rinnegato)]
        
        # Advance to day and kill negromante
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=cacciatore, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        self.assertFalse(negromante.alive)
        self.assertFalse(negromante.active)
        self.assertFalse(ipnotista.active)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.player == negromante or event.player == ipnotista)
            self.assertEqual(event.cause, TEAM_DEFEAT)
        
        # Advance to night and kill contadino and cacciatore
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        
        # Advance to dawn and check victory
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertFalse(contadino.alive)
        self.assertFalse(cacciatore.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VictoryEvent)]
        self.assertTrue(event.lupi_win)
        self.assertFalse(event.popolani_win)
        self.assertFalse(event.negromanti_win)
        self.assertEqual(event.cause, NATURAL)

    @record_name
    def test_blocking_roles(self):
        roles = [ Negromante, Lupo, Esorcista, Sequestratore, Sciamano, Contadino]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [sciamano] = [x for x in players if isinstance(x.role, Sciamano)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=sequestratore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=sequestratore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=esorcista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=sequestratore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sciamano, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == sequestratore]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == esorcista]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == sciamano]
        self.assertTrue(event.success)

    @record_name
    def test_disjoint_negromanti(self):
        roles = [ Negromante, Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [n1, n2] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=n1, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and kill messia
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=messia, timestamp=get_now()))
        
        # Advance to third night and try negromanti powers
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n1, target=messia, target_ghost=AMNESIA, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n2, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertFalse(event.success)
        self.assertTrue(isinstance(messia.role, Messia))
        self.assertTrue(isinstance(contadino.role, Contadino))
        
        # Try again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n1, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n2, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertFalse(event.success)
        self.assertTrue(isinstance(messia.role, Messia))
        self.assertTrue(isinstance(contadino.role, Contadino))
        
        # Try again (now it works)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n1, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=n2, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAWN)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertTrue(event.success)
        self.assertTrue(isinstance(messia.role, Messia))
        self.assertTrue(isinstance(contadino.role, Spettro))
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, ILLUSIONE)
        self.assertEqual(event.cause, NECROMANCER)
        
    @record_name
    def test_disjoint_negromanti_with_sequestratore(self): # New Lupus7
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Veggente, Sequestratore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [negromante1, negromante2] = [x for x in players if isinstance(x.role, Negromante)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to night and kill cacciatore
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(cacciatore.alive)
        
        # Kill contadino and try to ghostify cacciatore
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante1, target=cacciatore, target_ghost=ILLUSIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante2, target=cacciatore, target_ghost=VISIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=negromante2, timestamp=get_now()))

        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante1]
        self.assertTrue(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante2]
        self.assertFalse(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertTrue(isinstance(cacciatore.role, Spettro))
        self.assertEqual(event.ghost, ILLUSIONE)
        
        self.assertFalse(contadino.alive)
        
        # Advance to night and kill Veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(veggente.alive)
        
        # Try to ghostify veggente and contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante1, target=veggente, target_ghost=VISIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante2, target=contadino, target_ghost=CONFUSIONE, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=negromante1, timestamp=get_now()))

        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante1]
        self.assertFalse(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == negromante2]
        self.assertTrue(event.success)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertTrue(isinstance(contadino.role, Spettro))
        self.assertEqual(event.ghost, CONFUSIONE)
        
        self.assertTrue(isinstance(veggente.role, Veggente))
        
    @record_name
    def test_negromante_acts_every_turn(self): # Lupus7 new
        roles = [ Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino1, contadino2] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to first day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Put Contadino to stake
        for player in players:
            dynamics.inject_event(CommandEvent(type=VOTE, player=player, target=contadino1, timestamp=get_now()))

        # Advance to sunset and check death
        test_advance_turn(self.game)
        self.assertFalse(contadino1.alive)
        self.assertTrue(negromante.alive)

        # Advance to night, ghostify contadino1 and kill contadino2
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino1, target_ghost=AMNESIA, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino2, timestamp=get_now()))
        
        # Advance to dawn
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino1)
        self.assertEqual(event.ghost, AMNESIA)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino1.role, Spettro))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino2)
        self.assertEqual(event.cause, WOLVES)
        self.assertFalse(contadino2.alive)
        
        # Advance to night, try to ghostify contadino2
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino2, target_ghost=CONFUSIONE, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino2)
        self.assertEqual(event.ghost, CONFUSIONE)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino2.role, Spettro))
        

    @record_name
    def test_fantasma_dies_after_death_ghost(self): # Update Lupus7
        roles = [ Negromante, Lupo, Fantasma, Messia, Ipnotista, Veggente ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [fantasma] = [x for x in players if isinstance(x.role, Fantasma)]
        
        # Advance to day and kill veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to second night and create death ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to second day and kill fantasma
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fantasma, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.cause, STAKE)
        self.assertEqual(event.player, fantasma)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, fantasma)
        self.assertTrue(isinstance(fantasma.role, Spettro))
        self.assertEqual(event.cause, PHANTOM)
    
    @record_name
    def test_double_messia(self):
        roles = [ Messia, Messia, Fattucchiera, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [messia, messia2] = [x for x in players if isinstance(x.role, Messia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill fattucchiera
        test_advance_turn(self.game)
        
        self.assertTrue(messia.can_use_power())
        self.assertFalse(fattucchiera in messia.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia2, target=fattucchiera, timestamp=get_now()))
        
        # Advance to night and twice revive fattucchiera
        test_advance_turn(self.game)
        self.assertFalse(fattucchiera.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia2, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertTrue(fattucchiera.alive)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)]
        self.assertEqual(event.player, fattucchiera)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(len(events), 2)
        self.assertEqual( set([e.player for e in events]), set([messia, messia2]) )
        for event in events:
            self.assertTrue(event.success)
    
    @record_name
    def test_scrutatore(self): #Lupus7 update
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Scrutatore, Scrutatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [scrutatore, scrutatore2] = [x for x in players if isinstance(x.role, Scrutatore)]

        # Advance to night
        test_advance_turn(self.game)
        
        # Use Scrutatore power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=negromante, timestamp=get_now()))
        
        # Advance to day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=scrutatore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 3)
        self.assertEqual(set([e.voter for e in events if e.voted == contadino]), set([contadino, scrutatore]))
        
        # Advance to second night and use power
        test_advance_turn(self.game)
        self.assertFalse(scrutatore.can_use_power())
        self.assertTrue(scrutatore2.can_use_power())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore2, target=negromante, timestamp=get_now()))
        
        # Advance to third day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=negromante, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 0)
        self.assertTrue(negromante.alive)
        
        # Advance to third sunset and check that power is not persistent
        test_advance_turn(self.game)

        self.assertFalse(scrutatore2.can_use_power())
        self.assertTrue(scrutatore.can_use_power())

        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 1)

        # Advance to fourth night and use power
        test_advance_turn(self.game)
        self.assertTrue(scrutatore.can_use_power())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore2, target=ipnotista, timestamp=get_now()))
        
        # Advance to second day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Vote
        dynamics.inject_event(CommandEvent(type=VOTE, player=scrutatore, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=scrutatore2, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 3)
        self.assertEqual(set([e.voter for e in events if e.voted == contadino]), set([contadino, scrutatore, scrutatore2]))
    
    @record_name
    def test_scrutatore_and_amnesia(self):
        roles = [ Negromante, Lupo, Lupo, Messia, Ipnotista, Contadino, Scrutatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [scrutatore] = [x for x in players if isinstance(x.role, Scrutatore)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=scrutatore, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=lupo, target2=messia, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, DAY)
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual(self.game.current_turn.phase, SUNSET)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TallyAnnouncedEvent)]
        self.assertEqual(event.voted, messia)
        self.assertEqual(event.vote_num, 1)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(event.voter, lupo)
        self.assertEqual(event.voted, messia)
    
    @record_name
    def test_scrutatore_on_dead(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Scrutatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [scrutatore] = [x for x in players if isinstance(x.role, Scrutatore)]

        # Advance to night of second day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=contadino, target2=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == scrutatore]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_scrutatore_on_dead2(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Scrutatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [scrutatore] = [x for x in players if isinstance(x.role, Scrutatore)]

        # Advance to night of second day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=negromante, target2=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == scrutatore]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_ipnosi(self): #update Lupus7
        # General Ipnosi behaviour
        roles = [ Ipnotista, Negromante, Lupo, Contadino, Mago ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [mago] = [x for x in players if isinstance(x.role, Mago)]

        # Advance to night and kill mago
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=mago, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, mago)
        
        # Advance to night and ghostify mago
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=mago, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertTrue(event.success)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, mago)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(mago.role, Spettro))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == GHOST]
        self.assertEqual(event.player, mago)
        self.assertEqual(event.target, negromante)
        self.assertEqual(event.role_name, 'Negromante')
        
        # Advance to night and use power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago, target=contadino, target2=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == mago]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(event.voter, contadino)
        self.assertEqual(event.voted, negromante)
        
        # Advance to next sunset and check that the power is not persistent
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(len(events), 0)
    
    @record_name
    def test_ipnosi_on_dead_voter(self): # Update Lupus7
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to first day and kill Cacciatore
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=cacciatore, timestamp=get_now()))
        
        # Advance to night and make ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(cacciatore.alive)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=cacciatore, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(cacciatore.role, Spettro))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=contadino, target2=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == cacciatore]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_ipnosi_on_dead_voted(self): #Update Lpus7
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to first day and kill Cacciatore
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=cacciatore, timestamp=get_now()))
        
        # Advance to night and make ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(cacciatore.alive)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=cacciatore, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, cacciatore)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(cacciatore.role, Spettro))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use power
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=negromante, target2=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == cacciatore]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_ipnosi_not_created_by_ipnotista(self): # New Lupus7
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, ipnotista)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_spettro_created_after_morte(self): # New Lupus7
        roles = [ Veggente, Negromante, Lupo, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, veggente)
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Create Spettro della Morte
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to night
        test_advance_turn(self.game)
        self.assertTrue(isinstance(veggente.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Veggente
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Create Spettro
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, AMNESIA)
        self.assertEqual(event.cause, NECROMANCER)
        
    @record_name
    def test_many_fantasmi(self): # Lupus7 update
        for i in xrange(4):
            # Since this test is repeasted many times, we have to
            # destroy it and delete all users before testing again
            if 'game' in self.__dict__ and self.game is not None:
                self.game.delete()
                self.game = None
            delete_auto_users()
        
            roles = [ Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Fantasma, Negromante, Lupo, Contadino, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore, Cacciatore ]
            phantom_roles = [AMNESIA, CONFUSIONE, ILLUSIONE, IPNOSI, OCCULTAMENTO, VISIONE]
            
            self.game = create_test_game(i, roles)
            dynamics = self.game.get_dynamics()
            players = self.game.get_players()

            fantasmi     = [x for x in players if isinstance(x.role, Fantasma)]
            [negromante] = [x for x in players if isinstance(x.role, Negromante)]
            [lupo]       = [x for x in players if isinstance(x.role, Lupo)]
            [contadino]  = [x for x in players if isinstance(x.role, Contadino)]
            cacciatori   = [x for x in players if isinstance(x.role, Cacciatore)]
            
            self.assertEqual( len(cacciatori), len(fantasmi) )
            self.assertTrue( len(fantasmi) > len(phantom_roles) )
            
            # Advance to second night
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            
            # Kill Fantasmi
            for (i, cacciatore) in enumerate(cacciatori):
                fantasma = fantasmi[i]
                dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=fantasma, timestamp=get_now()))
            
            # Advance to dawn and check
            dynamics.debug_event_bin = []
            test_advance_turn(self.game)
            events = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
            self.assertEqual(set([e.player for e in events]), set(fantasmi))
            
            events = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
            for event in events:
                self.assertTrue(event.player in fantasmi)
                self.assertEqual(event.cause, PHANTOM)
            self.assertEqual(set([e.ghost for e in events]), set(phantom_roles))
            
            # TODO: assert that the right number of GhostificationFailedEvent siano generati
            
            events = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationFailedEvent)]
            self.assertEqual(len(events), len(fantasmi) - len(phantom_roles))
    
    @record_name
    def test_ipnosi_and_scrutatore_with_quorum(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Scrutatore, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, ipnosi] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [scrutatore] = [x for x in players if isinstance(x.role, Scrutatore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill future Spettro dell'Ipnosi
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=ipnosi, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, ipnotista)
        
        
        # Advance to night make ipnosi
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=negromante, target2=ipnosi, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Test
        
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, ipnotista)
        self.assertEqual(event.cause, HYPNOTIST_DEATH)
        self.assertEqual(event.ghost, IPNOSI)

        # Advance to night and use powers
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=contadino, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=contadino, target2=lupo, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=cacciatore, type=VOTE, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check (3 votes, 7 alive players, so quorum is not reached)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        [stake_failed_event] = [event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)]
        self.assertEqual(stake_failed_event.cause, MISSING_QUORUM)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        voters = [event.voter for event in events]
        self.assertEqual(len([x for x in voters if x == contadino]), 1)
        self.assertEqual(len([x for x in voters if x == cacciatore]), 1)
        self.assertEqual(len(voters), 2)
        for event in events:
            self.assertEqual(event.voted, lupo)
            
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TallyAnnouncedEvent)]
        self.assertEqual(event.voted, lupo)
        self.assertEqual(event.vote_num, 3)
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=scrutatore, target=contadino, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=contadino, target2=lupo, timestamp=get_now()))
        
        # Advance to day and vote (kill Lupo)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=cacciatore, type=VOTE, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(player=contadino, type=VOTE, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(player=lupo, type=VOTE, target=lupo, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [kill_event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(kill_event.cause, STAKE)
        self.assertEqual(kill_event.player, lupo)
        self.assertFalse(lupo.canonicalize().alive)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, StakeFailedEvent)], [])
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        voters = [event.voter for event in events]
        self.assertEqual(len([x for x in voters if x == contadino]), 1)
        self.assertEqual(len([x for x in voters if x == cacciatore]), 1)
        self.assertEqual(len([x for x in voters if x == lupo]), 1)
        self.assertEqual(len(voters), 3)
        for event in events:
            self.assertEqual(event.voted, lupo)
            
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TallyAnnouncedEvent)]
        self.assertEqual(event.voted, lupo)
        self.assertEqual(event.vote_num, 4)
    
    @record_name
    def test_disqualification(self):
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Scrutatore, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [scrutatore] = [x for x in players if isinstance(x.role, Scrutatore)]

        # Advance to second night and disqualify Ipnotista
        test_advance_turn(self.game)
        
        disqualification_event = DisqualificationEvent(player=ipnotista, private_message='Fregato!', public_message='L\'ipnotista non ci stava simpatico.', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(exile_event.cause, DISQUALIFICATION)
        self.assertEqual(exile_event.disqualification, disqualification_event)
    
    @record_name
    def test_exiled_mayor(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Fattucchiera, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to night and exile mayor
        test_advance_turn(self.game)
        
        disqualification_event = DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(exile_event.disqualification, disqualification_event)
        self.assertEqual(exile_event.player, negromante)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(exile_event.player, ipnotista)
        
        self.assertFalse(self.game.mayor == negromante)
        num = 0
        for p in players:
            if p is not negromante and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    @record_name
    def test_disqualified_mayor_while_appointing(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Fattucchiera, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to night and exile mayor
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=negromante, type=APPOINT, target=lupo, timestamp=get_now()))
        disqualification_event = DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(exile_event.disqualification, disqualification_event)
        self.assertEqual(exile_event.player, negromante)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(exile_event.player, ipnotista)
        
        self.assertFalse(self.game.mayor == negromante)
        self.assertFalse(self.game.mayor == lupo) # Mayor appointment is not considered when mayor is disqualified
        self.assertFalse(lupo.canonicalize().is_mayor())
    
    @record_name
    def test_exile_mayor_and_appointed_mayor(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Fattucchiera, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to night and appoint
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=negromante, type=APPOINT, target=lupo, timestamp=get_now()))
        
        # Advance to day and exile mayor & appointed mayor
        dynamics.inject_event(DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now()))
        dynamics.inject_event(DisqualificationEvent(player=lupo, private_message='Muhahahahahaha', timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(len(events), 2)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(len(events), 1)
        
        self.assertFalse(self.game.mayor == negromante)
        self.assertFalse(self.game.mayor == lupo)
        self.assertFalse(negromante.canonicalize().is_mayor())
        self.assertFalse(lupo.canonicalize().is_mayor())
        
        num = 0
        for p in players:
            if p is not negromante and p is not lupo and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    @record_name
    def test_exile_appointed_mayor(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Fattucchiera, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to night and appoint
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=negromante, type=APPOINT, target=lupo, timestamp=get_now()))
        
        # Advance to day and exile appointed mayor
        dynamics.inject_event(DisqualificationEvent(player=lupo, private_message='Muhahahahahaha', timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent)]
        self.assertEqual(event.cause, DISQUALIFICATION)
        
        self.assertEqual(self.game.mayor, negromante)
        
        # Advance to day and kill mayor
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(player=negromante, type=VOTE, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(player=contadino, type=VOTE, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(player=fattucchiera, type=VOTE, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(player=ipnotista, type=VOTE, target=negromante, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, negromante)
        
        self.assertFalse(self.game.mayor == negromante)
        self.assertFalse(self.game.mayor == lupo)
        self.assertFalse(negromante.canonicalize().is_mayor())
        self.assertFalse(lupo.canonicalize().is_mayor())
        
        num = 0
        for p in players:
            if p is not negromante and p is not lupo and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    @record_name
    def test_ipnosi_and_ipnotista(self): # Update Lupus7
        # Tests interaction between Ipnotista and Ipnosi on same person 
        # Now tests against Ipnotista instead of Trasformista with Ipnotista power
        roles = [ Ipnotista, Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista1, ipnotista2] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to first day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista1, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=contadino, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        
        # Make Spettro dell'Ipnosi
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=IPNOSI, timestamp=get_now()))

        # Advance to dawn
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista2, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, target2=negromante, timestamp=get_now()))
        
        # Advance to day and vote
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=ipnotista1, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result (Spettro has priority over Ipnotista)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and event.voter == ipnotista2]
        self.assertEqual(event.voter, ipnotista2)
        self.assertEqual(event.voted, ipnotista1)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and event.voter == lupo]
        self.assertEqual(event.voter, lupo)
        self.assertEqual(event.voted, negromante)
        
        # Advance to next day and vote again
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=ipnotista1, timestamp=get_now()))
        
        # Advance to sunset and check that lupo is under ipnotista2's control
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and event.voter == ipnotista2]
        self.assertEqual(event.voter, ipnotista2)
        self.assertEqual(event.voted, ipnotista1)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and event.voter == lupo]
        self.assertEqual(event.voter, lupo)
        self.assertEqual(event.voted, ipnotista1)
    
    @record_name
    def test_ipnosi_on_ipnotista(self): #Update Lupus7
        roles = [ Ipnotista, Ipnotista, Negromante, Lupo, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista1, ipnotista2] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to first day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista1, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=contadino, timestamp=get_now()))
        
        # Advance to sunset and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, contadino)
        
        # Make Spettro dell'Ipnosi
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=IPNOSI, timestamp=get_now()))

        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro), ipnotista1.role)
        
        # Advance to night and use power
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=ipnotista2, target2=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista2, target=negromante, timestamp=get_now()))
        
        # Advance to dawn
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result (Spettro succeeds)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player is contadino]
        self.assertTrue(event.success)
        self.assertFalse(event.sequestrated)
        
        # Advance to next day and (don't) vote
        test_advance_turn(self.game)
        
        # Advance to sunset and check that Spettro power had effect
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        voters = [event.voter for event in events]
        self.assertEqual(len([x for x in voters if x == negromante]), 1)
        self.assertEqual(len([x for x in voters if x == ipnotista2]), 1)
        self.assertEqual(len(voters), 2)
    
    @record_name
    def test_kill_and_disqualify_mayor(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to second night, kill and disqualify mayor
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        disqualification_event = DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(exile_event.disqualification, disqualification_event)
        self.assertEqual(exile_event.player, negromante)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(exile_event.player, ipnotista)
        
        [death_event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(death_event.player, negromante)
        self.assertEqual(death_event.cause, HUNTER)
        
        self.assertFalse(self.game.mayor == negromante)
        num = 0
        for p in players:
            if p is not negromante and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    @record_name
    def test_kill_and_disqualify_mayor_while_appointing(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Lupo, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to second night, kill and disqualify mayor, and make mayor appoint someone
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        disqualification_event = DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=APPOINT, player=negromante, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check (APPOINT command should be ignored)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(exile_event.disqualification, disqualification_event)
        self.assertEqual(exile_event.player, negromante)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(exile_event.player, ipnotista)
        
        [death_event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(death_event.player, negromante)
        self.assertEqual(death_event.cause, HUNTER)
        
        self.assertIsNot(self.game.mayor, negromante)
        self.assertIsNot(self.game.mayor, contadino)
        num = 0
        for p in players:
            if p is not negromante and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    @record_name
    def test_kill_and_disqualify_mayor_while_appointing2(self):
        roles = [ Contadino, Contadino, Negromante, Lupo, Cacciatore, Cacciatore, Ipnotista ]
        self.game = create_test_game(2204, roles)
        
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore1, cacciatore2] = [x for x in players if isinstance(x.role, Cacciatore)]
        
        self.assertEqual(self.game.mayor.user.username, 'pk3')
        self.assertEqual(self.game.mayor, negromante)
        self.assertTrue(negromante.canonicalize().is_mayor())
        
        # Advance to second night, kill and disqualify mayor, and make mayor appoint someone that is going to be killed and exiled too.
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        disqualification_event = DisqualificationEvent(player=negromante, private_message='Muhahaha', timestamp=get_now())
        dynamics.inject_event(disqualification_event)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore1, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore2, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=APPOINT, player=negromante, target=ipnotista, timestamp=get_now()))
        
        # Advance to dawn and check (APPOINT command should be ignored)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == DISQUALIFICATION]
        self.assertEqual(exile_event.disqualification, disqualification_event)
        self.assertEqual(exile_event.player, negromante)
        [exile_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ExileEvent) and event.cause == TEAM_DEFEAT]
        self.assertEqual(exile_event.player, ipnotista)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent) and event.cause == HUNTER]
        self.assertEqual(set([event.player for event in events]), set([negromante, ipnotista]))
        
        self.assertFalse(self.game.mayor == negromante)
        self.assertFalse(self.game.mayor == ipnotista)
        num = 0
        for p in players:
            if p is not negromante and p.canonicalize().is_mayor():
                num += 1
        self.assertEqual(num, 1)
    
    # Tests not needed anymore (Trasformista can only become popolano on Lupus7)
    # @record_name
    # def test_trasformista_on_ipnotista_becoming_immune_to_ipnosi(self):
        # # Tests the immunization against Ipnosi effects
        # # of Trasformista transformed into Ipnotista
        # roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Trasformista ]
        # self.game = create_test_game(1, roles)
        # dynamics = self.game.get_dynamics()
        # players = self.game.get_players()

        # [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        # [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        # [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        # [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        # [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]

        # # Advance to second night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Kill Ipnotista
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        # self.assertEqual(event.player, ipnotista)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        # self.assertEqual(event.player, ipnotista)
        # self.assertEqual(event.ghost, IPNOSI)
        # self.assertEqual(event.cause, HYPNOTIST_DEATH)
        # self.assertTrue(isinstance(ipnotista.role, Spettro))
        
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == GHOST]
        # self.assertEqual(event.player, ipnotista)
        # self.assertEqual(event.target, negromante)
        # self.assertEqual(event.role_name, 'Negromante')
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == HYPNOTIST_DEATH]
        # self.assertEqual(event.player, negromante)
        # self.assertEqual(event.target, ipnotista)
        # self.assertEqual(event.role_name, 'Spettro')
        
        # # Advance to night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Use powers (Ipnosi on Trasformista and Trasformista on Ipnotista)
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista, target=trasformista, target2=contadino, timestamp=get_now()))
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=ipnotista, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == ipnotista]
        # self.assertTrue(event.success)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == trasformista]
        # self.assertTrue(event.success)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        # self.assertEqual(event.player, trasformista)
        # self.assertEqual(event.target, ipnotista)
        # self.assertEqual(event.role_name, Ipnotista.name)
        
        # self.assertTrue(isinstance(trasformista.role, Ipnotista))
        
        # # Advance to sunset
        # test_advance_turn(self.game)
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        
        # # Check result
        # events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        # self.assertEqual(events, [])
        
        # # Advance to next sunset and check
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        
        # events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        # self.assertEqual(events, [])
    
    # @record_name
    # def test_amnesia_on_trasformista_on_ipnosi(self):
        # roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Trasformista, Cacciatore ]
        # self.game = create_test_game(1, roles)
        # dynamics = self.game.get_dynamics()
        # players = self.game.get_players()

        # [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        # [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        # [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        # [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        # [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        # [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # # Advance to second night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Kill Ipnotista and Contadino
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista, timestamp=get_now()))
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=contadino, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # events = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        # self.assertEqual(set([event.player for event in events]), set([ipnotista, contadino]))
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        # self.assertEqual(event.player, ipnotista)
        # self.assertEqual(event.ghost, IPNOSI)
        # self.assertEqual(event.cause, HYPNOTIST_DEATH)
        # self.assertTrue(isinstance(ipnotista.role, Spettro))
        
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == GHOST]
        # self.assertEqual(event.player, ipnotista)
        # self.assertEqual(event.target, negromante)
        # self.assertEqual(event.role_name, 'Negromante')
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent) and event.cause == HYPNOTIST_DEATH]
        # self.assertEqual(event.player, negromante)
        # self.assertEqual(event.target, ipnotista)
        # self.assertEqual(event.role_name, 'Spettro')
        
        # # Advance to night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Make Contadino a Spettro dell'Amnesia
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        # self.assertEqual(event.player, contadino)
        # self.assertEqual(event.ghost, AMNESIA)
        # self.assertEqual(event.cause, NECROMANCER)
        # self.assertTrue(isinstance(ipnotista.role, Spettro))
        
        # # Advance to night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Use powers (Amnesia on Trasformista and Trasformista on Ipnosi)
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=trasformista, timestamp=get_now()))
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=ipnotista, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == contadino]
        # self.assertTrue(event.success)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == trasformista]
        # self.assertTrue(event.success)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        # self.assertEqual(event.player, trasformista)
        # self.assertEqual(event.target, ipnotista)
        # self.assertEqual(event.role_name, Ipnotista.name)
        
        # self.assertTrue(isinstance(trasformista.role, Ipnotista))
        
        # # Advace to day and vote
        # test_advance_turn(self.game)
        
        # dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=negromante, timestamp=get_now()))
        
        # # Advance to sunset
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        
        # # Check result
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        # self.assertEqual(event.voter, trasformista)
        # self.assertEqual(event.voted, negromante)
    
    # @record_name
    # def test_trasformista_on_ipnotista_becoming_immune_to_ipnotista(self):
        # roles = [ Ipnotista, Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Trasformista ]
        # self.game = create_test_game(1, roles)
        # dynamics = self.game.get_dynamics()
        # players = self.game.get_players()

        # [ipnotista1, ipnotista2] = [x for x in players if isinstance(x.role, Ipnotista)]
        # [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        # [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        # [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        # [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]

        # # Advance to second night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Kill Ipnotista1, use Ipnotista2 power on Trasformista
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista1, timestamp=get_now()))
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista2, target=trasformista, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        # self.assertEqual(event.player, ipnotista1)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        # self.assertEqual(event.ghost, IPNOSI)
        # self.assertEqual(event.cause, HYPNOTIST_DEATH)
        # self.assertTrue(isinstance(ipnotista1.role, Spettro), ipnotista1.role)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == ipnotista2]
        # self.assertTrue(event.success)
        
        # self.assertEqual(trasformista.canonicalize().hypnotist, ipnotista2)
        
        # # Advance to night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Use Trasformista power on Ipnotista1
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=ipnotista1, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        # self.assertTrue(event.success)
        # self.assertEqual(event.player, trasformista)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        # self.assertEqual(event.player, trasformista)
        # self.assertEqual(event.target, ipnotista1)
        # self.assertEqual(event.role_name, Ipnotista.name)
        # self.assertTrue(isinstance(trasformista.role, Ipnotista))
        
        # self.assertEqual(trasformista.canonicalize().hypnotist, None)
        
        # # Advance to day and vote
        # test_advance_turn(self.game)
        
        # dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=contadino, timestamp=get_now()))
        
        # # Advance to sunset
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        
        # # Check result
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        # self.assertEqual(event.voter, ipnotista2)
        # self.assertEqual(event.voted, contadino)
    
    # @record_name
    # def test_trasformista_on_ipnotista_becoming_immune_to_ipnotista2(self):
        # # Differently from the previous test, in this test Trasformista is hypnotized in the same night of the transformation.
        # roles = [ Ipnotista, Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino, Trasformista ]
        # self.game = create_test_game(1, roles)
        # dynamics = self.game.get_dynamics()
        # players = self.game.get_players()

        # [ipnotista1, ipnotista2] = [x for x in players if isinstance(x.role, Ipnotista)]
        # [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        # [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        # [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        # [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]

        # # Advance to second night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Kill Ipnotista1
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista1, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        # self.assertEqual(event.player, ipnotista1)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        # self.assertEqual(event.ghost, IPNOSI)
        # self.assertEqual(event.cause, HYPNOTIST_DEATH)
        # self.assertTrue(isinstance(ipnotista1.role, Spettro), ipnotista1.role)
        
        # # Advance to night
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        # test_advance_turn(self.game)
        
        # # Use Trasformista power on Ipnotista1, and Ipnotista2 power on Trasformista
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=trasformista, target=ipnotista1, timestamp=get_now()))
        # dynamics.inject_event(CommandEvent(type=USEPOWER, player=ipnotista2, target=trasformista, timestamp=get_now()))
        
        # # Advance to dawn and check
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == trasformista]
        # self.assertTrue(event.success)
        # self.assertEqual(event.player, trasformista)
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, TransformationEvent)]
        # self.assertEqual(event.player, trasformista)
        # self.assertEqual(event.target, ipnotista1)
        # self.assertEqual(event.role_name, Ipnotista.name)
        # self.assertTrue(isinstance(trasformista.role, Ipnotista))
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == ipnotista2]
        # self.assertTrue(event.success)
        
        # self.assertEqual(trasformista.canonicalize().hypnotist, None)
        
        # # Advance to day and vote
        # test_advance_turn(self.game)
        
        # dynamics.inject_event(CommandEvent(type=VOTE, player=ipnotista2, target=contadino, timestamp=get_now()))
        
        # # Advance to sunset
        # dynamics.debug_event_bin = []
        # test_advance_turn(self.game)
        
        # # Check result
        # [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        # self.assertEqual(event.voter, ipnotista2)
        # self.assertEqual(event.voted, contadino)
    
    @record_name
    def test_ipnosi_and_amnesia(self): #update Lupus7
        # Interaction between Amnesia and Ipnosi
        roles = [ Mago, Negromante, Lupo, Contadino, Cacciatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [mago] = [x for x in players if isinstance(x.role, Mago)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Make Spettro dell'Amnesia
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, AMNESIA)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Ipnotista
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=mago, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player, mago)
        
        # Advance to next night and make spettro
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=mago, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, mago)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(mago.role, Spettro))
        
        # Advance to night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Use powers
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago, target=lupo, target2=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == mago]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) if event.player == contadino]
        self.assertTrue(event.success)
        
        # Advance to sunset
        test_advance_turn(self.game)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result (Amnesia wins over Ipnosi)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent)]
        self.assertEqual(events, [])
    
    @record_name
    def test_divinatore(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Divinatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [lupo1, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [negromante1, negromante2] = [x for x in players if isinstance(x.role, Negromante)]
        [divinatore] = [x for x in players if isinstance(x.role, Divinatore)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        dynamics.debug_event_bin = []
        
        # Inserting Soothsayer propositions
        ref_timestamp = self.game.current_turn.begin
        dynamics.inject_event(SoothsayerModelEvent(player_role=Cacciatore.name, advertised_role=Veggente.name, soothsayer_num=0, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(player_role=Negromante.name, advertised_role=Negromante.name, soothsayer_num=0, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(player_role=Lupo.name, advertised_role=Contadino.name, soothsayer_num=0, timestamp=ref_timestamp))
        dynamics.inject_event(SoothsayerModelEvent(player_role=Contadino.name, advertised_role=Contadino.name, soothsayer_num=0, timestamp=ref_timestamp))
        
        # Check
        events = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(len(events), 4)
        for e in events:
            self.assertEqual(e.player, divinatore)
        
        info = [(e.target, e.role_name) for e in events]
        self.assertTrue((negromante1, Negromante.name) in info or (negromante2, Negromante.name) in info)
        self.assertTrue((cacciatore, Veggente.name) in info)
        self.assertTrue((lupo1, Contadino.name) in info or (lupo2, Contadino.name) in info)
        self.assertTrue((contadino, Contadino.name) in info)

        test_advance_turn(self.game)
    
    @record_name
    def test_divinatore_knowing_about_himself(self):
        roles = [ Contadino, Negromante, Lupo, Divinatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        # Inserting Soothsayer proposition about himself
        ref_timestamp = self.game.current_turn.begin
        with self.assertRaises(IndexError):
            dynamics.inject_event(SoothsayerModelEvent(player_role=Divinatore.name, advertised_role=Divinatore.name, soothsayer_num=0, timestamp=ref_timestamp))
    
    @record_name
    def test_divinatore_knowing_about_another_divinatore(self):
        roles = [ Contadino, Negromante, Lupo, Divinatore, Divinatore ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [divinatore1, divinatore2] = [x for x in players if isinstance(x.role, Divinatore)]
        
        dynamics.debug_event_bin = []
        
        # Inserting Soothsayer proposition about a Soothsayer
        ref_timestamp = self.game.current_turn.begin
        dynamics.inject_event(SoothsayerModelEvent(player_role=Divinatore.name, advertised_role=Divinatore.name, soothsayer_num=0, timestamp=ref_timestamp))
        
        # Check
        events = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertTrue(event.player in [divinatore1, divinatore2])
        if event.player == divinatore1:
            divinatore_target = divinatore2
        else:
            divinatore_target = divinatore1
        
        info = (event.target, event.role_name)
        self.assertTrue((divinatore_target, Divinatore.name) == info)
            
    @record_name
    def test_load_test(self):
        self.game = self.load_game_helper('test.json')

    @record_name
    def test_load_test2(self):
        self.game = self.load_game_helper('mayor_appointing.json')
        players = self.game.get_players()
        self.assertEqual(self.game.get_dynamics().appointed_mayor.user.username, "")

    @record_name
    def test_load_lupus_6(self):
        # Loads lupus 6 dump. Sometimes random kills Davide instead of Julian, causing assertion error later.
        self.game = self.load_game_helper('lupus6.json')
        players = self.game.get_players()
        
    @record_name
    def test_ipnotista_dies_while_negromanti_create_ipnosi(self): # New
        roles = [ Ipnotista, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [ipnotista] = [x for x in players if isinstance(x.role, Ipnotista)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Ipnotista and make Spettro dell'Ipnosi
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=ipnotista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=IPNOSI, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, IPNOSI)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro))
        self.assertFalse(isinstance(ipnotista.role, Spettro))
    
    @record_name    
    def test_messia_fails_on_spettri(self): # Updated Lupus7
        roles = [ Fantasma, Negromante, Lupo, Lupo, Veggente, Cacciatore, Messia, Messia ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [fantasma] = [x for x in players if isinstance(x.role, Fantasma)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [messia1, messia2] = [x for x in players if isinstance(x.role, Messia)]

        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Veggente
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=veggente, timestamp=get_now()))
        
        # Advance to third night, kill Fantasma and ghostify Veggente
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=CORRUZIONE, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event1, event2] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event1.player, veggente)
        self.assertEqual(event1.ghost, CORRUZIONE)
        self.assertEqual(event1.cause, NECROMANCER)
        self.assertTrue(isinstance(veggente.role, Spettro))
        
        self.assertEqual(event2.player, fantasma)
        self.assertEqual(event2.cause, PHANTOM)
        self.assertTrue(isinstance(fantasma.role, Spettro))
                
        # Advance to fourth night and try resurrection
        dynamics.debug_event_bin = []
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia1, target=fantasma, timestamp=get_now()))        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=messia2, target=veggente, timestamp=get_now()))
        
        # Advance to dawn and check
        test_advance_turn(self.game)
        
        self.assertFalse(fantasma.alive)
        self.assertFalse(veggente.alive)
        self.assertTrue([event for event in dynamics.debug_event_bin if isinstance(event, PlayerResurrectsEvent)] == [])
    
    @record_name
    def test_assassino(self): # New
        killedroles = []
        for i in xrange(20):
            # Since this test is repeasted many times, we have to
            # destroy it and delete all users before testing again
            if 'game' in self.__dict__ and self.game is not None:
                self.game.delete()
                self.game = None
            delete_auto_users()
            
            roles = [ Assassino, Negromante, Lupo, Lupo, Contadino, Espansivo, Guardia ]
            self.game = create_test_game(i, roles)
            dynamics = self.game.get_dynamics()
            players = self.game.get_players()

            [negromante] = [x for x in players if isinstance(x.role, Negromante)]
            [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
            [contadino] = [x for x in players if isinstance(x.role, Contadino)]
            [assassino] = [x for x in players if isinstance(x.role, Assassino)]
            [guardia] = [x for x in players if isinstance(x.role, Guardia)]
            [espansivo] = [x for x in players if isinstance(x.role, Espansivo)]

            # Advance to second night
            test_advance_turn(self.game)
            
            self.assertFalse(assassino.role.can_use_power())
            
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
                
            # Assassino kill someone
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino, target=contadino, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=contadino, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=espansivo, target=contadino, timestamp=get_now()))
            
            dynamics.debug_event_bin = []
            test_advance_turn(self.game)
            
            [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
            self.assertEqual(event.cause, ASSASSIN)
            killedroles.append(event.player.get_role_name())
            
        # Check that all players died at least once
        self.assertEqual(len(set(killedroles)), 3) 
    
    @record_name        
    def test_assassino_not_fail(self): # New
        
        roles = [ Assassino, Negromante, Lupo, Lupo, Contadino]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [assassino] = [x for x in players if isinstance(x.role, Assassino)]
        
        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
            
        # Assassino doesn't fail
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino, target=contadino, timestamp=get_now()))
        
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == assassino]
        self.assertTrue(event.success)
        self.assertTrue(assassino.alive)            

    @record_name
    def test_assassino_with_illusione(self): #Lupus7 update
        roles = [ Veggente, Lupo, Negromante, Assassino, Contadino, Sequestratore]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]
        [assassino] = [x for x in players if isinstance(x.role, Assassino)]
        [sequestratore] = [x for x in players if isinstance(x.role, Sequestratore)]

        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=VOTE, player=assassino, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))

        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=ILLUSIONE, timestamp=get_now()))

        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, target2=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=sequestratore, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        # Now, assassino should not target the fake lupo and lupo should not die (because lupo is sequestrated)

        [assassination] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == assassino]
        deaths = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]

        self.assertTrue(assassination.success)
        self.assertEqual(len(deaths),0)

    @record_name        
    def test_assassino_can_kill_other_assassino(self): # New
        
        roles = [ Assassino, Assassino, Negromante, Lupo, Lupo, Contadino]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [assassino1, assassino2] = [x for x in players if isinstance(x.role, Assassino)]
        
        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
            
        # Both Assassini act
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino1, target=contadino, timestamp=get_now()))        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino2, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event1, event2] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertFalse(assassino1.alive)
        self.assertFalse(assassino2.alive)

    @record_name
    def test_assassini_act_independently(self): # New
        killedplayers = set()
        for i in xrange(20):
            # Since this test is repeasted many times, we have to
            # destroy it and delete all users before testing again
            if 'game' in self.__dict__ and self.game is not None:
                self.game.delete()
                self.game = None
            delete_auto_users()
            
            roles = [ Assassino, Assassino, Negromante, Lupo, Lupo, Contadino, Espansivo]
            self.game = create_test_game(i, roles)
            dynamics = self.game.get_dynamics()
            players = self.game.get_players()

            [negromante] = [x for x in players if isinstance(x.role, Negromante)]
            [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
            [contadino] = [x for x in players if isinstance(x.role, Contadino)]
            [assassino1, assassino2] = [x for x in players if isinstance(x.role, Assassino)]
            [espansivo] = [x for x in players if isinstance(x.role, Espansivo)]

            # Advance to night
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
            test_advance_turn(self.game)
        
            # Assassini kill someone
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino1, target=contadino, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino2, target=contadino, timestamp=get_now()))
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=espansivo, target=contadino, timestamp=get_now()))
            
            dynamics.debug_event_bin = []
            test_advance_turn(self.game)
            
            dead = tuple(set([x.get_role_name() for x in players if not x.alive]))
            killedplayers.add(dead)
        
        # Check that all possible couples died at least once
        self.assertEqual(len(killedplayers), 3)
        
    @record_name
    def test_confusione(self): # Update Lupus7
        roles = [ Negromante, Lupo, Lupo, Contadino, Contadino, Diavolo, Diavolo, Veggente, Veggente, Veggente, Veggente, Mago, Mago, Mago, Mago ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]
        [diavolo1, diavolo2] = [x for x in players if isinstance(x.role, Diavolo)]
        [veggente1, veggente2, veggente3, veggente4] = [x for x in players if isinstance(x.role, Veggente)]
        [mago1, mago2, mago3, mago4] = [x for x in players if isinstance(x.role, Mago)]
        
        # Advance to second night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Contadino
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Make Spettro della Confusione
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=CONFUSIONE, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player, contadino)
        self.assertEqual(event.ghost, CONFUSIONE)
        self.assertEqual(event.cause, NECROMANCER)
        self.assertTrue(isinstance(contadino.role, Spettro))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Test everything
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=lupo, target2=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente1, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente2, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente3, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente4, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=diavolo1, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=diavolo2, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago1, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago2, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago3, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago4, target=lupo, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        auras = set([event.aura for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)])
        self.assertEqual(auras, set([WHITE]))
        
        mysticities = set([event.is_mystic for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent)])
        self.assertEqual(mysticities, set([True]))

        roles = [event.role_name for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(len(set(roles)), 1)
        self.assertEqual(roles[0],Negromante.__name__)
        
    @record_name
    def test_confusione_visione(self): # Lupus7 update
        roles = [ Negromante, Lupo, Contadino, Contadino, Veggente]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante]             = [x for x in players if isinstance(x.role, Negromante)]
        [lupo]                   = [x for x in players if isinstance(x.role, Lupo)]
        [contadino1, contadino2] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente]               = [x for x in players if isinstance(x.role, Veggente)]
        
       # Advance to first day and kill contadino1
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo,       target=contadino1, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino1, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente,   target=contadino1, timestamp=get_now()))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Make Spettro VISIONE and kill Contadino2
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino2, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino1, target_ghost=VISIONE, timestamp=get_now()))

        # Advance 2 nights and make Spettro CONFUSIONE
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino2, target_ghost=CONFUSIONE, timestamp=get_now()))

        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # VISIONE checks negromante, CONFUSIONE makes Negromante look like a Veggente
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino1, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino2, target=negromante, target2=veggente, timestamp=get_now()))
        
        # Advance to dawn and check that VISIONE sees a Veggente
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, contadino1)
        self.assertEqual(event.target, negromante)
        self.assertEqual(event.role_name, Veggente.__name__)
        self.assertEqual(event.cause, VISION_GHOST)
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # VISIONE checks negromante, CONFUSIONE makes Negromante look like a Lupo
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino1, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino2, target=negromante, target2=lupo, timestamp=get_now()))
        
        # Advance to dawn and check that VISIONE sees a Lupo
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, RoleKnowledgeEvent)]
        self.assertEqual(event.player, contadino1)
        self.assertEqual(event.target, negromante)
        self.assertEqual(event.role_name, Lupo.__name__)
        self.assertEqual(event.cause, VISION_GHOST)
        
    @record_name
    def test_confusione_visione_fails_on_lupo(self): # Lupus7 update
        roles = [ Negromante, Lupo, Contadino, Contadino, Veggente]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante]             = [x for x in players if isinstance(x.role, Negromante)]
        [lupo]                   = [x for x in players if isinstance(x.role, Lupo)]
        [contadino1, contadino2] = [x for x in players if isinstance(x.role, Contadino)]
        [veggente]               = [x for x in players if isinstance(x.role, Veggente)]
        
        # Advance to first day and kill contadino1
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino1, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino1, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=veggente, target=contadino1, timestamp=get_now()))
        
        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Make Spettro VISIONE and kill Contadino2
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino2, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino1, target_ghost=VISIONE, timestamp=get_now()))

        # Advance 2 nights and make Spettro CONFUSIONE
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino2, target_ghost=CONFUSIONE, timestamp=get_now()))

        # Advance to next night
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # VISIONE checks Lupo, CONFUSIONE makes Lupo look like a Negromante
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino1, target=lupo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino2, target=lupo, target2=negromante, timestamp=get_now()))
        
        # Check that VISIONE fails
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino1]
        self.assertFalse(event.success)
        
    @record_name
    def test_lupi_and_negromanti_not_ghostified(self): # Update Lupus7
        roles = [ Negromante, Lupo, Lupo, Contadino, Cacciatore, Diavolo, Assassino, Medium ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo1, lupo2] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [diavolo] = [x for x in players if isinstance(x.role, Diavolo)]
        [assassino] = [x for x in players if isinstance(x.role, Assassino)]        
        [medium] = [x for x in players if isinstance(x.role, Medium)]
        
        # Advance to first day and kill Diavolo
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo1, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo2, target=diavolo, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=assassino, target=diavolo, timestamp=get_now()))
        
        # Advance to next night, try ghostification
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=diavolo, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(isinstance(diavolo.role, Diavolo))
        
        # Advance to next day and kill Assassino
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo1, target=assassino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=assassino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=assassino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo2, target=assassino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=assassino, target=assassino, timestamp=get_now()))
        
        # Advance to next night and try ghostification
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(assassino.alive)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=assassino, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(isinstance(assassino.role, Assassino))
        
        # Advance to next day and kill Lupo2
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo1, target=lupo2, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=lupo2, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=lupo2, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo2, target=lupo2, timestamp=get_now()))
        
        # Advance to next night and try ghostification
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(lupo2.alive)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=lupo2, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(isinstance(lupo2.role, Lupo))
        
        # Advance to next day and kill Medium
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo1, target=medium, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=medium, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=medium, target=medium, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=medium, timestamp=get_now()))
        
        # Advance to next night and try ghostification
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertFalse(medium.alive)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=medium, target_ghost=AMNESIA, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        self.assertTrue(isinstance(medium.role, Medium))
        
        
    @record_name
    def test_stregone(self): # Lupus7 update
        roles = [ Negromante, Lupo, Lupo, Trasformista, Stregone, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [trasformista] = [x for x in players if isinstance(x.role, Trasformista)]
        [stregone] = [x for x in players if isinstance(x.role, Stregone)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=trasformista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=stregone, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=VISIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=trasformista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stregone, target=trasformista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=trasformista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == lupo]
        self.assertFalse(event.success)
        self.assertTrue(trasformista.alive)
        
    @record_name
    def test_cyclic_block(self): #New
        roles = [ Negromante, Lupo, Lupo, Esorcista, Stregone, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [stregone] = [x for x in players if isinstance(x.role, Stregone)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=stregone, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=OCCULTAMENTO, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stregone, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.success]
        self.assertEqual(len(events), 1)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and not event.success]
        self.assertEqual(len(events), 2)
    
    @record_name
    def test_no_movement_knowledge_event(self):
        roles = [ Voyeur, Stalker, Guardia, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino, Esorcista ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [guardia] = [x for x in players if isinstance(x.role, Guardia)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        
        # Advance to night and use powers
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=voyeur, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent) and event.cause == VOYEUR]
        
        self.assertEqual(len(events), 3)
        for event in events:
            self.assertEqual(event.player, voyeur)
            self.assertTrue(event.target2 == guardia or event.target2 == esorcista or event.target2 == fattucchiera)
            self.assertEqual(event.target, contadino)
            self.assertEqual(event.cause, VOYEUR)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent) and event.cause == STALKER]
        self.assertEqual(event.player, stalker)
        self.assertEqual(event.target, voyeur)
        self.assertEqual(event.target2, contadino)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, NoMovementKnowledgeEvent)]
        self.assertEqual(len(events), 0)
        
        # Advance to second night and check that power cannot be used
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(voyeur.can_use_power())
        self.assertFalse(stalker.can_use_power())
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=stalker, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        events = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        self.assertEqual(len(events), 0)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NoMovementKnowledgeEvent) and event.cause == VOYEUR]
        self.assertEqual(event.player, voyeur)
        self.assertEqual(event.target, contadino)
        self.assertEqual(event.cause, VOYEUR)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NoMovementKnowledgeEvent) and event.cause == STALKER]
        self.assertEqual(event.player, stalker)
        self.assertEqual(event.target, fattucchiera)
        self.assertEqual(event.cause, STALKER)
        
    @record_name
    def test_everybody_dies(self): # Update Lupus7
        roles=[Veggente, Cacciatore, Lupo, Assassino, Negromante]
        self.game = create_test_game(1,roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [assassino] = [x for x in players if isinstance(x.role, Assassino)]
        [cacciatore] = [x for x in players if isinstance(x.role, Cacciatore)]
        [veggente] = [x for x in players if isinstance(x.role, Veggente)]

        #Advance to day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=assassino, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=veggente, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=cacciatore, target=veggente, timestamp=get_now()))
        
        #Advance to night and create MORTE
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=veggente, target_ghost=MORTE, timestamp=get_now()))
        
        #Advance to second night and kill everybody
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=cacciatore, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=assassino, target=cacciatore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=assassino, timestamp=get_now()))
        
        test_advance_turn(self.game)

        self.assertEqual(len(self.game.get_alive_players()),0)
        
    @record_name
    def test_game_over_flag(self):
        roles=[Contadino,Lupo,Negromante]
        self.game = create_test_game(1,roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]

        self.assertEqual(self.game.over, False)

        #Advance to day and kill negromante
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=negromante, timestamp=get_now()))

        test_advance_turn(self.game) # To sunset

        self.assertEqual(dynamics.over, False) #Game should not be over yet

        test_advance_turn(self.game) # To night

        self.assertEqual(dynamics.over, False) #Not yet...

        dynamics.inject_event(CommandEvent(type=USEPOWER, player=lupo, target=contadino, timestamp=get_now()))

        test_advance_turn(self.game) # To dawn

        self.assertEqual(dynamics.over, True) #Now!

        test_advance_turn(self.game)

        self.assertEqual(dynamics.over, True) #Still over!
