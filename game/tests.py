import datetime
from django.utils import timezone

from django.test import TestCase

from game.models import *


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
