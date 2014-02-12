from datetime import datetime

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


class Game(models.Model):
    running = models.BooleanField(default=False)
    current_turn = models.ForeignKey('Turn', null=True, blank=True, related_name='_game')
    mayor = models.ForeignKey('Player', null=True, blank=True, related_name='_game')
    
    def __unicode__(self):
        return u"Game %d" % self.pk
    game_name = property(__unicode__)
    
    def get_players(self):
        return Player.objects.filter(game=self)
    
    def get_active_players(self):
        return self.get_players().filter(active=True)
    
    def get_exiled_players(self):
        return self.get_players().filter(active=False)
    
    def get_alive_players(self):
        return self.get_active_players().filter(alive=True)
    
    def get_dead_players(self):
        return self.get_active_players().filter(alive=False)

    def initialize(self, begin_date):
        self.current_turn = Turn.first_turn(game)
        self.current_turn.set_first_begin_end()

    def compute_turn_advance(self):
        assert self.current_turn.end is not None
        next_turn = self.current_turn.next_turn()
        next_turn.set_begin_end(self.current_turn)
        self.current_turn = next_turn

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
        }
    phase = models.CharField(max_length=1, choices=TURN_PHASES.items())
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
            }[self.phase]
    
    @staticmethod
    def get_or_create(game, date, phase, must_exist=False):
        try:
            turn = Turn.objects.get(game=game, date=date, phase=phase)
        except Turn.DoesNotExist:
            if must_exist:
                raise
            turn = Turn(game=game, date=date, phase=phase)
            turn.save()

        return turn

    def next_turn(self):
        phase = PHASE_CYCLE[self.phase]
        date = self.date
        if phase == FIRST_PHASE:
            date += 1
        return Turn.get_or_create(game, date, phase)

    def prev_turn(self, must_exist=False):
        phase = REV_PHASE_CYCLE[self.phase]
        date = self.date
        if self.phase == FIRST_PHASE:
            date -= 1
        return Turn.get_or_create(game, date, phase, must_exist=must_exist)

    @staticmethod
    def first_turn(game):
        return Turn.get_or_create(game, FIRST_DATE, FIRST_PHASE)

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


class Role(KnowsChild):
    name = 'Generic role'
    team = None
    aura = None
    is_mystic = False
    
    message = 'Usa il tuo potere su:'
    message2 = 'Parametro secondario:'
    message_ghost = 'Potere soprannaturale:'
    
    last_usage = models.ForeignKey(Turn, null=True, blank=True, default=None)
    last_target = models.ForeignKey('Player', null=True, blank=True, default=None, related_name='target_inv_set')
    
    def __unicode__(self):
        return u"%s" % self.name
    
    def can_use_power(self):
        return False
    
    def get_targets(self):
        # Returns the list of possible targets
        return None
    
    def get_targets2(self):
        # Returns the list of possible second targets
        return None
    
    def get_targets_ghost(self):
        # Returns the list of possible ghost-power targets
        return None
    
    def days_from_last_usage(self):
        if last_usage is None:
            return None
        else:
            return self.player.game.current_turn.day - self.last_usage.day


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
    team = models.CharField(max_length=1, choices=TEAMS, null=True, blank=True, default=None)
    
    role = models.OneToOneField(Role, null=True, blank=True, default=None)
    aura = models.CharField(max_length=1, choices=AURA_COLORS, null=True, blank=True, default=None)
    is_mystic = models.BooleanField(default=False)
    
    alive = models.BooleanField(default=True)
    active = models.BooleanField(default=True)  # False if exiled (i.e. the team lost)
    
    
    class Meta:
        ordering = ['user']
    
    def get_full_name(self):
        return "%s %s" % (self.user.first_name, self.user.last_name)
    full_name = property(get_full_name)
    
    def get_role_name(self):
        return self.role.as_child().name
    role_name = property(get_role_name)
    
    def __unicode__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)
    
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
        if self.role is None:
            # The role has not been set -- this shouldn't happen if Game is running
            return False
        
        if not self.active:
            # The player has been exiled
            return False
        
        turn = self.game.current_turn
        if turn.phase != NIGHT:
            # Players can use their powers only during the night
            return False
        
        return self.role.as_child().can_use_power()
    
    can_use_power.boolean = True
    
    
    def can_vote(self):
        if not self.game.running:
            # The game is not running
            return False
        if self.game.current_turn is None:
            # The current turn has not been set -- this shouldn't happen if Game is running
            return False
        
        if not self.active:
            # The player has been exiled
            return False
        if not self.alive:
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
        if self.game.mayor is None:
            return False
        return self.pk == self.game.mayor.pk
    
    is_mayor.boolean = True
    
    def make_mayor(self):
        self.game.mayor = self
        self.game.save()


class Event(KnowsChild):
    # Generic event
    
    timestamp = models.DateTimeField(default=datetime.now)
    turn = models.ForeignKey(Turn)
    
    class Meta:
        ordering = ['turn', 'timestamp', 'pk']
    
    def __unicode__(self):
        return u"Event %d" % self.pk
    event_name = property(__unicode__)
