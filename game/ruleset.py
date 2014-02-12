from game.models import *
from game.roles import *
from game.constants import *


def setup_game():
    game = Game(running=True)
    game.save()
    turn = Turn(game=game, date=1, phase=NIGHT)
    turn.save()
    game.current_turn=turn
    game.save()


def setup_dummy_players():
    g = Game.objects.get()
    users = User.objects.all()
    for user in users:
        r = Cacciatore()
        r.save()
        Player.objects.create(user=user, game=g, role=r, team=POPOLANI, aura=WHITE)
