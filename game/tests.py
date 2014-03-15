
import sys
import datetime
import json
import os

from django.utils import timezone

from django.test import TestCase

from game.models import *
from game.roles import *
from game.events import *
from game.utils import get_now


def create_users(n):
    users = []
    for i in xrange(n):
        user = User.objects.create(username='pk%d' % (i), first_name='Paperinik', last_name='%d' % (i), email='', password='ciaociao')
        user.save()
        users.append(user)
    return users


def delete_auto_users():
    for user in User.objects.all():
        if user.username.startswith('pk'):
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


def create_game_from_dump(data):
    game = Game(running=True)
    game.save()
    game.initialize(get_now())

    for player_data in data['players']:
        user = User.objects.create(username=player_data['username'], first_name=player_data['username'])
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
    for turn_data in data['turns']:
        current_turn = game.current_turn
        for event_data in turn_data['events']:
            event = Event.from_dict(event_data, players_map)
            if current_turn.phase in FULL_PHASES:
                event.timestamp = get_now()
            else:
                event.timestamp = current_turn.begin
            #print >> sys.stderr, "Injecting event of type %s" % (event.subclass)
            game.get_dynamics().inject_event(event)
        test_advance_turn(game)

    return game


def test_advance_turn(game):
    turn = game.current_turn
    turn.end = get_now()
    turn.save()
    game.advance_turn()


def record_name(f):
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
            [mayor_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ElectNewMayorEvent)]
            self.assertEqual(mayor_event.player.pk, players[expected_mayor].pk)
            if expect_to_die is None or expect_to_die != expected_mayor:
                self.assertTrue(players[expected_mayor].is_mayor())
            mayor_after_election = players[expected_mayor]
        else:
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, ElectNewMayorEvent)], [])
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
    def test_lupo_on_negromante(self):
        roles = [ Cacciatore, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, lupo2] = [x for x in players if isinstance(x.role, Lupo)]

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
    def test_disjoint_lupi_with_sequestratore(self):
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
        self.assertFalse(event.success)

        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])
        self.assertTrue(cacciatore.alive)

        dynamics.debug_event_bin = None

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
    def test_mago_and_mistificazione(self):
        roles = [ Mago, Negromante, Negromante, Lupo, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [mago] = [x for x in players if isinstance(x.role, Mago)]
        [negromante, _] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]

        # Test on Negromante
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago, target=negromante, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent)]
        self.assertEqual(event.player, mago)
        self.assertEqual(event.target, negromante)
        self.assertEqual(event.cause, MAGE)
        self.assertEqual(event.is_mystic, True)

        dynamics.debug_event_bin = None
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # Test on Lupo
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=mago, target=lupo, timestamp=get_now()))

        dynamics.debug_event_bin = []
        test_advance_turn(self.game)

        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MysticityKnowledgeEvent)]
        self.assertEqual(event.player, mago)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.cause, MAGE)
        self.assertEqual(event.is_mystic, False)

        dynamics.debug_event_bin = None
        test_advance_turn(self.game)
        test_advance_turn(self.game)

        # TODO: test with Spettro della Mistificazione

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

        dynamics.debug_event_bin = None
    
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
    
    @record_name
    def test_fantasma(self):
        roles = [ Fantasma, Negromante, Lupo, Contadino, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()

        [fantasma] = [x for x in players if isinstance(x.role, Fantasma)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino, _] = [x for x in players if isinstance(x.role, Contadino)]

        # Advance to day
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        # Kill Fantasma
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fantasma, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fantasma, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fantasma, timestamp=get_now()))
        
        # Advance to sunset
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        # Check result
        self.assertFalse(fantasma.alive)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
        self.assertEqual(event.player,fantasma)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, GhostificationEvent)]
        self.assertEqual(event.player,fantasma)
        self.assertEqual(event.cause,PHANTOM)
        self.assertTrue(isinstance(fantasma.role, Spettro))

    @record_name
    def test_custode(self):
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
        
        # Custode cannot use her power on the same target in consecutive nights; negromante can
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        self.assertTrue(negromante.can_use_power())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=MORTE, timestamp=get_now()))
        self.assertTrue(custode.can_use_power())
        with self.assertRaises(AssertionError):
            dynamics.inject_event(CommandEvent(type=USEPOWER, player=custode, target=contadino, timestamp=get_now()))

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
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, MediumKnowledgeEvent)]
        self.assertEqual(event.player, medium)
        self.assertEqual(event.target, lupo)
        self.assertEqual(event.aura, BLACK)
        self.assertFalse(event.is_ghost)
        self.assertEqual(event.cause, MEDIUM)

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
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=veggente, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, AuraKnowledgeEvent)]
        self.assertEqual(event.player, veggente)
        self.assertEqual(event.target, fattucchiera)
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
    def test_necrofilo_with_lupo(self):
        roles = [ Necrofilo, Messia, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
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
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=lupo, timestamp=get_now()))
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
        self.assertFalse(event.success)
        self.assertTrue(isinstance(lupo.role, Lupo))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, NecrofilizationEvent)], [])

    @record_name
    def test_necrofilo_with_messia(self):
        roles = [ Necrofilo, Messia, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [messia] = [x for x in players if isinstance(x.role, Messia)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill messia
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(messia in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=messia, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=messia, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=messia, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(messia.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=messia, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertFalse(event.success)
        self.assertTrue(isinstance(necrofilo.role, Necrofilo))
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, NecrofilizationEvent)], [])

    @record_name
    def test_necrofilo_with_stalker(self):
        roles = [ Necrofilo, Stalker, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [stalker] = [x for x in players if isinstance(x.role, Stalker)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill stalker
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(stalker in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=stalker, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=stalker, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=stalker, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(stalker.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=stalker, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertTrue(event.success)
        
        self.assertTrue(isinstance(necrofilo.role, Stalker))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NecrofilizationEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertEqual(event.target, stalker)
        self.assertEqual(event.role_name, Stalker.__name__)
        
        self.assertEqual(necrofilo.team, POPOLANI)
        self.assertEqual(necrofilo.aura, WHITE)
        self.assertFalse(necrofilo.is_mystic)

    @record_name
    def test_necrofilo_with_fattucchiera(self):
        roles = [ Necrofilo, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill fattucchiera
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(fattucchiera in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=contadino, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=investigatore, target=fattucchiera, timestamp=get_now()))
        
        # Advance to night and use power
        test_advance_turn(self.game)
        self.assertFalse(fattucchiera.alive)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertTrue(event.success)
        
        self.assertTrue(isinstance(necrofilo.role, Fattucchiera))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NecrofilizationEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertEqual(event.target, fattucchiera)
        self.assertEqual(event.role_name, Fattucchiera.__name__)
        
        self.assertEqual(necrofilo.team, POPOLANI)
        self.assertEqual(necrofilo.aura, BLACK)
        self.assertTrue(necrofilo.is_mystic)

    @record_name
    def test_necrofilo_with_ghostified_investigatore(self):
        roles = [ Necrofilo, Fattucchiera, Investigatore, Negromante, Lupo, Lupo, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [necrofilo] = [x for x in players if isinstance(x.role, Necrofilo)]
        [fattucchiera] = [x for x in players if isinstance(x.role, Fattucchiera)]
        [investigatore] = [x for x in players if isinstance(x.role, Investigatore)]
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill investigatore
        test_advance_turn(self.game)
        
        self.assertTrue(necrofilo.can_use_power())
        self.assertFalse(investigatore in necrofilo.role.get_targets())
        
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=necrofilo, target=investigatore, timestamp=get_now()))
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
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=necrofilo, target=investigatore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertTrue(event.success)
        
        self.assertTrue(isinstance(necrofilo.role, Investigatore))
        
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, NecrofilizationEvent)]
        self.assertEqual(event.player, necrofilo)
        self.assertEqual(event.target, investigatore)
        self.assertEqual(event.role_name, Investigatore.__name__)
        
        self.assertEqual(necrofilo.team, POPOLANI)
        self.assertEqual(necrofilo.aura, WHITE)
        self.assertFalse(necrofilo.is_mystic)

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
    def test_messia_and_negromante(self):
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
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=investigatore, target_ghost=DUPLICAZIONE, timestamp=get_now()))
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
    def test_stalker_with_reflexive_player(self):
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
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)], [])

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
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=guardia, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=fattucchiera, target=fattucchiera, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=fattucchiera, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        events = [event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)]
        # Only guardia and esorcista are discovered
        self.assertEqual(len(events), 2)
        for event in events:
            self.assertEqual(event.player, voyeur)
            self.assertTrue(event.target2 == guardia or event.target2 == esorcista)
            self.assertEqual(event.target, fattucchiera)
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
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=esorcista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=esorcista, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == esorcista]
        self.assertTrue(event.success)

    @record_name
    def test_esorcista_with_morte(self):
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
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=sequestratore, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=esorcista, target=sequestratore, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == esorcista]
        self.assertTrue(event.success)
        self.assertTrue(sequestratore.alive)

    @record_name
    def test_profanatore(self):
        roles = [ Negromante, Lupo, Lupo, Profanatore, Esorcista, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [profanatore] = [x for x in players if isinstance(x.role, Profanatore)]
        [esorcista] = [x for x in players if isinstance(x.role, Esorcista)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=profanatore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=esorcista, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=MORTE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(negromante in profanatore.role.get_targets())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=esorcista, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=profanatore, target=contadino, timestamp=get_now()))
        
        # Advance to dawn and check
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertFalse(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == profanatore]
        self.assertTrue(event.success)
        self.assertTrue(esorcista.alive)

    @record_name
    def test_voyeur_with_spettro(self):
        roles = [ Negromante, Lupo, Lupo, Profanatore, Voyeur, Contadino ]
        self.game = create_test_game(1, roles)
        dynamics = self.game.get_dynamics()
        players = self.game.get_players()
        
        [negromante] = [x for x in players if isinstance(x.role, Negromante)]
        [lupo, _] = [x for x in players if isinstance(x.role, Lupo)]
        [profanatore] = [x for x in players if isinstance(x.role, Profanatore)]
        [voyeur] = [x for x in players if isinstance(x.role, Voyeur)]
        [contadino] = [x for x in players if isinstance(x.role, Contadino)]
        
        # Advance to day and kill contadino
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        dynamics.inject_event(CommandEvent(type=VOTE, player=profanatore, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=voyeur, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=negromante, target=contadino, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=VOTE, player=lupo, target=contadino, timestamp=get_now()))
        
        # Advance to second night and create ghost
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=negromante, target=contadino, target_ghost=DUPLICAZIONE, timestamp=get_now()))
        
        # Advance to third night and use powers
        test_advance_turn(self.game)
        self.assertTrue(isinstance(contadino.role, Spettro))
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        test_advance_turn(self.game)
        
        self.assertFalse(negromante in profanatore.role.get_targets())
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=contadino, target=negromante, timestamp=get_now()))
        dynamics.inject_event(CommandEvent(type=USEPOWER, player=voyeur, target=negromante, timestamp=get_now()))
        
        # Advance to dawn and check (voyeur cannot see spettro)
        dynamics.debug_event_bin = []
        test_advance_turn(self.game)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == contadino]
        self.assertTrue(event.success)
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, PowerOutcomeEvent) and event.player == voyeur]
        self.assertTrue(event.success)
        self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, MovementKnowledgeEvent)], [])

    @record_name
    def test_load_test(self):
        self.game = self.load_game_helper('test.json')

    @record_name
    def test_load_test2(self):
        self.game = self.load_game_helper('mayor_appointing.json')
        players = self.game.get_players()
        self.assertEqual(self.game.get_dynamics().appointed_mayor.user.username, "")
