from datetime import datetime
from threading import RLock

from django.db import models
from django import forms
from django.utils.text import capfirst
from django.contrib.auth.models import User

from constants import *

from utils import advance_to_time

import my_random as random


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


_dynamics_map = {}
_dynamics_map_lock = RLock()

class Game(models.Model):
    running = models.BooleanField(default=False)
    
    def __unicode__(self):
        return u"Game %d" % self.pk
    game_name = property(__unicode__)

    def current_turn(self):
        try:
            return Turn.objects.filter(game=self).order_by('-date', '-phase')[0]
        except Turn.DoesNotExist:
            return None
    current_turn = property(current_turn)
    
    def get_players(self):
        return Player.objects.filter(game=self)
    
    @staticmethod
    def get_running_game():
        return Game.objects.get(running=True)

    def mayor(self):
        return self.get_dynamics().mayor

    def get_dynamics(self):
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
        return [player for player in self.get_dynamics().players if player.active]
    
    def get_inactive_players(self):
        return [player for player in self.get_dynamics().players if not player.active]
    
    def get_alive_players(self):
        return [player for player in self.get_dynamics().players if player.alive]
    
    def get_dead_players(self):
        return [player for player in self.get_dynamics().players if not player.alive]

    def initialize(self, begin_date):
        first_turn = Turn.first_turn(self)
        first_turn.set_first_begin_end(begin_date)
        first_turn.save()

    def compute_turn_advance(self):
        assert self.current_turn.end is not None
        next_turn = self.current_turn.next_turn()
        next_turn.set_begin_end(self.current_turn)
        self.current_turn = next_turn
        self.current_turn.save()
        self.save()

        # Call the appropriate phase handler
        {
            DAY: self._compute_entering_day,
            NIGHT: self._compute_entering_night,
            SUNSET: self._compute_entering_sunset,
            DAWN: self._compute_entering_dawn,
            }[self.current_turn.phase]()

    def _compute_entering_night(self):
        pass

    def _compute_entering_dawn(self):
        pass

    def _compute_entering_day(self):
        pass

    def _compute_entering_sunset(self):
        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            #TODO
            pass

        winner = self._compute_vote_winner()
        if winner is not None:
            # TODO
            pass

    def _compute_elected_mayor(self):
        prev_turn = self.current_turn.prev_turn(must_exist=True)
        votes = CommandEvents.objects.filter(turn=prev_turn).filter(type=ELECT).order_by(Event.timestamp)
        new_mayor = None

        # TODO

        return new_mayor

    def _compute_vote_winner(self):
        prev_turn = self.current_turn.prev_turn(must_exist=True)
        votes = CommandEvents.objects.filter(turn=prev_turn).filter(type=VOTE).order_by(Event.timestamp)
        winner = None

        # Count last ballot for each player
        ballots = {}
        mayor_ballot = None
        for player in self.get_players():
            ballots[player.pk] = None
        for vote in votes:
            ballots[vote.player.pk] = vote
            if vote.player.is_mayor():
                mayor_ballot = vote

        # TODO: count Ipnotista and Spettro dell'Amnesia

        # TODO: check that at least half of the alive people voted; if
        # not, abort the voting

        # TODO: count Spettro della Duplicazione

        # Fill tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        for ballot in ballots.itervalues():
            tally_sheet[ballot.target.pk] += 1

        # Compute winners (or maybe loosers...)
        tally_sheet = tally_sheet.items()
        tally_sheet.sort(key=lambda x: x[1])
        max_votes = tally_sheet[0][1]
        winners = [x[0] for x in tally_sheet if x[1] == max_votes]
        assert len(winners) > 0
        if mayor_ballot.target.pk in winners:
            winner = mayor_ballot.target.pk
        else:
            winner = random.choice(winners)

        # TODO: kill the winner

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
        if phase == FIRST_PHASE:
            date += 1
        return Turn.get_or_create(self.game, date, phase, must_exist=must_exist)

    def prev_turn(self, must_exist=False):
        phase = REV_PHASE_CYCLE[self.phase]
        date = self.date
        if self.phase == FIRST_PHASE:
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

    def set_first_begin_end(self, begin_date):
        self.begin = datetime.combine(begin_date, FIRST_PHASE_BEGIN_TIME)
        self.set_end()

    def set_begin_end(self, prev_turn):
        self.begin = prev_turn.end
        self.set_end()


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
    
    def get_role_name(self):
        canonical = self.canonicalize()
        if canonical.role is not None:
            return canonical.role.name
        else:
            return "Unassigned"
    role_name = property(get_role_name)
    
    def __unicode__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)
    
    def canonicalize(self):
        return self.game.get_dynamics().get_canonical_player(self)

    # TODO: questa funzione forse non deve stare qui, e sicuramente nel caso va resa un po' piu' decente
    def aura_as_italian_string(self):
        if self.aura==WHITE:
            return "Bianca"
        else:
            return "Nera"
    
    def status_as_italian_string(self):
        if self.active:
            if self.alive:
                return "Vivo"
            else:
                return "Morto"
        else:
            return "Esiliato"
    
    
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
    
    def make_mayor(self):
        self.game.mayor = self
        self.game.save()


class Event(KnowsChild):
    # Generic event
    
    timestamp = models.DateTimeField()
    turn = models.ForeignKey(Turn)
    executed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['turn', 'timestamp', 'pk']
    
    def __unicode__(self):
        return u"Event %d" % self.pk
    event_name = property(__unicode__)

    def apply(self, dynamics):
        raise NotImplementedError("Calling Events.apply() instead of a subclass")
