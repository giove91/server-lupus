from functools import wraps
from game.models import *
from game.events import *
from game.constants import *
from game.utils import get_now, advance_to_time
import re

from inspect import isclass

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
    game = Game(name='test')
    game.save()

    users = create_users(len(roles))
    for user in users:
        if user.is_staff:
            raise Exception()
        player = Player.objects.create(user=user, game=game)
        player.save()


    game.initialize(get_now())

    user = User.objects.create(username='pk_master', first_name='Paperinik', last_name='Master', email='pikappa@sns.it', password='ciaociao')
    user.save()
    master = GameMaster(user=user, game=game)
    master.save()

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

class GameTest():
    seed = 1

    def setUp(self):
        kill_all_dynamics()
        ruleset = re.findall(r"game\.tests\.test_(.*)", self.__module__)[0]
        self.game = create_game(self.seed, ruleset, self.roles)
        self.dynamics = self.game.get_dynamics()
        if self.spectral_sequence is not None:
            self.dynamics.inject_event(SpectralSequenceEvent(sequence=self.spectral_sequence, timestamp=get_now()))

        self.master = GameMaster.objects.get(game=self.game)
        self.players = self.game.get_players()
        need_soothsayer = False
        for player in self.players:
            name = (player.role.__class__.__name__ + ('_' + player.role.disambiguation_label if player.role.disambiguation_label else '')).lower()
            setattr(self, name, player)
            need_soothsayer = need_soothsayer or player.role.needs_soothsayer_propositions()

        if not need_soothsayer:
            self.advance_turn()
        else:
            self.dynamics.debug_event_bin = []

    def tearDown(self):
        # Save a dump of the test game
        # if 'game' in self.__dict__:
            #with open(os.path.join('test_dumps', '%s.json' % (self._name)), 'w') as fout:
                #pass #dump_game(self.game, fout)

        # Destroy the leftover dynamics without showing the slightest
        # sign of mercy
        kill_all_dynamics()

    def advance_turn(self, phase=None):
        self.dynamics.debug_event_bin = []
        stop = False
        self.assertTrue(phase in {None, DAWN, SUNSET, NIGHT, DAY})
        while not stop:
            turn = self.game.current_turn
            turn.end = get_now()
            turn.save()
            self.dynamics.update()
            stop = phase is None or self.game.current_turn.phase == phase

    def usepower(self, player, target, **kwargs):
        self.dynamics.inject_event(CommandEvent(player=player, type=USEPOWER, target=target, **kwargs))

    def vote(self, player, target):
        self.dynamics.inject_event(CommandEvent(type=VOTE, player=player, target=target, timestamp=get_now()))

    def mass_vote(self, votes, expected):
        if self.dynamics.current_turn.phase != DAY:
            self.advance_turn(DAY)
        for voter, voted in enumerate(votes):
            self.vote(self.players[voter], self.players[voted])
        self.advance_turn()
        if expected is None:
            self.check_event(StakeFailedEvent, {'cause': MISSING_QUORUM})
        else:
            self.check_event(PlayerDiesEvent, {'cause': STAKE, 'player': self.players[expected]})

    def soothsayer_proposition(self, soothsayer, target, advertised_role):
        self.dynamics.inject_event(SoothsayerModelEvent(soothsayer=soothsayer, target=target, advertised_role=advertised_role, timestamp=get_now()))

    def get_events(self, event_class, **kwargs):
        events = [event for event in self.dynamics.debug_event_bin if isinstance(event, event_class)]
        for k,v in kwargs.items():
            events = [event for event in events if getattr(event, k) == v]

        return events

    def check_phase(self, phase):
        self.assertEqual(self.game.current_turn.phase, phase)

    def check_event(self, event, checks={}, **kwargs):
        if isclass(event):
            if checks is None:
                self.assertEqual(len(self.get_events(event, **kwargs)), 0, '\n%s was generated when it was not meant to.' % event.__name__)
                return
            else:
                events = self.get_events(event, **kwargs)
                self.assertEqual(len(events), 1, 'Expected exactly one %s, but %s were generated.' % (event.__name__, len(events)))
                [event] = events

        for k, v in checks.items():
            self.assertEqual(getattr(event, k), v, "\n%s's attribute %s is not what would be expected." % (event.__class__.__name__, k))

    def burn(self, victim):
        for player in self.game.get_alive_players():
            self.vote(player, victim)

    def autovote(self):
        for player in self.game.get_alive_players():
            self.vote(player, player)

    def restart(self):
        for player in self.players:
            player.user.delete()
        self.master.user.delete()
        self.game.delete()
        self.setUp()
