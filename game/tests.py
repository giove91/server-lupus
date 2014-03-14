
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
        test_advance_turn(self.game)
        
        # Check result
        [event] = [event for event in dynamics.debug_event_bin if isinstance(event, VoteAnnouncedEvent) and event.voter == contadino]
        self.assertEqual(event.voted, negromante)


    @record_name
    def test_load_test(self):
        self.game = self.load_game_helper('test.json')

    @record_name
    def test_load_test2(self):
        self.game = self.load_game_helper('mayor_appointing.json')
        players = self.game.get_players()
        self.assertEqual(self.game.get_dynamics().appointed_mayor.user.username, "")
