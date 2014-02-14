
from game.models import *
from game.roles import *
from game.constants import *
from game.events import *

import datetime

def setup_game():
    game = Game(running=True)
    game.save()
    game.initialize(datetime.date.today())

    users = User.objects.all()
    for user in users:
        player = Player.objects.create(user=user, game=game)
        player.save()

    event = SeedEvent(seed=2204)
    game.get_dynamics().inject_event(event)

    roles = [ Contadino, Lupo, Negromante, Fattucchiera ]
    for i, user in enumerate(users):
        event = AvailableRoleEvent(role_name=roles[i%len(roles)].__name__)
        game.get_dynamics().inject_event(event)
