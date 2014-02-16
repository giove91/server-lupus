import datetime
from django.utils import timezone

from django.test import TestCase

from game.models import *
from game.roles import *
from game.events import *
from game.utils import get_now


def create_users(n):
    for i in xrange(n):
        user = User.objects.create(username='pk%d' % (i), first_name='Paperinik', last_name='%d' % (i), email='', password='ciaociao')
        user.save()


def create_test_game(seed, roles):
    game = Game(running=True)
    game.save()
    game.initialize(get_now())

    create_users(len(roles))

    users = User.objects.all()
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


def test_advance_turn(game):
    turn = game.current_turn
    turn.end = get_now()
    turn.save()
    game.advance_turn()


class TurnTests(TestCase):
    
    def test_next_turn(self):
        # Checks that the order of phases is correct
        game = Game()
        first_turn = Turn(game=game, date=0, phase=CREATION)
        
        second_turn = first_turn.next_turn()
        self.assertEqual(second_turn.date, 1)
        self.assertEqual(second_turn.phase, NIGHT)
        
        third_turn = second_turn.next_turn()
        self.assertEqual(third_turn.date, 1)
        self.assertEqual(third_turn.phase, DAWN)
        
        fourth_turn = third_turn.next_turn()
        self.assertEqual(fourth_turn.date, 1)
        self.assertEqual(fourth_turn.phase, DAY)
        
        fifth_turn = fourth_turn.next_turn()
        self.assertEqual(fifth_turn.date, 1)
        self.assertEqual(fifth_turn.phase, SUNSET)
        
        sixth_turn = fifth_turn.next_turn()
        self.assertEqual(sixth_turn.date, 2)
        self.assertEqual(sixth_turn.phase, NIGHT)
        
        turn = sixth_turn
        for i in xrange(20):
            turn = turn.next_turn()
        self.assertEqual(turn.date, 7)
        self.assertEqual(turn.phase, NIGHT)


class GameTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        # Destroy the leftover dynamics without showing the slightest
        # sign of mercy
        kill_all_dynamics()

    def test_game_setup(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        game = create_test_game(2204, roles)

        self.assertEqual(game.current_turn.phase, CREATION)
        self.assertEqual(game.mayor().user.username, 'pk4')

    def test_turn_advance(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        game = create_test_game(2204, roles)

        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)

        self.assertEqual(game.current_turn.phase, DAY)

        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)

        self.assertEqual(game.current_turn.phase, DAWN)

    def voting_helper(self, roles, mayor_votes, stake_votes, expected_mayor, expect_to_die):
        if mayor_votes is not None:
            self.assertEqual(len(roles), len(mayor_votes))
        if stake_votes is not None:
            self.assertEqual(len(roles), len(stake_votes))

        # The seed is chosen so that the first player is the mayor
        game = create_test_game(1, roles)
        dynamics = game.get_dynamics()
        players = game.get_players()
        initial_mayor = game.mayor()

        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)

        self.assertEqual(game.current_turn.phase, DAY)
        self.assertEqual(game.mayor().pk, players[0].pk)

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
        if expect_to_die is not None:
            [kill_event] = [event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)]
            self.assertEqual(kill_event.cause, STAKE)
            self.assertEqual(kill_event.player.pk, players[expect_to_die].pk)
            self.assertFalse(players[expect_to_die].canonicalize().alive)
        else:
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, PlayerDiesEvent)], [])

        if expected_mayor is not None:
            [mayor_event] = [event for event in dynamics.debug_event_bin if isinstance(event, ElectNewMayorEvent)]
            self.assertEqual(mayor_event.player.pk, players[expected_mayor].pk)
            self.assertTrue(players[expected_mayor].is_mayor())
            self.assertEqual(game.mayor().pk, players[expected_mayor].pk)
        else:
            self.assertEqual([event for event in dynamics.debug_event_bin if isinstance(event, ElectNewMayorEvent)], [])
            self.assertEqual(game.mayor().pk, initial_mayor.pk)

        dynamics.debug_event_bin = None

    def test_stake_vote_unanimity(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
        self.voting_helper(roles, None, votes, None, 0)

    def test_stake_vote_absolute_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 1, 1, 2, None ]
        self.voting_helper(roles, None, votes, None, 0)

    def test_stake_vote_relative_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 1, 1, 1, 2, None, None ]
        self.voting_helper(roles, None, votes, None, 0)

    def test_stake_vote_tie_with_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 1, 1, 1, 3, 4, None, None ]
        self.voting_helper(roles, None, votes, None, 0)

    def test_stake_vote_tie_without_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 2, 0, 0, 1, 1, 1, 0, 4, None, None ]
        self.voting_helper(roles, None, votes, None, 1)

    def test_stake_vote_no_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, None, None, None, None, None, None, None, None ]
        self.voting_helper(roles, None, votes, None, None)

    def test_stake_vote_half_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, None, None, None, None, None ]
        self.voting_helper(roles, None, votes, None, 0)

    def test_stake_vote_mayor_not_voting(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ None, 0, 0, 0, 0, 0, 0, None, None, None ]
        self.voting_helper(roles, None, votes, None, 0)


    def test_election_unanimity(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
        self.voting_helper(roles, votes, None, 0, None)

    def test_election_absolute_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, 0, 1, 1, 2, None ]
        self.voting_helper(roles, votes, None, 0, None)

    def test_election_relative_majority(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 1, 1, 1, 2, None, None ]
        self.voting_helper(roles, votes, None, None, None)

    def test_election_tie_with_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 1, 1, 1, 3, 4, None, None ]
        self.voting_helper(roles, votes, None, None, None)

    def test_election_tie_without_mayor(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 2, 0, 0, 1, 1, 1, 0, 4, None, None ]
        self.voting_helper(roles, votes, None, None, None)

    def test_election_no_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, None, None, None, None, None, None, None, None ]
        self.voting_helper(roles, votes, None, None, None)

    def test_election_half_quorum(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ 0, 0, 0, 0, 0, None, None, None, None, None ]
        self.voting_helper(roles, votes, None, None, None)

    def test_election_mayor_not_voting(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        votes = [ None, 0, 0, 0, 0, 0, 0, None, None, None ]
        self.voting_helper(roles, votes, None, 0, None)


    def test_composite_election_same_mayor(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        mayor_votes = [ 1, 1, 1, 1, 2, 2, 0, 0, 0, 0 ]
        stake_votes = [ 2, 3, 2, 3, 2, 3, None, None, None, None ]
        self.voting_helper(roles, mayor_votes, stake_votes, None, 2)

    def test_composite_election_change_mayor(self):
        # Here we make use of the fact that the mayor is 0 in the
        # beginning
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        mayor_votes = [ 1, 1, 1, 1, 1, 1, 0, 0, 0, 0 ]
        stake_votes = [ 2, 3, 2, 3, 2, 3, None, None, None, None ]
        self.voting_helper(roles, mayor_votes, stake_votes, 1, 3)
