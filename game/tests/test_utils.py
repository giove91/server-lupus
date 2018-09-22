from functools import wraps
from game.models import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time

def delete_auto_users():
    for user in User.objects.all():
        if user.username.startswith('pk'):
            user.delete()

def create_users(n):
    users = []
    for i in range(n):
        user = User.objects.create(username='pk%d' % (i), first_name='Paperinik', last_name='%d' % (i), email='paperinik.%d@sns.it' % (i), password='ciaociao')
        profile = Profile.objects.create(user=user, gender=MALE)
        profile.save()
        user.set_password('ciaociao')
        user.save()
        users.append(user)
    return users

def create_game(seed, ruleset, roles):
    game = Game()
    game.save()

    users = create_users(len(roles))
    for user in users:
        if user.is_staff:
            raise Exception()
        player = Player.objects.create(user=user, game=game)
        player.save()

    game.initialize(get_now())

    first_turn = game.get_dynamics().current_turn

    assert first_turn.phase == FIRST_PHASE, Turn.objects.filter(game=game)
    event = SeedEvent(seed=seed)
    event.timestamp = first_turn.begin
    game.get_dynamics().inject_event(event)

    event = SetRulesEvent(ruleset=ruleset)
    event.timestamp = first_turn.begin
    game.get_dynamics().inject_event(event)

    for i in range(len(game.get_dynamics().players)):
        event = AvailableRoleEvent(role_class=roles[i%len(roles)])
        event.timestamp = first_turn.begin
        game.get_dynamics().inject_event(event)

    return game

def create_game_from_dump(data, start_moment=None):
    if start_moment is None:
        start_moment = get_now()

    game = Game()
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
    game.get_dynamics().update()

def record_name(f):
    @wraps(f)
    def g(self):
        self._name = f.__name__
        return f(self)

    return g
