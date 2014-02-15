import datetime
from django.utils import timezone

from django.test import TestCase

from game.models import *
from game.roles import *
from game.events import *


def create_users(n):
    for i in xrange(n):
        user = User.objects.create(username='pk%d' % (i), first_name='Paperinik', last_name='%d' % (i), email='', password='ciaociao')
        user.save()


def create_test_game(seed, roles):
    game = Game(running=True)
    game.save()
    game.initialize(datetime.now(tz=REF_TZINFO))

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
    turn.end = datetime.now(tz=REF_TZINFO)
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

    def test_game_setup(self):
        roles = [ Contadino, Contadino, Contadino, Contadino, Lupo, Lupo, Negromante, Fattucchiera, Ipnotista, Ipnotista ]
        game = create_test_game(2204, roles)

        self.assertEqual(game.mayor().user.username, 'pk4')

        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)
        test_advance_turn(game)
