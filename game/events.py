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
    type = models.CharField(max_length=1, choices=ACTION_TYPES, default=None)

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
        assert dynamics.current_turn.phase in CommandEvent.REAL_RELEVANT_PHASES[self.type]
        assert self.player is not None

        # Canonicalize players
        self.player = self.player.canonicalize()
        if self.target is not None:
            self.target = self.target.canonicalize()
        if self.target2 is not None:
            self.target2 = self.target2.canonicalize()

        if self.type == APPOINT:
            assert self.player.is_mayor()
            assert self.target2 is None
            assert self.target_ghost is None
            if self.target is not None:
                assert self.player.pk != self.target.pk
                assert self.target.alive
                dynamics.appointed_mayor = self.target
            else:
                dynamics.appointed_mayor = None

        elif self.type == VOTE or self.type == ELECT:
            assert self.player.alive
            if self.target is not None:
                assert self.target.alive
            assert self.target2 is None
            assert self.target_ghost is None
            if self.type == VOTE:
                self.player.recorded_vote = self.target
            elif self.type == ELECT:
                self.player.recorded_elect = self.target
            else:
                assert False, "Should not arrive here"

        elif self.type == USEPOWER:
            self.player.canonicalize().role.apply_usepower(dynamics, self)

        else:
            assert False, "Invalid type"


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

            given_roles = {}
            for player_pk, role_name in zip(players_pks, dynamics.available_roles):
                event = SetRoleEvent(player=dynamics.players_dict[player_pk], role_name=role_name)
                dynamics.generate_event(event)
                given_roles[player_pk] = role_name

            event = SetMayorEvent()
            event.player = dynamics.players_dict[mayor]
            dynamics.generate_event(event)

            # Then compute all the knowledge classes and generate the
            # relevant events
            knowledge_classes = {}
            knowledge_classes_rev = {}
            for player in dynamics.players:
                role_class = Role.get_from_name(given_roles[player.pk])
                knowledge_class = role_class.knowledge_class
                if knowledge_class is not None:
                    if not knowledge_class in knowledge_classes:
                        knowledge_classes[knowledge_class] = []
                    knowledge_classes[knowledge_class].append(player)
                    knowledge_classes_rev[player.pk] = knowledge_class
            for player in dynamics.players:
                if not player.pk in knowledge_classes_rev:
                    continue
                knowledge_class = knowledge_classes[knowledge_classes_rev[player.pk]]
                for target in knowledge_class:
                    if target.pk != player.pk:
                        event = RoleKnowledgeEvent(player=player, target=target, role_name=given_roles[target.pk], cause=KNOWLEDGE_CLASS)
                        dynamics.generate_event(event)


class SetRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200)

    def apply(self, dynamics):
        role_class = Role.get_from_name(self.role_name)
        player = self.player.canonicalize()
        role = role_class(player)
        player.role = role
        player.team = role.team
        player.aura = role.aura
        player.is_mystic = role.is_mystic
        assert player.role is not None
        assert player.team is not None
        assert player.aura is not None
        assert player.is_mystic is not None
    
    def to_player_string(self, player):
        if player == self.player:
            return u'Ti è stato assegnato il ruolo di %s.' % self.role_name
        elif player == 'admin':
            return u'A %s è stato assegnato il ruolo di %s.' % (self.player.full_name, self.role_name)
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

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'text': self.text,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.text = data['text']

    def apply(self,dynamics):
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
    RELEVANT_PHASES = [SUNSET, DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    DEATH_CAUSE_TYPES = (
        (STAKE, 'Stake'),
        (HUNTER, 'Hunter'),
        (WOLVES, 'Wolves'),
        (DEATH_GHOST, 'DeathGhost'),
        )
    cause = models.CharField(max_length=1, choices=DEATH_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        STAKE: SUNSET,
        HUNTER: DAWN,
        WOLVES: DAWN,
        DEATH_GHOST: DAWN,
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in PlayerDiesEvent.REAL_RELEVANT_PHASES[self.cause]

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


class RoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN]
    # FIXME: probably SOOTHSAYER is not really automatic
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200, default=None)
    KNOWLEDGE_CAUSE_TYPES = (
        (SOOTHSAYER, 'Soothsayer'),
        (EXPANSIVE, 'Expansive'),
        (KNOWLEDGE_CLASS, 'KnowledgeClass'),
        (GHOST, 'Ghost'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        SOOTHSAYER: [CREATION],
        KNOWLEDGE_CLASS: [CREATION],
        EXPANSIVE: [DAWN],
        # FIXME: what happens when Fantasma dies and becomes a ghost?
        # It can happen also during sunset
        GHOST: [DAWN],
        }

    # def to_dict(self):
    #     ret = Event.to_dict(self)
    #     ret.update({
    #             'player': self.player.user.username,
    #             'target': self.target.user.username,
    #             'role_name': self.role_name,
    #             'cause': self.cause,
    #             })
    #     return ret

    # def load_from_dict(self, data, players_map):
    #     self.player = players_map[data['player']]
    #     self.target = players_map[data['target']]
    #     self.role_name = data['role_name']
    #     self.cause = data['cause']

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in RoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]

        if self.cause == SOOTHSAYER:
            assert isinstance(self.player.canonicalize().role, Divinatore)

        elif self.cause == EXPANSIVE:
            assert isinstance(self.target.canonicalize().role, Espansivo)

        elif self.cause == GHOST:
            assert isinstance(self.target.canonicalize().role, Negromante)

        elif self.cause == KNOWLEDGE_CLASS:
            assert self.player.canonicalize().role.knowledge_class is not None
            assert self.target.canonicalize().role.knowledge_class is not None
            assert self.player.canonicalize().role.knowledge_class == self.target.canonicalize().role.knowledge_class

        if self.cause != SOOTHSAYER:
            role_class = roles_map[self.role_name]
            assert isinstance(self.target.canonicalize().role, role_class)
    
    
    def to_player_string(self, player):
        role = Role.get_from_name(self.role_name).name
        
        if self.cause == SOOTHSAYER:
            if player == 'admin':
                return u'Il Divinatore %s riceve la frase: "%s"' % (self.player.full_name, self.to_soothsayer_proposition())
        
        elif self.cause == EXPANSIVE:
            if player == self.player:
                return u'%s ti rivela di essere l\'Espansivo.' % self.target.full_name
            elif player == 'admin':
                return u'%s rivela a %s di essere l\'Espansivo.' % (self.target.full_name, self.player.full_name)
        
        elif self.cause == KNOWLEDGE_CLASS:
            if player == self.player:
                return u'A %s è stato assegnato il ruolo di %s.' % (self.target.full_name, role)
            elif player == 'admin':
                return u'Per conoscenza iniziale, %s sa che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role)
        
        elif self.cause == GHOST:
            if player == self.player:
                return u'Vieni a sapere che %s è un %s.' % (self.target.full_name, role)
            elif player == 'admin':
                return u'Per spettrificazione, %s viene a sapere che %s è un %s.' % (self.player.full_name, self.target.full_name, role)
        
        else:
            raise Exception ('Unknown cause for RoleKnowledgeEvent.')
        
        return None
    
    def to_soothsayer_proposition(self):
        assert self.cause == SOOTHSAYER
        role = Role.get_from_name(self.role_name).name
        return u'%s ha il ruolo di %s.' % (self.target.full_name, role)


class AuraKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    aura = models.CharField(max_length=1, default=None, choices=Player.AURA_COLORS)
    KNOWLEDGE_CAUSE_TYPES = (
        (SEER, 'Seer'),
        (DETECTIVE, 'Detective'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass
    
    def to_player_string(self, player):
        aura = AURA_IT[ self.aura ]
        
        if player == self.player:
            return u'Hai utilizzato il tuo potere su %s, scoprendo che ha aura %s.' % (self.target.full_name, aura)
        elif player == 'admin':
            return u'%s ha utilizzato il proprio potere su %s, scoprendo che ha aura %s.', (self.player.full_name, self.target.full_name, aura)
        return None
            


class MysticityKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    is_mystic = models.BooleanField(default=None)
    # There is only one choice, but I like to have this for
    # homogeneity
    KNOWLEDGE_CAUSE_TYPES = (
        (MAGE, 'Mage'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass
    
    def to_player_string(self, player):
        if self.is_mystic:
            result = ''
        else:
            result = 'non '
        
        if player == self.player:
            return u'Hai utilizzato il tuo potere su %s, scoprendo che %sè un mistico.' % (self.target.full_name, result)
        elif player == 'admin':
            return u'%s ha utilizzato il proprio potere su %s, scoprendo che %sè un mistico.', (self.player.full_name, self.target.full_name, result)


class TeamKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    team = models.CharField(max_length=1, default=None, choices=Player.TEAMS)
    # There is only one choice, but I like to have this for
    # homogeneity
    KNOWLEDGE_CAUSE_TYPES = (
        (VISION_GHOST, 'VisionGhost'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass


class MovementKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    # Target and target2 are to be understood as how they are in
    # CommandEvent; that is, target is the player that was watched and
    # target2 is where he went (for the Stalker) or who went by him
    # (for the Voyeur)
    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    target2 = models.ForeignKey(Player, related_name='+')
    KNOWLEDGE_CAUSE_TYPES = (
        (STALKER, 'Stalker'),
        (VOYEUR, 'Voyeur'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass


class MediumKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    aura = models.CharField(max_length=1, default=None, choices=Player.AURA_COLORS)
    is_ghost = models.BooleanField(default=None)
    # There is only one choice, but I like to have this for
    # homogeneity
    KNOWLEDGE_CAUSE_TYPES = (
        (MEDIUM, 'Medium'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass


class PowerOutcomeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    command = models.OneToOneField(CommandEvent)
    success = models.BooleanField()
    sequestrated = models.BooleanField()

    def apply(self, dynamics):
        assert self.command.type == USEPOWER
        assert self.command.player.pk == self.player.pk
        assert self.command.target is not None
    
    def to_player_string(self, player):
        target = self.command.target
        target2 = self.command.target2
        target_ghost = self.command.target_ghost
        oa = self.player.oa
        
        if self.success:
            if player == self.player:
                return u'Hai utilizzato con successo il tuo potere su %s.' % target.full_name
            
            elif player == 'admin':
                return u'%s ha utilizzato con successo il proprio potere su %s.' % (self.player.full_name, target.full_name)
        
        else:
            if player == self.player:
                return u'Ti risvegli confus%s e stordit%s: l\'unica cosa di cui sei cert%s è di non essere riuscit%s ad utilizzare il tuo potere su %s, questa notte.' % (oa, oa, oa, oa, target.full_name)
            
            elif player == 'admin':
                string = u'%s non è riuscit%s ad utilizzare il proprio potere su %s, questa notte ' % (self.player.full_name, oa, target.full_name)
                if self.sequestrated:
                    string += '(sequestrat%s)' % oa
                else:
                    string += '(non sequestrat%s)' %oa



