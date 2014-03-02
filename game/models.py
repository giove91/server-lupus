from datetime import datetime
from threading import RLock

from django.db import models
from django import forms
from django.utils.text import capfirst
from django.contrib.auth.models import User
from django.db.models.signals import pre_delete

from constants import *

from utils import advance_to_time


class KnowsChild(models.Model):
    # Make a place to store the class name of the child
    # (copied almost entirely from http://blog.headspin.com/?p=474)
    subclass = models.CharField(max_length=200)
 
    class Meta:
        abstract = True
 
    def as_child(self):
        return getattr(self, self.subclass.lower())
 
    def save(self, *args, **kwargs):
        # save what kind we are.
        self.subclass = self.__class__.__name__
        super(KnowsChild, self).save(*args, **kwargs)


def dump_game(game, fout):
    import json
    data = {'players': [],
            'turns': []}
    for player in Player.objects.filter(game=game):
        data['players'].append({'username': player.user.username})

    for turn in Turn.objects.filter(game=game).order_by('date', 'phase'):
        turn_data = {'events': []}
        for event in Event.objects.filter(turn=turn).order_by('timestamp', 'pk'):
            event = event.as_child()
            if not event.AUTOMATIC:
                turn_data['events'].append(event.to_dict())
        data['turns'].append(turn_data)

    json.dump(data, fout, indent=4)


_dynamics_map = {}
_dynamics_map_lock = RLock()

def kill_all_dynamics():
    with _dynamics_map_lock:
        _dynamics_map.clear()

class Game(models.Model):
    running = models.BooleanField(default=False)

    def __unicode__(self):
        return u"Game %d" % self.pk
    game_name = property(__unicode__)

    def current_turn(self):
        try:
            return Turn.objects.filter(game=self).order_by('-date', '-phase')[0]
        except IndexError:
            return None
    current_turn = property(current_turn)

    def get_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return self.get_dynamics().players

    @staticmethod
    def get_running_game():
        try:
            return Game.objects.get(running=True)
        except Game.DoesNotExist:
            return None

    def mayor(self):
        return self.get_dynamics().mayor
    mayor = property(mayor)

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
                    from dynamics import Dynamics
                    _dynamics_map[self.pk] = Dynamics(self)
        _dynamics_map[self.pk].update()
        return _dynamics_map[self.pk]

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

    def advance_turn(self):
        assert self.current_turn.end is not None
        next_turn = self.current_turn.next_turn()
        next_turn.set_begin_end(self.current_turn)
        next_turn.save()
        self.get_dynamics().update()

    def check_turn_advance(self):
        """Compare current timestamp against current turn's end time
        and, if necessary, create the new turn."""
        while self.current_turn.end is not None and datetime.now() >= self.current_turn.end:
            self.advance_turn()

# Delete the dynamics object when the game is deleted
def game_pre_delete_callback(sender, instance, **kwargs):
    with _dynamics_map_lock:
        del _dynamics_map[instance.pk]
pre_delete.connect(game_pre_delete_callback, sender=Game)

class Turn(models.Model):
    game = models.ForeignKey(Game)

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

    @staticmethod
    def first_turn(game, must_exist=False):
        return Turn.get_or_create(game, FIRST_DATE, FIRST_PHASE, must_exist=must_exist)

    def set_end(self):
        if self.phase in FULL_PHASES:
            self.end = advance_to_time(self.begin, FULL_PHASE_END_TIMES[self.phase])
        else:
            self.end = None

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
    
    user = models.OneToOneField(User)
    gender = models.CharField(max_length=1, choices=GENDERS)


class Player(models.Model):
    AURA_COLORS = (
        (WHITE, 'White'),
        (BLACK, 'Black'),
    )
    
    TEAMS = (
        (POPOLANI, 'Popolani'),
        (LUPI, 'Lupi'),
        (NEGROMANTI, 'Negromanti'),
    )
    
    user = models.OneToOneField(User, primary_key=True)
    game = models.ForeignKey(Game)
    
    class Meta:
        ordering = ['user']
    
    def get_full_name(self):
        return "%s %s" % (self.user.first_name, self.user.last_name)
    full_name = property(get_full_name)
    
    def get_gender(self):
        try:
            return self.user.profile.gender
        except Profile.DoesNotExist:
            return MALE
    gender = property(get_gender)
    
    def __unicode__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)
    
    # Returns 'o' or 'a' depending on the player's gender
    def get_oa(self):
        if self.gender == MALE:
            return 'o'
        else:
            return 'a'
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
            return canonical.role.name
        else:
            return "Unassigned"
    role_name = property(get_role_name)
    
    # TODO: Gio, e' giusto che si chiami self.canonicalize() in ognuna di queste funzioni?
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
        if not self.game.running:
            # The game is not running
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
        return self.canonicalize().team

    def aura(self):
        return self.canonicalize().aura

    def alive(self):
        return self.canonicalize().alive
    alive.boolean = True

    def active(self):
        return self.canonicalize().active
    active.boolean = True
    
    
    def can_vote(self):
        if not self.game.running:
            # The game is not running
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


class Event(KnowsChild):
    """Event base class."""

    timestamp = models.DateTimeField()
    turn = models.ForeignKey(Turn)

    class Meta:
        ordering = ['turn', 'timestamp', 'pk']

    def __unicode__(self):
        return u"Event %d" % self.pk
    event_name = property(__unicode__)

    def is_automatic(self):
        return self.as_child().AUTOMATIC
    is_automatic.boolean = True

    def apply(self, dynamics):
        raise NotImplementedError("Calling Events.apply() instead of a subclass")

    def load_from_dict(self, data, players_map):
        raise NotImplementedError("Calling Events.load_from_dict() instead of a subclass")

    def to_dict(self):
        return {'subclass': self.subclass}

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
    
    game = models.ForeignKey(Game, null=True, blank=True, default=None)
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
    turn = models.ForeignKey(Turn, null=True, blank=True)
    user = models.ForeignKey(User)
    text = models.TextField()
    visible = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __unicode__(self):
        return u"Comment %d" % self.pk
    comment_name = property(__unicode__)



