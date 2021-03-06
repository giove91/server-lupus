
from game.models import *
from game.roles import *
from game.constants import *
from game.events import *
from game.utils import get_now

import datetime

def setup_game(begin):
    game = Game(running=True)
    game.save()
    game.initialize(begin)

    users = User.objects.all()
    for user in users:
        if user.is_staff:
            continue
        player = Player.objects.create(user=user, game=game)
        player.save()

    first_turn = game.get_dynamics().current_turn

    event = SeedEvent(seed=2204)
    event.timestamp = first_turn.begin
    game.get_dynamics().inject_event(event)

    roles = [ Contadino, Lupo, Negromante, Fattucchiera ]
    for i in xrange(len(game.get_dynamics().players)):
        event = AvailableRoleEvent(role_name=roles[i%len(roles)].__name__)
        event.timestamp = first_turn.begin
        game.get_dynamics().inject_event(event)

def play_dummy_game():
    # We begin with creation, just after setup_game() finished
    game = Game.get_running_game()
    assert game.current_turn.phase == CREATION
    assert len(game.get_dynamics().players) == 4

    game.advance_turn()
    game.advance_turn()
    game.advance_turn()

    # Now it is day; let us vote for death!

def create_game(seed, roles, initial_info):
    game = Game(running=True)
    game.save()
    game.initialize(get_now())

    users = User.objects.filter(is_staff=False).all()
    assert len(roles) == len(users)
    for user in users:
        assert not user.is_staff
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

    for text in initial_info:
        game.get_dynamics().inject_event(InitialPropositionEvent(text=text, timestamp=get_now()))

    return game
