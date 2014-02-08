from datetime import datetime

from django.db import models
from django import forms
from django.utils.text import capfirst
from django.contrib.auth.models import User


class Game(models.Model):
    running = models.BooleanField(default=False)
    current_turn = models.ForeignKey('Turn', null=True, blank=True, related_name='+')
    
    def __unicode__(self):
        return u"Game %d" % self.pk
    game_name = property(__unicode__)
    
    def get_players(self):
        return Player.objects.filter(game=self)
    
    def get_active_players(self):
        return self.get_players().filter(active=True)
    
    def get_alive_players(self):
        return self.get_active_players().filter(alive=True)
    
    def get_dead_players(self):
        return self.get_active_players().filter(alive=False)


class Turn(models.Model):
    game = models.ForeignKey(Game)
    day = models.IntegerField()
    
    TURN_PHASES = (
        ('D', 'Day'),
        ('S', 'Sunset'),
        ('N', 'Night'),
        ('W', 'Dawn' ),
    )
    phase = models.CharField(max_length=1, choices=TURN_PHASES)
    begin = models.DateTimeField(default=datetime.now)
    end = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['day', 'phase']
    
    def is_day(self):
        return self.phase=='D'
    
    def is_night(self):
        return self.phase=='N'
    
    def is_sunset(self):
        return self.phase=='S'
    
    def is_dawn(self):
        return self.phase=='W'
    
    def __unicode__(self):
        if self.is_day():
            return u"Day %d" % self.day
        elif self.is_night():
            return u"Night %d" % self.day
        elif self.is_sunset():
            return u"Sunset %d" % self.day
        elif self.is_dawn():
            return u"Dawn %d" %self.day
        
    as_string = property(__unicode__)
    
    def phase_as_italian_string(self):
        if self.is_day():
            return 'Giorno'
        elif self.is_night():
            return 'Notte'
        elif self.is_sunset():
            return 'Tramonto'
        elif self.is_dawn():
            return 'Alba'
    
    def next_turn(self):
        phase='D'
        day=self.day
        
        if self.is_day():
            phase='S'
        elif self.is_sunset():
            phase='N'
        elif self.is_night():
            phase='W'
        elif self.is_dawn():
            phase='D'
            day+=1
        next_turn = Turn(game=self.game, day=day, phase=phase)
        return next_turn


class Role(models.Model):
    role_name = 'Generic role'
    team = 'P'
    aura = 'W'
    is_mystic = False
    
    message = 'Usa il tuo potere su:'
    message2 = 'Parametro secondario:'
    message_ghost = 'Potere soprannaturale:'
    
    last_usage = models.ForeignKey(Turn, null=True, blank=True, default=None)
    last_target = models.ForeignKey('Player', null=True, blank=True, default=None, related_name='target_inv_set')
    
    def __unicode__(self):
        return u"%s" % self.role_name
    
    def get_team_name(self):
        teams = { 'P': 'Popolani', 'L': 'Lupi', 'N': 'Negromanti' }
        return teams[self.team]
    
    def get_aura(self):
        auras = { 'W': 'White', 'B': 'Black' }
        return auras[self.aura]
    
    def can_use_power(self):
        return False
    
    def get_targets(self):
        # Returns the list of possible targets
        return None


class Player(models.Model):
    AURA_COLORS = (
        ('W', 'White'),
        ('B', 'Black'),
    )
    
    TEAMS = (
        ('P', 'Popolani'),
        ('L', 'Lupi'),
        ('N', 'Negromanti'),
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
    
    def _get_full_name(self):
        return "%s %s" % (self.user.first_name, self.user.last_name)
    full_name = property(_get_full_name)
    
    def __unicode__(self):
        return u"%s %s" % (self.user.first_name, self.user.last_name)
    
    def aura_as_italian_string(self):
        if self.aura=='W':
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
        if not turn.is_night():
            # Players can use their powers only during the night
            return False
        
        return self.role.can_use_power()
    
    can_use_power.boolean = True
    
    
    def can_use_power_on(self, target):
        if not self.can_use_power():
            # The player cannot use her power
            return False
        
        if not target.active:
            # Target has been exiled
            return False
        
        return self.role.can_use_power_on(target)
    
    
    def get_targets(self):
        # Returns the list of Players that can be used as targets
        res = Player.objects.filter(game=self.game).filter(active=True)
        if not self.role.reflexive:
            res = res.exclude(pk=self.pk)
        if not self.role.on_living:
            res = res.exclude(alive=True)
        if not self.role.on_dead:
            res = res.exclude(alive=False)
        if not self.role.reusable_on_same_target and self.last_usage is not None and self.last_usage.day==self.game.current_turn.day-1 and self.last_target is not None:
            res = res.exclude(pk=self.last_target.pk)
        return res
    
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
        if not turn.is_day():
            # Players can vote only during the day
            return False
        
        # Everything seems to be OK
        return True
    
    can_vote.boolean = True
    


class Event(models.Model):
    # Generic event
    
    timestamp = models.DateTimeField(default=datetime.now)
    turn = models.ForeignKey(Turn)
    
    class Meta:
        ordering = ['turn', 'timestamp', 'pk']
    
    def __unicode__(self):
        return u"Event %d" % self.pk
    
    event_name = property(__unicode__)


class CommandEvent(Event):
    # A command submitted by a player
    
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        ('P', 'UsePower'),
        ('V', 'Vote'),
        ('E', 'Elect'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='action_target_set')
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='action_target2_set')
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk


'''
class Action(models.Model):
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        ('P', 'UsePower'),
        ('V', 'Vote'),
        ('E', 'Elect'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='action_target_set')
    param = models.ForeignKey(Player, null=True, blank=True, related_name='action_param_set')
    day = models.IntegerField()
    time = models.DateTimeField(auto_now_add=True, blank=True)
    
    class Meta:
        ordering = ['time', 'pk']
    
    def __unicode__(self):
        return u"Action %d" % self.pk
    
    action_name = property(__unicode__)
'''

