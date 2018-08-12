from datetime import datetime, time, timedelta
from threading import RLock
import sys

from django.db import models, IntegrityError
from django import forms
from django.utils.text import capfirst
from django.contrib.auth.models import User
from django.db.models.signals import pre_delete
from django.conf import settings

from .constants import *

from .utils import advance_to_time, get_now


class KnowsChild(models.Model):
    # Make a place to store the class name of the child
    # (copied almost entirely from http://blog.headspin.com/?p=474)
    subclass = models.CharField(max_length=200)
 
    class Meta:
        abstract = True
 
    def as_child(self):
        return getattr(self, self.subclass.lower())

    def fill_subclass(self):
        self.subclass = self.__class__.__name__

    def save(self, *args, **kwargs):
        self.fill_subclass()
        super(KnowsChild, self).save(*args, **kwargs)


def dump_game(game, fout):
    assert game is not None
    import json
    data = {'players': [],
            'turns': []}
    for player in Player.objects.filter(game=game).order_by('pk'):
        data['players'].append({'username': player.user.username,
                                'first_name': player.user.first_name,
                                'last_name': player.user.last_name,
                                'email': player.user.email,
                                'password': player.user.password,
                                'gender': player.user.profile.gender,
                                })

    for turn in Turn.objects.filter(game=game).order_by('date', 'phase'):
        turn_data = {'events': [], 'comments': []}
        for event in Event.objects.filter(turn=turn).order_by('timestamp', 'pk'):
            event = event.as_child()
            if not event.AUTOMATIC:
                turn_data['events'].append(event.to_dict())
        for comment in Comment.objects.filter(turn=turn).order_by('timestamp'):
            turn_data['comments'].append(comment.to_dict())
        data['turns'].append(turn_data)

    json.dump(data, fout, indent=4)


_dynamics_map = {}
_dynamics_map_lock = RLock()

def kill_all_dynamics():
    with _dynamics_map_lock:
        _dynamics_map.clear()

class Game(models.Model):
    public = models.BooleanField(default=False)
    postgame_info = models.BooleanField(default=False)
    def __unicode__(self):
        return u"Game %d" % self.pk
    name = models.CharField(max_length=32, verbose_name='Nome della partita')
    description = models.CharField(max_length=64, verbose_name='Descrizione')

    day_end_weekdays = models.PositiveSmallIntegerField(default=79, verbose_name='Sere in cui finisce il giorno')

    def get_day_end_weekdays(self):
        return [ i for i in range(7) if (self.day_end_weekdays >> i) & 1]

    night_end_time = models.TimeField(default=time(8), null=True, verbose_name='Ora dell\'alba')
    day_end_time = models.TimeField(default=time(22), null=True, verbose_name='Ora del tramonto')

    half_phase_duration = models.IntegerField(default=60, verbose_name='Durata delle fasi di alba e tramonto (in secondi)')

    def get_phase_end_time(self, phase):
        if phase == DAY:
            return self.day_end_time
        elif phase == NIGHT:
            return self.night_end_time
        else:
            return None

    def started(self):
        return self.get_dynamics().random is not None
    started = property(started)

    def current_turn(self):
        try:
            return Turn.objects.filter(game=self).order_by('-date', '-phase')[0]
        except IndexError:
            return None
    current_turn = property(current_turn)

    def get_masters(self):
        return GameMaster.objects.filter(game=self)
    masters = property(get_masters)

    def get_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().players
    players = property(get_players)
    def mayor(self):
        return self.get_dynamics().mayor
    mayor = property(mayor)

    def is_over(self):
        return self.get_dynamics().over
    is_over = property(is_over)

    def get_dynamics(self):
        """Obtain or create the Dynamics object globally assigned to
        this game."""
        global _dynamics_map
        global _dynamics_map_lock
        if self.pk not in _dynamics_map:
            with _dynamics_map_lock:
                # The previous "if" is not relevant, because it was
                # tested before acquiring the lock; it is useful
                # nevertheless, because it heavily limits the numer of
                # times the lock has to be acquired
                if self.pk not in _dynamics_map:
                    from .dynamics import Dynamics
                    _dynamics_map[self.pk] = Dynamics(self)
        dynamics = _dynamics_map[self.pk]
        dynamics.update()
        if not dynamics.failed:
            return dynamics
        else:
            return None

    def kill_dynamics(self):
        """Kill the Dynamics object globally assigned to
        this game."""
        global _dynamics_map
        global _dynamics_map_lock
        if self.pk in _dynamics_map:
            with _dynamics_map_lock:
                if self.pk in _dynamics_map:
                    from .dynamics import Dynamics
                    del _dynamics_map[self.pk]

    def recompute_automatic_events(self):
        """This is not really race-free, so use with care..."""
        global _dynamics_map
        global _dynamics_map_lock
        with _dynamics_map_lock:
            if self.pk in _dynamics_map:
                from .dynamics import Dynamics
                del _dynamics_map[self.pk]
            for event in Event.objects.filter(turn__game=self):
                if event.as_child().AUTOMATIC:
                    event.delete()


    def get_active_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().get_active_players()
    active_players = property(get_active_players)

    def get_inactive_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().get_inactive_players()
    inactive_players = property(get_inactive_players)

    def get_alive_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().get_alive_players()
    alive_players = property(get_alive_players)

    def get_dead_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().get_dead_players()
    dead_players = property(get_dead_players)

    def initialize(self, begin):
        first_turn = Turn.first_turn(self)
        first_turn.set_first_begin_end(begin)
        first_turn.save()
        assert first_turn.phase == CREATION

    def advance_turn(self, current_turn=None):
        """Advance to next turn. If current_turn is passed, the turn
        that will be created is the one following the turn passed. If
        the next turn is already in the database, it will not be created
        twice."""
        if current_turn is None:
            current_turn = self.current_turn
        assert current_turn.end is not None
        next_turn = current_turn.next_turn()
        next_turn.set_begin_end(current_turn)
        try:
            next_turn.save()
        except IntegrityError:
            # Next turn has already been created by another thread.
            # Let's check it is indeed there.
            next_turn = current_turn.next_turn(must_exist=True)

        dynamics = self.get_dynamics()
        assert dynamics is not None
        dynamics.update()

    def check_turn_advance(self):
        """Compare current timestamp against current turn's end time
        and, if necessary, create the new turn."""
        while self.current_turn.end is not None and get_now() >= self.current_turn.end:
            self.advance_turn()

# Delete the dynamics object when the game is deleted
def game_pre_delete_callback(sender, instance, **kwargs):
    with _dynamics_map_lock:
        if instance.pk in _dynamics_map:
            del _dynamics_map[instance.pk]
pre_delete.connect(game_pre_delete_callback, sender=Game)

class Turn(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)

    # Date is counted starting from FIRST_DATE
    date = models.IntegerField()
    
    TURN_PHASES = {
        DAY: 'Day',
        SUNSET: 'Sunset',
        NIGHT: 'Night',
        DAWN: 'Dawn',
        CREATION: 'Creation',
        }
    phase = models.CharField(max_length=1, choices=TURN_PHASES.items())

    # begin must always be set (and coincide with the previous turn's
    # end if it exists); end can be None only when it is the last turn
    # of an ongoing game

    begin = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['date', 'phase']
        unique_together = (('game', 'date', 'phase'),)
    
    def __unicode__(self):
        return "%s %d" % (Turn.TURN_PHASES[self.phase], self.date)
    as_string = property(__unicode__)
    
    def __hash__(self):
        # Custom hash function, working for non-saved objects
        return hash((self.game, self.date,self.phase))

    def phase_as_italian_string(self):
        return {
            DAY: 'Giorno',
            SUNSET: 'Tramonto',
            NIGHT: 'Notte',
            DAWN: 'Alba',
            CREATION: 'Creazione',
            }[self.phase]
    phase_as_italian_string_property = property(phase_as_italian_string)
    
    def turn_as_italian_string(self):
        if self.phase == CREATION:
            return u'Prologo'
        elif self.phase == DAY:
            return u'Giorno %s' % self.date
        elif self.phase == NIGHT:
            return u'Notte %s' % self.date
        elif self.phase == SUNSET:
            return u'Tramonto del giorno %s' % self.date
        elif self.phase == DAWN:
            return u'Alba del giorno %s' % self.date
    turn_as_italian_string_property = property(turn_as_italian_string)
    
    
    @staticmethod
    def get_or_create(game, date, phase, must_exist=False):
        try:
            turn = Turn.objects.get(game=game, date=date, phase=phase)
        except Turn.DoesNotExist:
            if must_exist:
                raise
            turn = Turn(game=game, date=date, phase=phase)
            #turn.save()

        return turn

    def next_turn(self, must_exist=False):
        """Return next turn. If it does not exist, then it is NOT created in
        the database.

        """
        phase = PHASE_CYCLE[self.phase]
        date = self.date
        if phase == DATE_CHANGE_PHASE:
            date += 1
        return Turn.get_or_create(self.game, date, phase, must_exist=must_exist)

    def prev_turn(self, must_exist=False):
        phase = REV_PHASE_CYCLE[self.phase]
        date = self.date
        if self.phase == DATE_CHANGE_PHASE:
            date -= 1
        return Turn.get_or_create(self.game, date, phase, must_exist=must_exist)

    def full_days_from_start(self):
        # Returns the number of full phase cycles from beginning
        phase = FIRST_PHASE
        date = FIRST_DATE
        i = 0
        while phase != self.phase:
            phase = PHASE_CYCLE[phase]
            if phase == DATE_CHANGE_PHASE:
                date += 1
            i += 1
            assert (i < 5)

        return self.date - date

    @staticmethod
    def first_turn(game, must_exist=False):
        return Turn.get_or_create(game, FIRST_DATE, FIRST_PHASE, must_exist=must_exist)

    def set_end(self, allow_retroactive_end=True):
        if self.game.is_over:
            # If the game has already ended, the turn will be endless
            self.end = None
        elif self.phase in FULL_PHASES:
            allowed_weekdays = self.game.get_day_end_weekdays() if self.phase == DAY else None
            self.end = advance_to_time(self.begin, self.game.get_phase_end_time(self.phase), allowed_weekdays=allowed_weekdays)
        elif self.phase in HALF_PHASES:
            self.end = self.begin + timedelta(seconds=self.game.half_phase_duration)
        else:
            self.end = None

        # If allow_retroactive_end is False, the turn cannot end in the past: in that case,
        # we force the turn to end now.
        if not allow_retroactive_end and self.end is not None and self.end <= get_now():
            self.end = get_now()

    def set_first_begin_end(self, begin):
        #self.begin = datetime.combine(begin_date, FIRST_PHASE_BEGIN_TIME)
        self.begin = begin
        self.set_end()

    def set_begin_end(self, prev_turn):
        self.begin = prev_turn.end
        self.set_end()


class Profile(models.Model):
    # Additional information about Users
    
    GENDERS = (
        (MALE, 'Male'),
        (FEMALE, 'Female'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=1, choices=GENDERS)
    
    # Returns 'o' or 'a' depending on the gender
    def get_oa(self):
        if self.gender == FEMALE:
            return 'a'
        else:
            return 'o'
    oa = property(get_oa)


class Player(models.Model):
    AURA_COLORS = (
        (WHITE, 'White'),
        (BLACK, 'Black'),
    )
    AURA_COLORS_DICT = dict(AURA_COLORS)
    
    TEAMS = (
        (POPOLANI, 'Popolani'),
        (LUPI, 'Lupi'),
        (NEGROMANTI, 'Negromanti'),
    )
    TEAMS_DICT = dict(TEAMS)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        unique_together = ['user','game']
    
    def get_full_name(self):
        return "%s %s" % (self.user.first_name, self.user.last_name)
    full_name = property(get_full_name)
    
    def get_gender(self):
        try:
            return self.user.profile.gender
        except Profile.DoesNotExist:
            return MALE
    gender = property(get_gender)
    
    def __str__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)
    
    # Returns 'o' or 'a' depending on the player's gender
    def get_oa(self):
        try:
            return self.user.profile.oa
        except Profile.DoesNotExist:
            return 'o'
    oa = property(get_oa)
    
    
    def canonicalize(self):
        # We save on queries when we can
        if 'canonical' in self.__dict__ and self.canonical:
            return self
        else:
            return self.game.get_dynamics().get_canonical_player(self)

    
    def get_role_name(self):
        canonical = self.canonicalize()
        if canonical.role is not None:
            return canonical.role.__class__.__name__
        else:
            return "Unassigned"
    role_name = property(get_role_name)
    
    def aura_as_italian_string(self):
        canonical = self.canonicalize()
        return AURA_IT[ canonical.aura ]
    aura_as_italian_string_property = property(aura_as_italian_string)
    
    def status_as_italian_string(self):
        canonical = self.canonicalize()
        if canonical.active:
            if canonical.alive:
                return u'Viv%s' % self.oa
            else:
                return u'Mort%s' % self.oa
        else:
            return u'Esiliat%s' % self.oa
    status_as_italian_string_property = property(status_as_italian_string)
    
    def team_as_italian_string(self):
        canonical = self.canonicalize()
        return TEAM_IT[ canonical.team ]
    team_as_italian_string_property = property(team_as_italian_string)
    
    
    def can_use_power(self):
        if self.game.is_over:
            # The game has ended
            return False
        if self.game.current_turn is None:
            # The current turn has not been set -- this shouldn't happen if Game is running
            return False

        canonical = self.canonicalize()

        if canonical.role is None:
            # The role has not been set -- this shouldn't happen if Game is running
            return False
        
        if not canonical.active:
            # The player has been exiled
            return False
        
        turn = self.game.current_turn
        if turn.phase != NIGHT:
            # Players can use their powers only during the night
            return False
        
        return canonical.role.can_use_power()
    can_use_power.boolean = True

    def team(self):
        return Player.TEAMS_DICT[self.canonicalize().team]

    def aura(self):
        return Player.AURA_COLORS_DICT[self.canonicalize().aura]

    def is_mystic(self):
        return self.canonicalize().is_mystic
    is_mystic.boolean = True

    def alive(self):
        return self.canonicalize().alive
    alive.boolean = True

    def active(self):
        return self.canonicalize().active
    active.boolean = True
    
    
    def can_vote(self):
        if self.game.is_over:
            # The game is over
            return False
        if self.game.current_turn is None:
            # The current turn has not been set -- this shouldn't happen if Game is running
            return False

        canonical = self.canonicalize()
        
        if not canonical.active:
            # The player has been exiled
            return False
        if not canonical.alive:
            # The player is dead
            return False
        
        turn = self.game.current_turn
        if turn.phase != DAY:
            # Players can vote only during the day
            return False
        
        # Everything seems to be OK
        return True
    can_vote.boolean = True
    
    def is_mayor(self):
        # True if this player is the Mayor
        mayor = self.game.get_dynamics().mayor
        if mayor is None:
            return False
        return self.pk == mayor.pk
    is_mayor.boolean = True

    def is_appointed_mayor(self):
        appointed_mayor = self.game.get_dynamics().appointed_mayor
        if appointed_mayor is None:
            return False
        return self.pk == appointed_mayor.pk
    is_appointed_mayor.boolean = True

class GameMaster(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        unique_together = ['user','game']

    def get_full_name(self):
        return "%s %s" % (self.user.first_name, self.user.last_name)
    full_name = property(get_full_name)

    def get_gender(self):
        try:
            return self.user.profile.gender
        except Profile.DoesNotExist:
            return MALE
    gender = property(get_gender)
    # Returns 'o' or 'a' depending on the master's gender
    def get_oa(self):
        try:
            return self.user.profile.oa
        except Profile.DoesNotExist:
            return 'o'
    oa = property(get_oa)

class Event(KnowsChild):
    """Event base class."""
    CAN_BE_SIMULATED = False

    timestamp = models.DateTimeField()
    turn = models.ForeignKey(Turn,on_delete=models.CASCADE)

    class Meta:
        ordering = ['turn', 'timestamp', 'pk']

    def __unicode__(self):
        if self.pk is not None:
            return u"Event %d" % self.pk
        else:
            return u"Event without pk"
    event_name = property(__unicode__)

    def is_automatic(self):
        return self.as_child().AUTOMATIC
    is_automatic.boolean = True

    def apply(self, dynamics):
        raise NotImplementedError("Calling Events.apply() instead of a subclass")

    def load_from_dict(self, data, players_map):
        raise NotImplementedError("Calling Events.load_from_dict() instead of a subclass")

    def to_dict(self):
        return {'subclass': self.subclass, 'timestamp': self.timestamp.isoformat()}

    @staticmethod
    def from_dict(data, players_map):
        [subclass] = [x for x in Event.__subclasses__() if x.__name__ == data['subclass']]
        event = subclass()
        # The following line shouldn't be required
        #event.subclass = data['subclass']
        event.load_from_dict(data, players_map)
        return event

    def to_player_string(self, player):
        # Default is no message
        return None



class Announcement(models.Model):
    
    game = models.ForeignKey(Game, null=True, blank=True, default=None, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=datetime.now)
    text = models.TextField()
    visible = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __unicode__(self):
        return u"Announcement %d" % self.pk
    announcement_name = property(__unicode__)


class Comment(models.Model):
    
    timestamp = models.DateTimeField(default=datetime.now)
    turn = models.ForeignKey(Turn, null=True, blank=True,on_delete=models.CASCADE)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    text = models.TextField()
    visible = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __unicode__(self):
        return u"Comment %d" % self.pk
    comment_name = property(__unicode__)

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'user': self.user.username,
            'text': self.text,
            'visible': self.visible,
        }


class PageRequest(models.Model):
    
    user = models.ForeignKey(User,models.CASCADE)
    timestamp = models.DateTimeField()
    path = models.TextField()
    ip_address = models.TextField()
    hostname = models.TextField()
    
    class Meta:
        ordering = ['timestamp']
    
    def __unicode__(self):
        return u"PageRequest %d" % self.pk
    pagerequest_name = property(__unicode__)


