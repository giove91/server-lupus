from game.models import *


def setup_game():
    Game.objects.create()


def setup_dummy_players():
    g = Game.objects.get()
    users = User.objects.all()
    for user in users:
        Player.objects.create(user=user, game=g)
    
