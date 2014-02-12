from django.db import models
from models import Event, Role, Player
from roles import *
from constants import *


class CommandEvent(Event):
    # A command submitted by a player
    
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        (USEPOWER, 'UsePower'),
        (VOTE, 'Vote'),
        (ELECT, 'Elect'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='commandevent_target_set')
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='commandevent_target2_set')
    target_ghost = models.CharField(max_length=1, choices=Spettro.POWERS_LIST, null=True, blank=True)
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

