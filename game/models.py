from datetime import datetime

from django.db import models
from django import forms
from django.utils.text import capfirst
from django.db.models.fields import Field, IntegerField
from django.contrib.auth.models import User



class LupusTimeField(IntegerField):
    description = "Day and phase of a Lupus game"
    
    __metaclass__ = models.SubfieldBase
    
    def get_prep_value(self, value):
        if value is None:
            return None
        return 2*(value.day - 1) + value.phase
    
    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, LupusTime):
            return value
        intval = int(value)
        day = intval/2 + 1
        phase = intval%2
        
        return LupusTime(day, phase)
    
    # TODO: sarebbe da cambiare in modo da mostrare il valore giusto; al momento lei mostra LupusTime::__unicode__()
    '''
    def formfield(self, **kwargs):
        defaults = {'form_class': forms.IntegerField}
        defaults.update(kwargs)
        return super(IntegerField, self).formfield(**defaults)
    '''
    def formfield(self, **kwargs):
        defaults = {'required': not self.blank,
                    'label': capfirst(self.verbose_name),
                    'help_text': self.help_text}
        if self.has_default():
            if callable(self.default):
                print "PRIMO CASO"
                defaults['initial'] = self.default
                defaults['show_hidden_initial'] = True
            else:
                print "SECONDO CASO"
                defaults['initial'] = self.get_default()
                print self.get_default()
        defaults.update(kwargs)
        print defaults
        print defaults['widget']
        return forms.IntegerField(**defaults)


class LupusTime(object):
    def __init__(self, day, phase):
        # day is an integer
        # phase is a 0/1 integer (0 = day, 1 = night)
        self.day = day
        self.phase = phase
    
    def __unicode__(self):
        # Ora e' fatta cosi' perche' LupusTimeField::formfield() non funziona come dovrebbe...
        a = LupusTimeField()
        return a.get_prep_value(self)
    
    def as_string(self):
        if self.phase==0:
            return "Day %d" % self.day
        else:
            return "Night %d" % self.day
    
    def is_day(self):
        return self.phase==0
    
    def is_night(self):
        return self.phase==1
    
    def advance(self):
        if self.is_day():
            self.phase=1
        else:
            self.day+=1
            self.phase=0



class Game(models.Model):
    running = models.BooleanField(default=False)
    current_turn = models.ForeignKey('Turn', null=True, blank=True, related_name='+')
    
    def __unicode__(self):
        return u"Game %d" % self.pk
    game_name = property(__unicode__)



class Turn(models.Model):
    game = models.ForeignKey(Game)
    day = models.IntegerField()
    
    TURN_PHASES = (
        ('D', 'Day'),
        ('N', 'Night'),
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
    
    def __unicode__(self):
        if self.is_day():
            return u"Day %d" % self.day
        else:
            return u"Night %d" % self.day
    as_string = property(__unicode__)
    
    def phase_as_italian_string(self):
        if self.is_day():
            return 'Giorno'
        else:
            return 'Notte'
    
    def next_turn(self):
        phase='D'
        day=0
        if self.is_day():
            self.phase='N'
        else:
            self.day+=1
            self.phase='D'
        next_turn = Turn(game=self.game, day=day, phase=phase)
        return next_turn



class Team(models.Model):
    team_name = models.CharField(max_length=64, unique=True)
    
    def __unicode__(self):
        return u"%s" % self.team_name
    
    class Meta:
        ordering = ['pk']



class CommonInfo(models.Model):
    AURA_COLORS = (
        ('W', 'White'),
        ('B', 'Black'),
    )
    
    class Meta:
        abstract = True


class Role(CommonInfo):
    role_name = models.CharField(max_length=64, unique=True)
    team = models.ForeignKey(Team)
    aura = models.CharField(max_length=1, choices=CommonInfo.AURA_COLORS, default='W')
    is_mystic = models.BooleanField(default=False)
    
    has_power = models.BooleanField(default=True)
    frequency = models.IntegerField(default=1)      # 0 = infty (i.e. the power can be used only once)
    reflexive = models.BooleanField(default=False)  # The player can use his power on herself
    on_living = models.BooleanField(default=True)   # The power can be used on the living
    on_dead = models.BooleanField(default=True)     # The power can be used on the dead
    reusable_on_same_target = models.BooleanField(default=True) # The power can be used in consecutive nights on the same target
    is_ghost = models.BooleanField(default=False)
    
    def __unicode__(self):
        return u"%s" % self.role_name
    
    class Meta:
        ordering = ['team', 'role_name']


class Player(CommonInfo):
    user = models.OneToOneField(User, primary_key=True)
    game = models.ForeignKey(Game)
    team = models.ForeignKey(Team, null=True, blank=True, default=None)
    
    role = models.ForeignKey(Role, null=True, blank=True, default=None)
    aura = models.CharField(max_length=1, choices=CommonInfo.AURA_COLORS, null=True, blank=True, default=None)
    is_mystic = models.BooleanField(default=False)
    
    alive = models.BooleanField(default=True)
    active = models.BooleanField(default=True)  # False if exiled (i.e. the team lost)
    
    last_usage = models.ForeignKey(Turn, null=True, blank=True, default=None) # Last power usage (None = never used)
    last_target = models.ForeignKey('self', null=True, blank=True, default=None)   # Last target -- should be set to NULL if role changes
    
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
        if not self.role.has_power:
            # The player doesn't have a power
            return False
        
        turn = self.game.current_turn
        if turn.is_day():
            # Players can use their powers only during the night
            return False
            
        # Checking if the power can be used, considering the dead/alive property of the user
        if self.role.is_ghost:
            if self.alive:
                return False
        else:
            if not self.alive:
                return False
        
        if self.last_usage is None:
            # The power has never been used
            return True
        if self.role.frequency==0:
            # The power could be used only once
            return False
        return turn.day - self.last_usage.day >= self.role.frequency
    
    can_use_power.boolean = True
    
    
    def can_use_power_on(self, target):
        if not self.can_use_power():
            # The player cannot use her power
            return False
        
        if not target.active:
            # Target has been exiled
            return False
        if target.pk==self.pk and not self.role.reflexive:
            # Target is herself but the power is not reflexive
            return False
        if target.alive and not self.role.on_living:
            # Target is alive but the power cannot be used on the living
            return False
        if not target.alive and not self.role.on_dead:
            # Target is dead but the power cannot be used on the dead
            return False
        
        if not self.role.reusable_on_same_target and self.last_target is not None and self.last_target.pk==target.pk and self.last_usage is not None and self.last_usage.day==self.game.current_turn.day-1:
            # The power cannot be used on the same target in consecutive nights
            return False
        return True
    
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
        if turn.is_night():
            # Players cannot vote during the night
            return False
        
        # Everything seems to be OK
        return True
    
    can_vote.boolean = True
    

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


