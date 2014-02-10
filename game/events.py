from django.db import models
from models import Event, Role, Player


class CommandEvent(Event):
    # A command submitted by a player
    
    USEPOWER = 'P'
    VOTE = 'V'
    ELECT = 'E'
    
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        (USEPOWER, 'UsePower'),
        (VOTE, 'Vote'),
        (ELECT, 'Elect'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='action_target_set')
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='action_target2_set')
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

