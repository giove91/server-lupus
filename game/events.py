# -*- coding: utf-8 -*-

from django.db import models
from .models import Event, Player
from .roles import *
from .constants import *
from .utils import dir_dict, rev_dict
from importlib import import_module

class CommandEvent(Event):
    # A command submitted by a player

    RELEVANT_PHASES = [DAY, NIGHT]
    AUTOMATIC = False
    
    player = models.ForeignKey(Player, related_name='action_set',on_delete=models.CASCADE)
    
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
    
    target = models.ForeignKey(Player, null=True, blank=True, related_name='+',on_delete=models.CASCADE)
    target2 = models.ForeignKey(Player, null=True, blank=True, related_name='+',on_delete=models.CASCADE)
    target_ghost = models.CharField(max_length=1, choices=POWER_NAMES.items(), null=True, blank=True)
    
    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

    def player_role(self):
        if self.player is not None:
            return self.player.canonicalize().role.full_name
        else:
            return None

    def target_role(self):
        if self.target is not None:
            return self.target.canonicalize().role.full_name
        else:
            return None

    def target2_role(self):
        if self.target2 is not None:
            return self.target2.canonicalize().role.full_name
        else:
            return None

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'player': self.player.user.username,
                'target': self.target.user.username if self.target is not None else None,
                'target2': self.target2.user.username if self.target2 is not None else None,
                'target_ghost': POWER_NAMES[self.target_ghost] if self.target_ghost is not None else None,
                'type': dict(CommandEvent.ACTION_TYPES)[self.type],
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.player = players_map[data['player']]
        self.target = players_map[data['target']]
        self.target2 = players_map[data['target2']]
        self.target_ghost = data['target_ghost']
        self.type = rev_dict(CommandEvent.ACTION_TYPES)[data['type']]

    def check_phase(self, dynamics=None, turn=None):
        if turn is None:
            turn = dynamics.current_turn
        return turn.phase in CommandEvent.REAL_RELEVANT_PHASES[self.type]

    def apply(self, dynamics):
        assert self.check_phase(dynamics=dynamics)

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

    # This is a CharField so that we can store very big integers; it
    # is expected to contain an integer anyway
    seed = models.CharField(max_length=200)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'seed': int(self.seed),
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.seed = data['seed']

    def apply(self, dynamics):
        # We use Wichmann-Hill because it is a pure Python
        # implementation; its reduced randomness properties shouldn't
        # be a problem for us
        from .my_random import WichmannHill
 
        dynamics.random = WichmannHill()
        dynamics.random.seed(int(self.seed))

class SetRulesEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    ruleset = models.CharField(max_length=200)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'ruleset': self.ruleset,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.ruleset = data['ruleset']

    def apply(self, dynamics):
        roles = import_module('game.roles.' + self.ruleset)
        dynamics.roles_list = roles.roles_list
        dynamics.required_roles = roles.required_roles.copy()
        dynamics.starting_roles = roles.starting_roles
        dynamics.starting_teams = roles.starting_teams

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
            players_pks = sorted(dynamics.players_dict.keys())
            mayor = dynamics.random.choice(players_pks)
            dynamics.random.shuffle(players_pks)

            given_roles = {}
            for player_pk, role_name in zip(players_pks, dynamics.available_roles):
                full_role_name = dynamics.roles_list[role_name].full_name
                event = SetRoleEvent(player=dynamics.players_dict[player_pk], role_name=role_name, full_role_name=full_role_name)
                dynamics.generate_event(event)
                given_roles[player_pk] = role_name

            event = SetMayorEvent()
            event.player = dynamics.players_dict[mayor]
            event.cause = BEGINNING
            dynamics.generate_event(event)

            # Then compute all the knowledge classes and generate the
            # relevant events
            knowledge_classes = {}
            knowledge_classes_rev = {}
            for player in dynamics.players:
                role_class = dynamics.roles_list[given_roles[player.pk]]
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
                        event = RoleKnowledgeEvent(player=player, target=target, full_role_name=dynamics.roles_list[given_roles[target.pk]].full_name, cause=KNOWLEDGE_CLASS)
                        dynamics.generate_event(event)


class SetRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    role_name = models.CharField(max_length=200)
    full_role_name = models.CharField(max_length=200)

    def apply(self, dynamics):
        role_class = dynamics.roles_list[self.role_name]
        player = self.player.canonicalize()
        role = role_class(player)
        # Assign a label to disambiguate players with the same role
        try:
            dynamics.assignements_per_role[role_class.__name__] += 1
        except KeyError:
            dynamics.assignements_per_role[role_class.__name__] = 1
        if len([role_name for role_name in dynamics.available_roles if role_name == role_class.__name__]) > 1:
            role.disambiguation_label = chr(ord('A') + dynamics.assignements_per_role[role_class.__name__] - 1)

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
            return u'Ti è stato assegnato il ruolo di %s.' % self.full_role_name
        elif player == 'admin':
            return u'A%s %s è stato assegnato il ruolo di %s.' % ('d' if self.player.full_name[0] in ['A','E','I','O','U', 'a', 'e', 'i', 'o', 'u'] else '', self.player.full_name, self.full_role_name)
        else:
            return None


class SetMayorEvent(Event):
    RELEVANT_PHASES = [CREATION, SUNSET, DAWN]
    AUTOMATIC = True
    CAN_BE_SIMULATED = False

    player = models.ForeignKey(Player, null=True, related_name='+',on_delete=models.CASCADE)

    SET_MAYOR_CAUSES = (
        (BEGINNING, 'Beginning'),
        (ELECT, 'Elect'),
        (SUCCESSION_RANDOM, 'SuccessionRandom'),
        (SUCCESSION_CHOSEN, 'SuccessionChosen'),
        )
    cause = models.CharField(max_length=1, choices=SET_MAYOR_CAUSES, default=None)

    REAL_RELEVANT_PHASES = {
        BEGINNING: [CREATION],
        ELECT: [SUNSET],
        SUCCESSION_RANDOM: [DAWN, SUNSET],
        SUCCESSION_CHOSEN: [DAWN, SUNSET],
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in SetMayorEvent.REAL_RELEVANT_PHASES[self.cause]
        if self.player is not None:
            player = self.player.canonicalize()
            assert player.alive

            if self.cause == BEGINNING:
                assert dynamics.mayor is None
                assert dynamics.appointed_mayor is None

            if not player.is_mayor():
                dynamics.mayor = player
                dynamics.appointed_mayor = None

            # The mayor can be already in charge only if they are just
            # being re-elected
            else:
                assert self.cause == ELECT

            assert player.is_mayor()
        else:
            assert self.cause == SUCCESSION_RANDOM
            assert len(dynamics.get_alive_players())==0
            dynamics.mayor = None
            dynamics.appointed_mayor = None
        

    def to_player_string(self, player):
        if self.player is None:
            return None
        oa = self.player.oa
        if self.cause == BEGINNING:
            if player == self.player:
                return u'Sei stat%s nominat%s Sindaco del villaggio.' % (oa, oa)
            else:
                return u'%s è stat%s nominat%s Sindaco del villaggio.' % (self.player.full_name, oa, oa)
        elif self.cause == ELECT:
            if player == self.player:
                return u'Sei stat%s elett%s Sindaco del villaggio.' % (oa, oa)
            else:
                return u'%s è stat%s elett%s nuovo Sindaco del villaggio.' % (self.player.full_name, oa, oa)
        elif self.cause == SUCCESSION_RANDOM or self.cause == SUCCESSION_CHOSEN:
            if player == self.player:
                return u'Sei stat%s nominat%s nuovo Sindaco del villaggio.' % (oa, oa)
            else:
                return u'%s è stat%s nominat%s nuovo Sindaco del villaggio.' % (self.player.full_name, oa, oa)
        else:
            raise Exception('Unknown cause for SetMayorEvent')


class InitialPropositionEvent(Event):
    # An initial proposition published by the GM
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False
    
    text = models.TextField(verbose_name='Testo')

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'text': self.text,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.text = data['text']

    def apply(self, dynamics):
        pass
    
    def to_player_string(self, player):
        # This event is processed separately
        return None


class VoteAnnouncedEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True
    CAN_BE_SIMULATED = True

    voter = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    voted = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
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
    CAN_BE_SIMULATED = True

    voted = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
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


class PlayerResurrectsEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert not player.alive

        # If the player is a ghost, their power gets deactivated. Poor
        # they!
        if player.role.ghost:
            assert player.role.has_power
            player.role.has_power = False

        player.alive = True
        
    def to_player_string(self,player):
        oa = self.player.oa
        if player == self.player:
            return u'Sei stat%s resuscitat%s! Gioisci, una seconda vita ricca di possibilità ti si apre davanti!' % (oa, oa)
        else:
            return u'%s ritorna al villaggio viv%s, veget%s e sorridente, e riprende la sua vita come se niente fosse.' % (self.player.full_name, oa, oa)


class TransformationEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    full_role_name = models.CharField(max_length=200, default=None)

    TRANSFORMATION_CAUSES = (
        (TRANSFORMIST, 'Transformist'),
        (NECROPHILIAC, 'Necrophiliac')
        )
    cause = models.CharField(max_length=1, choices=TRANSFORMATION_CAUSES, default=None)

    def apply(self, dynamics):
        player = self.player.canonicalize()
        target = self.target.canonicalize()

        assert player.alive
        assert not target.alive

        if self.cause == TRANSFORMIST:
            assert player.role.__class__.__name__ == 'Trasformista'
        elif self.cause == NECROPHILIAC:
            assert player.role.__class__.__name__ == 'Necrofilo'
        else:
            raise Exception ('Unknown cause for TransformationEvent')

        # Check that power is not una tantum or that role is powerless
        if player.role.__class__.__name__ == 'Trasformista':
            assert target.role.frequency not in [NEVER, ONCE_A_GAME]

        # Take original role class if the target is a ghost
        new_role_class = target.role.__class__
        if target.role.ghost:
            new_role_class = target.role_class_before_ghost
            assert new_role_class is not None
        assert self.full_role_name == new_role_class.full_name
        assert new_role_class.team == self.player.team

        # Instantiate new role class and copy attributes
        player.role = new_role_class(player)
        player.aura = target.aura
        player.is_mystic = target.is_mystic

        # Call any role-specific code
        player.role.post_appearance(dynamics)

    def to_player_string(self, player):
        if self.cause == TRANSFORMIST:
            if player == self.player:
                return u'Dopo aver utilizzato il tuo potere su %s hai assunto il ruolo di %s.' % (self.target.full_name, self.full_role_name)
            elif player == 'admin':
                return u'%s ha utilizzato il proprio potere di Trasformista su %s assumendo il ruolo di %s.' % (self.player.full_name, self.target.full_name, self.full_role_name)
        elif self.cause == NECROPHILIAC:
            if player == self.player:
                return u'Dopo aver utilizzato il tuo potere su %s hai assunto il ruolo di %s.' % (self.target.full_name, self.full_role_name)
            elif player == 'admin':
                return u'%s ha utilizzato il proprio potere di Necrofilo su %s assumendo il ruolo di %s.' % (self.player.full_name, self.target.full_name, self.full_role_name)
        else:
            raise Exception ('Unknown cause for TransformationEvent')

class CorruptionEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert player.alive
        assert player.is_mystic and player.aura == WHITE

        # Change role in Negromante
        player.role = dynamics.roles_list['Negromante'](player)
        player.team = NEGROMANTI

    def to_player_string(self, player):
        if player == self.player:
            return u'Al tuo risveglio percepisci che qualcosa è cambiato in te. Senti un nuovo potere, una travolgente affinità per le arti occulte che pervade le tue membra, ed una incontenibile voglia di cioccolata calda. Lo Spettro della Corruzione ha preso possesso di te: sei diventato un Negromante, e da adesso per te comincia una nuova vita.'
        elif player == 'admin':
            return u'%s ha assunto il ruolo di Negromante per l\'effetto dello Spettro della Corruzione.' % (self.player.full_name)


class StakeFailedEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True

    STAKE_FAILED_CAUSES = (
        (MISSING_QUORUM, 'MissingQuorum'),
        (ADVOCATE, 'Advocate'),
        )
    cause = models.CharField(max_length=1, choices=STAKE_FAILED_CAUSES, default=None)

    def apply(self, dynamics):
        pass

    def to_player_string(self, player):
        if self.cause == MISSING_QUORUM:
            return u'Quest\'oggi non è stato raggiunto il quorum, per cui non viene ucciso nessuno. Che giornata sprecata.'
        elif self.cause == ADVOCATE:
            return u'Sebbene sia stato raggiunto il quorum, dei grovigli burocratici invalidano la sentenza: non viene pertanto ucciso nessuno. Che giornata sprecata.'
        else:
            raise Exception ('Unknown cause for StakeFailedEvent')


class PlayerDiesEvent(Event):
    RELEVANT_PHASES = [SUNSET, DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    DEATH_CAUSE_TYPES = (
        (STAKE, 'Stake'),
        (HUNTER, 'Hunter'),
        (WOLVES, 'Wolves'),
        (ASSASSIN, 'Assassin'),
        (DEATH_GHOST, 'DeathGhost'),
        )
    cause = models.CharField(max_length=1, choices=DEATH_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        STAKE: [SUNSET],
        HUNTER: [DAWN],
        WOLVES: [DAWN],
        DEATH_GHOST: [DAWN],
        ASSASSIN: [DAWN],
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in PlayerDiesEvent.REAL_RELEVANT_PHASES[self.cause]

        player = self.player.canonicalize()
        player.just_dead = True

        dynamics.upcoming_deaths.append(self)

    def apply_death(self, dynamics):
        assert dynamics.current_turn.phase in PlayerDiesEvent.REAL_RELEVANT_PHASES[self.cause]

        player = self.player.canonicalize()
        assert player.alive
        assert player.just_dead

        # Yeah, finally kill player!
        player.alive = False
        player.just_dead = False
        
        player.role.post_death(dynamics)

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


class SoothsayerModelEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    soothsayer = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    advertised_role = models.CharField(max_length=200, default=None) # Full name of role

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
            'target': self.target.user.username,
            'advertised_role': self.advertised_role,
            'soothsayer': self.soothsayer.user.username,
        })
        return ret

    def load_from_dict(self, data, players_map):
        self.target = players_map[data['target']]
        self.advertised_role = data['advertised_role']
        self.soothsayer = players_map[data['soothsayer']]

    def apply(self, dynamics):
        event = RoleKnowledgeEvent(player=self.soothsayer, target=self.target, full_role_name=self.advertised_role, cause=SOOTHSAYER)
        dynamics.generate_event(event)

class RoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    full_role_name = models.CharField(max_length=200, default=None)
    KNOWLEDGE_CAUSE_TYPES = (
        (SOOTHSAYER, 'Soothsayer'),
        (EXPANSIVE, 'Expansive'),
        (KNOWLEDGE_CLASS, 'KnowledgeClass'),
        # GHOST: a new Spettro (possibly a former Fantasma) is made
        # aware of its Negromanti
        (GHOST, 'Ghost'),
        # PHANTOM: a Negromante is made aware of the Fantasma just
        # transformed to Ghost
        (PHANTOM, 'Phantom'),
        # HYPNOTIST_DEATH: a Negromante is made aware of the Ipnotista
        # just transformed to Spettro dell'Ipnosi
        (HYPNOTIST_DEATH, 'HypnotistDeath'),
        (DEVIL, 'Devil'),
        (VISION_GHOST, 'Vision'),
        (MEDIUM, 'Medium'),
        (CORRUPTION, 'Corruption'),
        (NECROPHILIAC, 'Necrophiliac')
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        SOOTHSAYER: [CREATION],
        KNOWLEDGE_CLASS: [CREATION],
        EXPANSIVE: [DAWN],
        GHOST: [DAWN, SUNSET],
        PHANTOM: [DAWN, SUNSET],
        HYPNOTIST_DEATH: [DAWN, SUNSET],
        DEVIL: [DAWN],
        MEDIUM: [DAWN],
        VISION_GHOST: [DAWN],
        NECROPHILIAC: [DAWN],
        CORRUPTION: [DAWN]
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in RoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]

        if self.cause == SOOTHSAYER:
            assert self.player.canonicalize().role.__class__.__name__ == 'Divinatore'

        elif self.cause == EXPANSIVE:
            assert self.target.canonicalize().role.__class__.__name__ == 'Espansivo'

        elif self.cause == NECROPHILIAC:
            assert self.target.canonicalize().role.__class__.__name__ == 'Necrofilo'

        elif self.cause == GHOST:
            assert self.player.canonicalize().role.ghost
            assert self.target.canonicalize().role.__class__.__name__ == 'Negromante'

        elif self.cause == PHANTOM or self.cause == HYPNOTIST_DEATH or self.cause == CORRUPTION:
            assert self.player.canonicalize().role.__class__.__name__ == 'Negromante'
            assert self.target.canonicalize().role.ghost

        elif self.cause == KNOWLEDGE_CLASS:
            assert self.player.canonicalize().role.knowledge_class is not None
            assert self.target.canonicalize().role.knowledge_class is not None
            assert self.player.canonicalize().role.knowledge_class == self.target.canonicalize().role.knowledge_class

        elif self.cause == DEVIL:
            assert self.player.canonicalize().role.__class__.__name__ == 'Diavolo'
            assert self.target.canonicalize().alive

        elif self.cause == MEDIUM:
            assert self.player.canonicalize().role.__class__.__name__ == 'Medium'
            assert not self.target.canonicalize().alive

        elif self.cause == HYPNOTIST_DEATH:
            assert False

        if self.cause in [EXPANSIVE, GHOST, PHANTOM, HYPNOTIST_DEATH, KNOWLEDGE_CLASS]:
            assert self.target.canonicalize().role.full_name == self.full_role_name
    
    
    def to_player_string(self, player):
        toa = self.target.oa
        poa = self.player.oa
        role = self.full_role_name
        
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

        elif self.cause == PHANTOM:
            # self.player is a Necromancer, self.target has just become a Ghost
            if player == self.player:
                return u'Percepisci che %s era un Fantasma: dopo la morte è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che il Fantasma %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)

        elif self.cause == CORRUPTION:
            if player == self.player:
                return u'Vieni a sapere che %s è lo Spettro con il potere della Corruzione.' % (self.target.full_name)
            elif player == 'admin':
                return u'%s viene a sapere che lo Spettro che l\'ha corrott%s è %s.' % (self.player.full_name, poa, self.target.full_name)

        elif self.cause == GHOST:
            if player == self.player:
                return u'Vieni a sapere che %s è un Negromante.' % (self.target.full_name)
            elif player == 'admin':
                return u'Per spettrificazione, %s viene a sapere che %s è un Negromante.' % (self.player.full_name, self.target.full_name)

        elif self.cause == DEVIL:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role)
            elif player == 'admin':
                return u'Il Diavolo %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role)
        
        elif self.cause == MEDIUM:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role)
            elif player == 'admin':
                return u'Il Medium %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role)
        
        elif self.cause == HYPNOTIST_DEATH:
            if player == self.player:
                return u'Percepisci che %s era un Ipnotista: dopo la morte è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che l\'Ipnotista %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)
        
        elif self.cause == VISION_GHOST:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role)
            elif player == 'admin':
                return u'Lo Spettro con il potere della Visione %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role)
        
        elif self.cause == NECROPHILIAC:
            if player == self.player:
                return u'Percepisci che il Necrofilo %s ha profanato la tua salma questa notte.' % (self.target.full_name)
            elif player == 'admin':
                return u'%s viene a sapere che il Necrofilo %s ha profanato la sua tomba.' % (self.player.full_name, self.target.full_name)
        
        else:
            raise Exception ('Unknown cause for RoleKnowledgeEvent')
        
        return None
    
    def to_soothsayer_proposition(self):
        assert self.cause == SOOTHSAYER
        return u'%s ha il ruolo di %s.' % (self.target.full_name, self.full_role_name)

class AuraKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    aura = models.CharField(max_length=1, default=None, choices=Player.AURA_COLORS)
    KNOWLEDGE_CAUSE_TYPES = (
        (SEER, 'Seer'),
        (DETECTIVE, 'Detective'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass
    
    def to_player_string(self, player):
        aura = AURA_IT[ self.aura ].lower()
        
        if self.cause == SEER:
            if player == self.player:
                return u'Scopri che %s ha aura %s.' % (self.target.full_name, aura)
            elif player == 'admin':
                return u'Il Veggente %s scopre che %s ha aura %s.' % (self.player.full_name, self.target.full_name, aura)
            return None
        
        elif self.cause == DETECTIVE:
            if player == self.player:
                return u'Scopri che %s ha aura %s.' % (self.target.full_name, aura)
            elif player == 'admin':
                return u"L'Investigatore %s scopre che %s ha aura %s." % (self.player.full_name, self.target.full_name, aura)
            return None
        
        else:
            raise Exception ('Unknown cause for AuraKnowledgeEvent')


class MysticityKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
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
            return u'Scopri che %s %sè un mistico.' % (self.target.full_name, result)
        elif player == 'admin':
            return u'%s scopre che %s %sè un mistico.' % (self.player.full_name, self.target.full_name, result)


class TeamKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    team = models.CharField(max_length=1, default=None, choices=Player.TEAMS)
    # There is only one choice, but I like to have this for
    # homogeneity
    KNOWLEDGE_CAUSE_TYPES = (
        (VISION_GHOST, 'VisionGhost'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert self.target.canonicalize().team == self.team or self.target.canonicalize().has_confusion
    
    def to_player_string(self, player):
        team = TEAM_IT[ self.team ]
        
        if player == self.player:
            return u'Scopri che %s appartiene alla Fazione dei %s.' % (self.target.full_name, team)
        elif player == 'admin':
            return u'%s scopre che %s appartiene alla Fazione dei %s.' % (self.player.full_name, self.target.full_name, team)
        return None


class MovementKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    # Target and target2 are to be understood as how they are in
    # CommandEvent; that is, target is the player that was watched and
    # target2 is where he went (for the Stalker) or who went by him
    # (for the Voyeur)
    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    target2 = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    KNOWLEDGE_CAUSE_TYPES = (
        (STALKER, 'Stalker'),
        (VOYEUR, 'Voyeur'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert self.target.pk != self.target2.pk
    
    def to_player_string(self, player):
        if self.cause == STALKER:
            moving_player = self.target
            destination = self.target2
        elif self.cause == VOYEUR:
            moving_player = self.target2
            destination = self.target
        else:
            raise Exception ('Unknown cause')
        
        if player == self.player:
            return u'Scopri che stanotte %s si è recat%s da %s.' % (moving_player.full_name, moving_player.oa, destination.full_name)
        elif player == 'admin':
            return u'%s scopre che stanotte %s si è recat%s da %s.' % (self.player.full_name, moving_player.full_name, moving_player.oa, destination.full_name)
        else:
            return None


class NoMovementKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    # Target is to be understood as how it is in CommandEvent;
    # that is, target is the player that was watched.
    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    
    KNOWLEDGE_CAUSE_TYPES = (
        (STALKER, 'Stalker'),
        (VOYEUR, 'Voyeur'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert self.player.pk != self.target.pk
    
    def to_player_string(self, player):
        if player == self.player:
            if self.cause == STALKER:
                return u'Scopri che stanotte %s non si è recat%s da nessuna parte.' % (self.target.full_name, self.target.oa)
            elif self.cause == VOYEUR:
                return u'Scopri che stanotte nessun personaggio si è recato da %s.' % (self.target.full_name)
            else:
                raise Exception ('Unknown cause')
        
        elif player == 'admin':
            if self.cause == STALKER:
                return u'%s scopre che stanotte %s non si è recat%s da nessuna parte.' % (self.player.full_name, self.target.full_name, self.target.oa)
            elif self.cause == VOYEUR:
                return u'%s scopre che stanotte nessun personaggio si è recato da %s.' % (self.player.full_name, self.target.full_name)
            else:
                raise Exception ('Unknown cause')
        
        else:
            return None

class QuantitativeMovementKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    visitors = models.IntegerField()

    KNOWLEDGE_CAUSE_TYPES = (
        (KEEPER, 'Keeper'),
        (GUARD, 'Guard')
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert self.player.pk != self.target.pk

    def to_player_string(self, player):
        if player == self.player:
            if self.visitors == 0:
                return u'Scopri che stanotte nessun personaggio si è recato da %s.' % (self.target.full_name)
            elif self.visitors == 1:
                return u'Scopri che stanotte esattamente un altro personaggio si è recato da %s.' % (self.target.full_name)
            else:
                return u'Scopri che stanotte esattamente %s altri personaggi si sono recati da %s.' % (self.visitors, self.target.full_name)

        elif player == 'admin':
            if self.visitors == 0:
                return u'%s scopre che stanotte nessun personaggio si è recato da %s.' % (self.player.full_name, self.target.full_name)
            elif self.visitors == 1:
                return u'%s scopre che stanotte esattamente un altro personaggio si è recato da %s.' % (self.player.full_name, self.target.full_name)
            else:
                return u'%s scopre che stanotte %s altri personaggi si sono recati da %s.' % (self.player.full_name, self.visitors, self.target.full_name)

        else:
            return None



class HypnotizationEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    hypnotist = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player.canonicalize()
        hypnotist = self.hypnotist.canonicalize()

        assert hypnotist.role.__class__.__name__ == 'Ipnotista'

        player.hypnotist = hypnotist
    
    def to_player_string(self, player):
        oa = self.player.oa
        
        if player == 'admin':
            return u'%s è stat%s ipnotizzat%s da %s.' % (self.player.full_name, oa, oa, self.hypnotist.full_name)
        else:
            return None


class GhostificationEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    ghost = models.CharField(max_length=1, choices=POWER_NAMES.items(), default=None)
    GHOSTIFICATION_CAUSES = (
        (NECROMANCER, 'Necromancer'),
        (PHANTOM, 'Phantom'),
        (HYPNOTIST_DEATH, 'HypnotistDeath'),
        )
    cause = models.CharField(max_length=1, choices=GHOSTIFICATION_CAUSES, default=None)

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert not player.alive
        assert self.ghost not in dynamics.used_ghost_powers
        assert not(dynamics.death_ghost_created and self.cause == NECROMANCER)
        #assert not(dynamics.death_ghost_created and self.cause == HYPNOTIST_DEATH and not dynamics.death_ghost_just_created), (dynamics.death_ghost_created, dynamics.death_ghost_just_created, self.cause)
        assert not(self.cause == HYPNOTIST_DEATH and not isinstance(player.role, Ipnotista))
        assert not(self.cause == HYPNOTIST_DEATH and player.team != NEGROMANTI)
        #assert not(self.cause == HYPNOTIST_DEATH and self.ghost != IPNOSI)
        #assert not(self.cause != HYPNOTIST_DEATH and self.ghost == IPNOSI)
        #assert not(self.ghost == IPNOSI and [player2 for player2 in dynamics.get_alive_players() if isinstance(player2.role, Ipnotista) and player2.team == NEGROMANTI] != [])

        # Update global status
        dynamics.used_ghost_powers.add(self.ghost)

        # Call pre disappearance code
        player.role.pre_disappearance(dynamics)

        # Save original role for Trasformista
        assert player.role_class_before_ghost is None
        player.role_class_before_ghost = player.role.__class__

        # Real ghostification
        player.role = dynamics.roles_list[POWER_NAMES[self.ghost]](player)
        player.team = NEGROMANTI

    def to_player_string(self, player):
        oa = self.player.oa
        power = POWER_NAMES[self.ghost]
        
        if self.cause == NECROMANCER:
            if player == self.player:
                return u'Credevi che i giochi fossero fatti? Pensavi che la morte fosse un evento definitivo? Certo che no! Come nelle migliori soap opera, non c\'è pace neanche dopo la sepoltura. Sei stat%s risvegliat%s come Spettro, e ti è stato assegnato il seguente potere soprannaturale: %s.' % (oa, oa, power)
            elif player == 'admin':
                return u'%s è stat%s risvegliat%s come Spettro con il seguente potere soprannaturale: %s.' % (self.player.full_name, oa, oa, power)
        
        elif self.cause == PHANTOM:
            if player == self.player:
                return u'La sopraggiunta morte ti dà un senso di beatitudine. Sei diventat%s uno Spettro, e possiedi ora il seguente potere soprannaturale: %s.' % (oa, power)
            elif player == 'admin':
                return u'Il Fantasma %s è divenuto uno Spettro con il seguente potere soprannaturale: %s' % (self.player.full_name, power)
        
        elif self.cause == HYPNOTIST_DEATH:
            if player == self.player:
                return u'Sei diventat%s uno Spettro, e possiedi ora il seguente potere soprannaturale: %s.' % (oa, power)
            elif player == 'admin':
                return u'L\'Ipnotista %s è divenuto uno Spettro con il seguente potere soprannaturale: %s' % (self.player.full_name, power)
        
        else:
            raise Exception ('Unknown cause for GhostificationEvent')
        
        return None


class GhostificationFailedEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert not player.alive
        assert player.role.__class__.__name__ == 'Fantasma'

    def to_player_string(self, player):
        oa = self.player.oa
        
        if player == self.player:
            return u'Sembra che tu abbia aspettato troppo a morire: i poteri soprannaturali sono stati tutti assegnati, per cui sei condannat%s a rimanere un Fantasma.' % oa
        elif player == 'admin':
            return u'Il Fantasma %s non diventa uno Spettro per mancanza di poteri soprannaturali.' % self.player.full_name
        else:
            return None


class PowerOutcomeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    command = models.OneToOneField(CommandEvent, on_delete=models.CASCADE)
    success = models.BooleanField(default=False)
    sequestrated = models.BooleanField(default=False)

    def apply(self, dynamics):
        assert self.command.type == USEPOWER
        assert self.command.player.pk == self.player.pk
        assert self.command.target is not None

        player = self.player.canonicalize()
        player.role.last_usage = dynamics.prev_turn
        player.role.last_target = self.command.target.canonicalize()
    
    def to_player_string(self, player):
        target = self.command.target
        target2 = self.command.target2
        target_ghost = self.command.target_ghost
        oa = self.player.oa

        def role_description(role, rcbf):
            desc = role.full_name
            if role.ghost:
                desc += ', ex %s' % (rcbf.full_name)
            return desc

        player_role = role_description(self.player.role, self.player.role_class_before_ghost)
        target_role = role_description(target.role, target.role_class_before_ghost)

        if self.success:
            if player == self.player:
                return u'Hai utilizzato con successo il tuo potere su %s.' % target.full_name
            
            elif player == 'admin':
                return u'%s (%s) ha utilizzato con successo il proprio potere su %s (%s).' % (self.player.full_name, player_role, target.full_name, target_role)
        
        else:
            if player == self.player:
                return u'Ti risvegli confus%s e stordit%s: l\'unica cosa di cui sei cert%s è di non essere riuscit%s ad utilizzare il tuo potere su %s, questa notte.' % (oa, oa, oa, oa, target.full_name)
            
            elif player == 'admin':
                string = u'%s (%s) non è riuscit%s ad utilizzare il proprio potere su %s (%s) ' % (self.player.full_name, player_role, oa, target.full_name, target_role)
                if self.sequestrated:
                    string += '(sequestrat%s).' % oa
                else:
                    string += '(non sequestrat%s).' %oa
                return string


class DisqualificationEvent(Event):
    RELEVANT_PHASES = [DAY, NIGHT]
    AUTOMATIC = False

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    private_message = models.TextField()
    public_message = models.TextField(null=True, blank=True, default=None)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'player': self.player.user.username,
                'private_message': self.private_message,
                'public_message': self.public_message,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.player = players_map[data['player']]
        self.private_message = data['private_message']
        self.public_message = data['public_message']

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert player.active

        dynamics.pending_disqualifications.append(self)

    def to_player_string(self, player):
        oa = self.player.oa
        
        if player == self.player:
            return u'Sei stat%s squalificat%s. Il motivo della squalifica è: %s' % (oa, oa, self.private_message)
        elif player == 'admin':
            return u'%s è stat%s squalificat%s.' % (self.player.full_name, oa, oa)
        else:
            return None


class FreeTextEvent(Event):
    RELEVANT_PHASES = [CREATION, NIGHT, DAWN, SUNSET, DAY]
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

    def apply(self, dynamics):
        pass

    def to_player_string(self, player):
        return self.text


class ExileEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    EXILE_CAUSES = (
        (DISQUALIFICATION, 'Disqualification'),
        (TEAM_DEFEAT, 'TeamDefeat'),
        )
    cause = models.CharField(max_length=1, choices=EXILE_CAUSES, default=None)
    disqualification = models.OneToOneField(DisqualificationEvent, null=True, blank=True, default=None, on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert player.active

        was_alive = player.alive

        player.role.pre_disappearance(dynamics)

        if self.cause == DISQUALIFICATION:
            assert self.disqualification is not None
        else:
            assert self.disqualification is None

        player.active = False
        if self.cause == DISQUALIFICATION:
            player.disqualified = True

        if was_alive:
            player.role.post_death(dynamics)
    def to_player_string(self, player):
        oa = self.player.oa
        
        if self.cause == DISQUALIFICATION:
            if player == self.player:
                return u'Sei stat%s squalificat%s. Il motivo della squalifica è: %s' % (oa, oa, self.disqualification.private_message)
            else:
                if self.disqualification.public_message is None:
                    return u'%s è stat%s squalificat%s.' % (self.player.full_name, oa, oa)
                else:
                    return u'%s è stat%s squalificat%s. Il motivo della squalifica è: %s' % (self.player.full_name, oa, oa, self.disqualification.public_message)
        
        elif self.cause == TEAM_DEFEAT:
            team = TEAM_IT[ self.player.canonicalize().team ]
            
            if player == self.player:
                return u'La tua Fazione è stata sconfitta. Per te non rimane che l\'esilio.'
            else:
                return u'%s è stat%s esiliat%s a causa della sconfitta della Fazione dei %s.' % (self.player.full_name, oa, oa, team)


class ForceVictoryEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = False

    popolani_win = models.BooleanField(default=None)
    lupi_win = models.BooleanField(default=None)
    negromanti_win = models.BooleanField(default=None)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'popolani_win': self.popolani_win,
                'lupi_win': self.lupi_win,
                'negromanti_win': self.negromanti_win,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.popolani_win = data['popolani_win']
        self.lupi_win = data['lupi_win']
        self.negromanti_win = data['negromanti_win']

    def apply(self, dynamics):
        dynamics.generate_event(VictoryEvent(popolani_win=self.popolani_win,
                                             lupi_win=self.lupi_win,
                                             negromanti_win=self.negromanti_win,
                                             cause=FORCED,
                                             timestamp=self.timestamp))

    def to_player_string(self, player):
        return None


class VictoryEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    popolani_win = models.BooleanField(default=None)
    lupi_win = models.BooleanField(default=None)
    negromanti_win = models.BooleanField(default=None)
    VICTORY_CAUSES = (
        (NATURAL, 'Natural'),
        (FORCED, 'Forced'),
        )
    cause = models.CharField(max_length=1, choices=VICTORY_CAUSES, default=None)

    def get_winners(self):
        winners = []
        if self.popolani_win:
            winners.append(POPOLANI)
        if self.lupi_win:
            winners.append(LUPI)
        if self.negromanti_win:
            winners.append(NEGROMANTI)
        return winners

    def apply(self, dynamics):
        winners = self.get_winners()
        dynamics.winners = winners
        dynamics.over = True
        dynamics.giove_is_happy = True
        dynamics.server_is_on_fire = True
    
    def to_player_string(self, player):
        winners = self.get_winners()
        if len(winners) == 1:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s.</b>' % (TEAM_IT[winners[0]])
        elif len(winners) == 2:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s e della Fazione dei %s.</b>' % (TEAM_IT[winners[0]], TEAM_IT[winners[1]])
        elif len(winners) == 3:
            # Questa cosa mi auguro che non possa davvero succedere
            return u'<b>La partita si è conclusa con la vittoria di tutte le Fazioni.</b>'
        else:
            raise Exception ('Number of winner is not reasonable')



