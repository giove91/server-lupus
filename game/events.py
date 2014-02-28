# -*- coding: utf-8 -*-

from django.db import models
from models import Event, Player
from roles import *
from constants import *
from utils import dir_dict, rev_dict

class CommandEvent(Event):
    # A command submitted by a player

    RELEVANT_PHASES = [DAY, NIGHT]
    AUTOMATIC = False
    
    player = models.ForeignKey(Player, related_name='action_set')
    
    ACTION_TYPES = (
        (USEPOWER, 'UsePower'),
        (VOTE, 'Vote'),
        (ELECT, 'Elect'),
        (APPOINT, 'Appoint'),
    )
    type = models.CharField(max_length=1, choices=ACTION_TYPES)

    REAL_RELEVANT_PHASES = {
        USEPOWER: [NIGHT],
        VOTE: [DAY],
        ELECT: [DAY],
        APPOINT: [DAY, NIGHT],
        }
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='+')
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='+')
    target_ghost = models.CharField(max_length=1, choices=Spettro.POWERS_LIST, null=True, blank=True)
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'player': self.player.user.username,
                'target': self.target.user.username if self.target is not None else None,
                'target2': self.target2.user.username if self.target2 is not None else None,
                'target_ghost': dir_dict(Spettro.POWERS_LIST)[self.target_ghost],
                'type': dict(CommandEvent.ACTION_TYPES)[self.type],
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.player = players_map[data['player']]
        self.target = players_map[data['target']]
        self.target2 = players_map[data['target2']]
        self.target_ghost = rev_dict(Spettro.POWERS_LIST)[data['target_ghost']]
        self.type = rev_dict(CommandEvent.ACTION_TYPES)[data['type']]

    def apply(self, dynamics):
        # Do nothing; events will be counted during sunset or dawn;
        # just check that we're in the correct phase; the only
        # exception is the appointment, which takes effect immediately
        assert dynamics.current_turn.phase in CommandEvent.REAL_RELEVANT_PHASES[self.type]

        if self.type == APPOINT:
            assert self.player.is_mayor()
            assert self.target is not None
            assert self.target2 is None
            assert self.player.pk != self.target.pk
            canonical = self.target.canonicalize()
            assert canonical.alive
            dynamics.appointed_mayor = canonical


class SeedEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    seed = models.IntegerField()

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'seed': self.seed,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.seed = data['seed']

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

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'role_name': self.role_name,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.role_name = data['role_name']

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
    
    def to_player_string(self, player):
        if player == self.player:
            return u'Ti è stato assegnato il ruolo di: %s.' % self.role_name
        elif player == 'admin':
            return u'A %s è stato assegnato il ruolo di: %s.' % (self.player.full_name, self.role_name)
        else:
            return None


class SetMayorEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert player.alive
        assert dynamics.mayor is None
        assert dynamics.appointed_mayor is None
        dynamics.mayor = player
        dynamics.appointed_mayor = None

    def to_player_string(self, player):
        oa = self.player.oa
        if player == self.player:
            return u'Sei stat%s nominat%s Sindaco del villaggio.' % (oa, oa)
        else:
            return u'%s è stat%s nominat%s Sindaco del villaggio.' % (self.player.full_name, oa, oa)


class InitialPropositionEvent(Event):
    # An initial proposition published by the GM
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False
    
    text = models.TextField()
    
    def apply(self,dynamics):
        # TODO: Gio, qua bisogna mettere qualcosa?
        pass
    
    def to_player_string(self,player):
        # This event is processed separately
        return None


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
    
    def to_player_string(self,player):
        # This event is processed separately
        return None


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
    
    def to_player_string(self,player):
        # This event is processed separately
        return None


class ElectNewMayorEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert player.alive
        if dynamics.mayor.pk != player.pk:
            dynamics.mayor = player
            dynamics.appointed_mayor = None
        assert player.is_mayor()
    
    def to_player_string(self, player):
        oa = self.player.oa
        if player == self.player:
            return u'Sei stat%s elett%s Sindaco del villaggio.' % (oa, oa)
        else:
            return u'%s è stat%s elett%s nuovo Sindaco del villaggio.' % (self.player.full_name, oa, oa)
        


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

        if player.is_mayor():
            if dynamics.appointed_mayor is not None:
                assert dynamics.appointed_mayor.alive
                dynamics.mayor = dynamics.appointed_mayor
                dynamics.appointed_mayor = None

            else:
                candidates = [x for x in dynamics.get_alive_players() if x.pk != player.pk]
                dynamics.mayor = dynamics.random.choice(candidates)

        if player.is_appointed_mayor():
            dynamics.appointed_mayor = None

        # TODO: other actions to trigger: Cacciatore power, Fantasma
        # power, release of Ipnotista lock

        player.alive = False

    def to_player_string(self, player):
        oa = self.player.oa
        if player == self.player:
            if self.cause == STAKE:
                return u'Sei stat%s bruciat%s sul rogo.' % (oa, oa)
            else:
                return u'Sei mort%s durante la notte.' % oa
        else:
            if self.cause == STAKE:
                return u'%s è stat%s bruciat%s sul rogo.' % (self.player.full_name, oa, oa)
            else:
                return u'%s è stat%s ritrovat%s mort%s.' % (self.player.full_name, oa, oa, oa)


class SoothsayerRevelationEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'player': self.player.user.username,
                'target': self.target.user.username,
                'role_name': self.role_name,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.player = players_map[data['player']]
        self.target = players_map[data['target']]
        self.role_name = data['role_name']

    def apply(self, dynamics):
        assert isinstance(self.player.canonicalize().role, Divinatore)
