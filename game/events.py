# -*- coding: utf-8 -*-

from django.db import models
from models import Event, Player
from roles import *
from constants import *

class CommandEvent(Event):
    # A command submitted by a player

    RELEVANT_PHASES = [DAY, NIGHT]
    AUTOMATIC = False
    
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        (USEPOWER, 'UsePower'),
        (VOTE, 'Vote'),
        (ELECT, 'Elect'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)

    REAL_RELEVANT_PHASES = {
        USEPOWER: NIGHT,
        VOTE: DAY,
        ELECT: DAY,
        }
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='+')
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='+')
    target_ghost = models.CharField(max_length=1, choices=Spettro.POWERS_LIST, null=True, blank=True)
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

    def apply(self, dynamics):
        # Do nothing; events will be counted during sunset or dawn;
        # just check that we're in the correct phase
        assert dynamics.current_turn.phase in CommandEvent.REAL_RELEVANT_PHASES[self.type]


class SeedEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    seed = models.IntegerField()

    def apply(self, dynamics):
        # We use Wichmann-Hill because it is a pure Python
        # implementation; its reduced randomness properties shouldn't
        # be a problem for us
        from my_random import WichmannHill
        dynamics.random = WichmannHill()
        dynamics.random.seed(self.seed)


class AvailableRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    role_name = models.CharField(max_length=200)

    def apply(self, dynamics):
        assert len(dynamics.available_roles) < len(dynamics.players), "%d %d" % (len(dynamics.available_roles), len(dynamics.players))
        dynamics.available_roles.append(self.role_name)

        # If this is the last role, assign randomly the roles to the
        # players and then choose a random mayor
        if len(dynamics.available_roles) == len(dynamics.players):
            players_pks = dynamics.players_dict.keys()
            players_pks.sort()
            mayor = dynamics.random.choice(players_pks)
            dynamics.random.shuffle(players_pks)

            for player_pk, role_name in zip(players_pks, dynamics.available_roles):
                event = SetRoleEvent()
                event.player = dynamics.players_dict[player_pk]
                event.role_name = role_name
                dynamics.generate_event(event)

            event = SetMayorEvent()
            event.player = dynamics.players_dict[mayor]
            dynamics.generate_event(event)


class SetRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200)

    def apply(self, dynamics):
        [role_class] = [x for x in Role.__subclasses__() if x.__name__ == self.role_name]
        player = self.player.canonicalize()
        role = role_class(player)
        player = self.player.canonicalize()
        player.role = role
        player.team = role.team
        player.aura = role.aura
        player.is_mystic = role.is_mystic


class SetMayorEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert player.alive
        dynamics.mayor = player


class VoteAnnouncedEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    voter = models.ForeignKey(Player, related_name='+')
    voted = models.ForeignKey(Player, related_name='+')
    # Allow ELECT and VOTE here
    type = models.CharField(max_length=1, choices=CommandEvent.ACTION_TYPES)

    def apply(self, dynamics):
        assert self.type in [ELECT, VOTE]
        assert self.voter.canonicalize().alive
        assert self.voted.canonicalize().alive


class TallyAnnouncedEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    voted = models.ForeignKey(Player, related_name='+')
    vote_num = models.IntegerField()
    # Allow ELECT and VOTE here
    type = models.CharField(max_length=1, choices=CommandEvent.ACTION_TYPES)

    def apply(self, dynamics):
        assert self.type in [ELECT, VOTE]
        assert self.voted.canonicalize().alive
        assert self.vote_num > 0


class ElectNewMayorEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert player.alive
        dynamics.mayor = player
        assert player.is_mayor()
    
    def to_player_string(self, player):
        if player == self.player:
            return u'Sei stato eletto sindaco del villaggio.'
        else:
            return u'È stato eletto un nuovo sindaco, %s.' % self.player.full_name
        


class PlayerDiesEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    DEATH_CAUSE_TYPES = (
        (STAKE, 'Stake'),
        (HUNTER, 'Hunter'),
        (WOLVES, 'Wolves'),
        (DEATH_GHOST, 'DeathGhost'),
        )
    cause = models.CharField(max_length=1, choices=DEATH_CAUSE_TYPES)

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert player.alive
        player.alive = False

        # TODO: trigger the actions that depend on a player's death,
        # like mayor inheritance, trigger Cacciatore power, trigger
        # Fantasma power
    
    def to_player_string(self, player):
        if player == self.player:
            if self.cause == STAKE:
                return u'Sei stato bruciato sul rogo.'
            else:
                return u'Sei morto durante la notte.'
        else:
            if self.cause == STAKE:
                return u'%s è stato bruciato sul rogo.' % self.player.full_name
            else:
                return u'%s è stato ritrovato morto.' % self.player.full_name




