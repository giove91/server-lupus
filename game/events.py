# -*- coding: utf-8 -*-

from django.db import models
from .models import Event, Player, StringsSetField, RoleField, MultipleRoleField, BooleanArrayField
from .roles.base import Role
from .constants import *
from .utils import dir_dict, rev_dict
from importlib import import_module
from inspect import isclass

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
    role_class = RoleField(null=True)
    multiple_role_class = MultipleRoleField(null=True)

    def __unicode__(self):
        return u"CommandEvent %d" % self.pk

    def __repr__(self):
        return u"%sEvent (%d) from %s" % (dict(self.ACTION_TYPES)[self.type], self.pk, self.player)

    def player_role(self):
        if self.player is not None:
            return self.player.canonicalize().role.name
        else:
            return None

    def target_role(self):
        if self.target is not None:
            return self.target.canonicalize().role.name
        else:
            return None

    def target2_role(self):
        if self.target2 is not None:
            return self.target2.canonicalize().role.name
        else:
            return None

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'player': self.player.user.username,
                'target': self.target.user.username if self.target is not None else None,
                'target2': self.target2.user.username if self.target2 is not None else None,
                'role_class': self.role_class.as_string() if self.role_class is not None else None,
                'multiple_role_class': [x.as_string() for x in self.multiple_role_class] if self.multiple_role_class is not None else None,
                'type': dict(CommandEvent.ACTION_TYPES)[self.type],
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.player = players_map[data['player']]
        self.target = players_map[data['target']]
        self.target2 = players_map[data['target2']]
        self.role_class = Role.get_from_string(data['role_class']) if data['role_class'] is not None else None
        self.multiple_role_class = {Role.get_from_string(x) for x in data['multiple_role_class']} if data['multiple_role_class'] is not None else None
        self.type = rev_dict(CommandEvent.ACTION_TYPES)[data['type']]

    def check_phase(self, dynamics=None, turn=None):
        if turn is None:
            turn = dynamics.current_turn
        return turn.phase in CommandEvent.REAL_RELEVANT_PHASES[self.type]

    def apply(self, dynamics):
        assert self.check_phase(dynamics=dynamics)

        assert self.player is not None

        # Canonicalize players
        self.player = self.player.canonicalize(dynamics)
        if self.target is not None:
            self.target = self.target.canonicalize(dynamics)
        if self.target2 is not None:
            self.target2 = self.target2.canonicalize(dynamics)

        if self.type == APPOINT:
            assert self.player.is_mayor(dynamics)
            assert self.target2 is None
            assert self.role_class is None
            assert self.multiple_role_class is None
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
            assert self.role_class is None
            assert self.multiple_role_class is None
            if self.type == VOTE:
                self.player.recorded_vote = self.target
            elif self.type == ELECT:
                self.player.recorded_elect = self.target
            else:
                assert False, "Should not arrive here"

        elif self.type == USEPOWER:
            self.player.canonicalize(dynamics).power.apply_usepower(dynamics, self)

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
        self.seed = str(data['seed'])

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
        module = import_module('game.roles.' + self.ruleset)
        dynamics.rules = module.Rules()
        dynamics.valid_roles = [getattr(module, k) for k in dir(module) if isclass(getattr(module, k)) and issubclass(getattr(module, k), Role) and getattr(module, k).__module__ == 'game.roles.' + self.ruleset]
        dynamics.valid_roles.sort(key=lambda x: (TEAMS.index(x.team), x.name))
        dynamics.ruleset = self.ruleset

class SpectralSequenceEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    # Sequence is stored like a number, where the nth bit determines if the nth death
    # is ghostified
    sequence = BooleanArrayField()

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'sequence': self.sequence,
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.sequence = data['sequence']

    def apply(self, dynamics):
        dynamics.spectral_sequence = self.sequence.copy()

    def to_player_string(self, player):
        if player == 'admin':
            seq = ', '.join([str(i+1) for i,x in enumerate(self.sequence) if x])
            return u'È stata assegnata la seguente sequenza spettrale: %s' % seq

class AvailableRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = False

    role_class = RoleField()

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'role_class': self.role_class.as_string(),
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.role_class = Role.get_from_string(data['role_class'])

    def apply(self, dynamics):
        assert len(dynamics.available_roles) < len(dynamics.players), "%d %d" % (len(dynamics.available_roles), len(dynamics.players))
        dynamics.available_roles.append(self.role_class)

        # If this is the last role, assign randomly the roles to the
        # players and then choose a random mayor
        if len(dynamics.available_roles) == len(dynamics.players):
            players_pks = sorted(dynamics.players_dict.keys())
            mayor = dynamics.random.choice(players_pks)
            dynamics.random.shuffle(players_pks)

            given_roles = {}
            for player_pk, role_class in zip(players_pks, dynamics.available_roles):
                event = SetRoleEvent(player=dynamics.players_dict[player_pk], role_class=role_class)
                dynamics.generate_event(event)
                given_roles[player_pk] = role_class

            if dynamics.rules.mayor:
                event = SetMayorEvent()
                event.player = dynamics.players_dict[mayor]
                event.cause = BEGINNING
                dynamics.generate_event(event)

            # Then compute all the knowledge classes and generate the
            # relevant events
            knowledge_classes = {}
            knowledge_classes_rev = {}
            for player in dynamics.players:
                role_class = given_roles[player.pk]
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
                        event = RoleKnowledgeEvent(player=player, target=target, role_class=given_roles[target.pk], cause=KNOWLEDGE_CLASS)
                        dynamics.generate_event(event)


class SetRoleEvent(Event):
    RELEVANT_PHASES = [CREATION]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    role_class = RoleField()

    def apply(self, dynamics):
        player = self.player
        assert player.canonical
        role = self.role_class(player)
        # Assign a label to disambiguate players with the same role
        try:
            dynamics.assignements_per_role[self.role_class] += 1
        except KeyError:
            dynamics.assignements_per_role[self.role_class] = 1
        if dynamics.available_roles.count(self.role_class) > 1:
            role.disambiguation_label = chr(ord('A') + dynamics.assignements_per_role[self.role_class] - 1)

        player.role = role
        player.team = role.team
        player.aura = role.aura
        player.is_mystic = role.is_mystic
        if player.role.initial_dead_power is None:
            from .roles.base import NoPower
            player.dead_power = NoPower(player)
        else:
            player.dead_power = player.role.initial_dead_power(player)

        assert player.role is not None
        assert player.team is not None
        assert player.aura is not None
        assert player.is_mystic is not None
        assert player.dead_power is not None
    def to_player_string(self, player):
        if player == self.player:
            return u'Ti è stato assegnato il ruolo di %s.' % self.role_class.name
        elif player == 'admin':
            return u'A%s %s è stato assegnato il ruolo di %s.' % ('d' if self.player.full_name[0] in ['A','E','I','O','U', 'a', 'e', 'i', 'o', 'u'] else '', self.player.full_name, self.role_class.name)
        else:
            return None


class SetMayorEvent(Event):
    RELEVANT_PHASES = [CREATION, SUNSET, DAWN]
    AUTOMATIC = True
    CAN_BE_SIMULATED = False

    player = models.ForeignKey(Player, null=True, blank=True, related_name='+',on_delete=models.CASCADE)

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
            player = self.player
            assert player.canonical
            assert player.alive

            if self.cause == BEGINNING:
                assert dynamics.mayor is None
                assert dynamics.appointed_mayor is None

            if not player.is_mayor(dynamics):
                dynamics.mayor = player
                dynamics.appointed_mayor = None

            # The mayor can be already in charge only if they are just
            # being re-elected
            else:
                assert self.cause == ELECT

            assert player.is_mayor(dynamics)
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
        assert self.voter.alive
        assert self.voted.alive

    def to_player_string(self,player):
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
        assert self.voted.alive
        assert self.vote_num > 0

    def to_player_string(self,player):
        # This event is processed separately
        return None


class PlayerResurrectsEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player
        assert not player.alive
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
    role_class = RoleField(default=None)

    TRANSFORMATION_CAUSES = (
        (TRANSFORMIST, 'Transformist'),
        (NECROPHILIAC, 'Necrophiliac')
        )
    cause = models.CharField(max_length=1, choices=TRANSFORMATION_CAUSES, default=None)

    def apply(self, dynamics):
        player = self.player
        target = self.target

        assert player.canonical and target.canonical
        assert player.alive
        assert not target.alive

        if self.cause == TRANSFORMIST:
            assert player.role.__class__.__name__ == 'Trasformista'
        elif self.cause == NECROPHILIAC:
            assert player.role.__class__.__name__ == 'Necrofilo'
        else:
            raise Exception ('Unknown cause for TransformationEvent')

        assert self.role_class.team == self.player.team

        # Instantiate new role class and copy attributes
        player.role = self.role_class(player)
        player.aura = target.aura
        player.is_mystic = target.is_mystic

        # Call any role-specific code
        player.role.post_appearance(dynamics)

    def to_player_string(self, player):
        if self.cause == TRANSFORMIST:
            if player == self.player:
                return u'Dopo aver utilizzato la tua abilità su %s hai assunto il ruolo di %s.' % (self.target.full_name, self.role_class.name)
            elif player == 'admin':
                return u'%s ha utilizzato la propria abilità di Trasformista su %s assumendo il ruolo di %s.' % (self.player.full_name, self.target.full_name, self.role_class.name)
        elif self.cause == NECROPHILIAC:
            if player == self.player:
                return u'Dopo aver utilizzato la tua abilità su %s hai assunto il ruolo di %s.' % (self.target.full_name, self.role_class.name)
            elif player == 'admin':
                return u'%s ha utilizzato la propria abilità di Necrofilo su %s assumendo il ruolo di %s.' % (self.player.full_name, self.target.full_name, self.role_class.name)
        else:
            raise Exception ('Unknown cause for TransformationEvent')

class CorruptionEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)

    def apply(self, dynamics):
        player = self.player

        assert player.canonical
        assert player.alive
        assert player.is_mystic and player.aura == WHITE

        # Change role in Negromante
        [role_class] = [x for x in dynamics.valid_roles if x.necromancer]
        player.role = role_class(player)
        player.team = dynamics.rules.necromancers_team

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
        (LIFE_GHOST, 'LifeGhost'),
        )
    cause = models.CharField(max_length=1, choices=DEATH_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        STAKE: [SUNSET],
        HUNTER: [DAWN],
        WOLVES: [DAWN],
        DEATH_GHOST: [DAWN],
        ASSASSIN: [DAWN],
        LIFE_GHOST: [DAWN]
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in PlayerDiesEvent.REAL_RELEVANT_PHASES[self.cause]

        player = self.player
        assert player.canonical
        player.just_dead = True

        dynamics.upcoming_deaths.append(self)

    def apply_death(self, dynamics):
        assert dynamics.current_turn.phase in PlayerDiesEvent.REAL_RELEVANT_PHASES[self.cause]

        player = self.player
        assert player.canonical
        assert player.alive
        assert player.just_dead

        # Yeah, finally kill player!
        player.alive = False
        player.just_dead = False

        player.role.post_not_alive(dynamics)
        player.role.post_death(dynamics)
        player.dead_power.post_death(dynamics)
        # Trigger generic post_death code
        dynamics.rules.post_death(dynamics, player)

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
    advertised_role = RoleField()

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
            'target': self.target.user.username,
            'advertised_role': self.advertised_role.as_string(),
            'soothsayer': self.soothsayer.user.username,
        })
        return ret

    def load_from_dict(self, data, players_map):
        self.target = players_map[data['target']]
        self.advertised_role = Role.get_from_string(data['advertised_role'])
        self.soothsayer = players_map[data['soothsayer']]

    def apply(self, dynamics):
        pass

    def to_player_string(self, player):
        if player == 'admin':
            return u'Il Divinatore %s riceve la frase: "%s"' % (self.soothsayer.full_name, self.to_soothsayer_proposition())

    def to_soothsayer_proposition(self):
        return u'%s ha il ruolo di %s.' % (self.target.full_name, self.advertised_role.name)



class RoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    role_class = RoleField()

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
        (SPECTRAL_SEQUENCE, 'SpectralSequence'),
        # HYPNOTIST_DEATH: a Negromante is made aware of the Ipnotista
        # just transformed to Spettro dell'Ipnosi
        (HYPNOTIST_DEATH, 'HypnotistDeath'),
        (DEVIL, 'Devil'),
        (DETECTIVE, 'Detective'),
        (VISION_GHOST, 'Vision'),
        (MEDIUM, 'Medium'),
        (CORRUPTION, 'Corruption'),
        (NECROPHILIAC, 'Necrophiliac')
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        SOOTHSAYER: [DAWN],
        KNOWLEDGE_CLASS: [CREATION],
        EXPANSIVE: [DAWN],
        GHOST: [DAWN, SUNSET],
        PHANTOM: [DAWN, SUNSET],
        HYPNOTIST_DEATH: [DAWN, SUNSET],
        DEVIL: [DAWN],
        DETECTIVE: [DAWN],
        MEDIUM: [DAWN],
        VISION_GHOST: [DAWN],
        NECROPHILIAC: [DAWN],
        CORRUPTION: [DAWN],
        SPECTRAL_SEQUENCE: [DAWN, SUNSET]
        }

    def check_validity(self, dynamics):
        return self.player.active and self.target.active

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in RoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]
        assert self.player.canonical
        if self.cause == SOOTHSAYER:
            assert self.player.canonicalize().role.__class__.__name__ == 'Divinatore'

        elif self.cause == EXPANSIVE:
            assert self.target.canonicalize().role.__class__.__name__ == 'Espansivo'

        elif self.cause == NECROPHILIAC:
            assert self.target.canonicalize().role.__class__.__name__ == 'Necrofilo'

        elif self.cause == GHOST:
            assert self.player.canonicalize().specter
            assert self.target.canonicalize().role.__class__.__name__ == 'Negromante'

        elif self.cause == PHANTOM or self.cause == HYPNOTIST_DEATH or self.cause == CORRUPTION:
            assert self.player.canonicalize().role.__class__.__name__ == 'Negromante'
            assert self.target.canonicalize().specter

        elif self.cause == KNOWLEDGE_CLASS:
            assert self.player.canonicalize().role.knowledge_class is not None
            assert self.target.canonicalize().role.knowledge_class is not None
            assert self.player.canonicalize().role.knowledge_class == self.target.canonicalize().role.knowledge_class

        elif self.cause == DEVIL:
            assert self.player.canonicalize().role.__class__.__name__ == 'Diavolo'
            assert self.target.canonicalize().alive

        elif self.cause == DETECTIVE:
            assert self.player.canonicalize().role.__class__.__name__ == 'Investigatore'
            assert not self.target.canonicalize().alive

        elif self.cause == MEDIUM:
            assert self.player.canonicalize().role.__class__.__name__ == 'Medium'
            assert not self.target.canonicalize().alive

        elif self.cause == HYPNOTIST_DEATH:
            assert False

        if self.cause in [EXPANSIVE, KNOWLEDGE_CLASS, GHOST]:
            assert isinstance(self.target.canonicalize().role, self.role_class)

        if self.cause in [PHANTOM, HYPNOTIST_DEATH]:
            assert isinstance(self.target.canonicalize().dead_power, self.role_class)


    def to_player_string(self, player):
        toa = self.target.oa
        poa = self.player.oa
        role_name = self.role_class.name

        if self.cause == EXPANSIVE:
            if player == self.player:
                return u'%s ti rivela di essere l\'Espansivo.' % self.target.full_name
            elif player == 'admin':
                return u'%s rivela a %s di essere l\'Espansivo.' % (self.target.full_name, self.player.full_name)

        elif self.cause == KNOWLEDGE_CLASS:
            if player == self.player:
                return u'A %s è stato assegnato il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'Per conoscenza iniziale, %s sa che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == PHANTOM:
            # self.player is a Necromancer, self.target has just become a Ghost
            if player == self.player:
                return u'Percepisci che %s era un Fantasma: dopo la morte è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che il Fantasma %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)

        elif self.cause == SPECTRAL_SEQUENCE:
            # self.player is a Necromancer, self.target has just become a Ghost
            if player == self.player:
                return u'Percepisci che %s è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)

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
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'Il Diavolo %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == DETECTIVE:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'L\'Investigatore %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == SOOTHSAYER:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'Il Divinatore %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == MEDIUM:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'Il Medium %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == HYPNOTIST_DEATH:
            if player == self.player:
                return u'Percepisci che %s era un Ipnotista: dopo la morte è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che l\'Ipnotista %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)

        elif self.cause == VISION_GHOST:
            if player == self.player:
                return u'Scopri che %s ha il ruolo di %s.' % (self.target.full_name, role_name)
            elif player == 'admin':
                return u'Lo Spettro con il potere della Visione %s scopre che %s ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        elif self.cause == NECROPHILIAC:
            if player == self.player:
                return u'Percepisci che il Necrofilo %s ha profanato la tua salma questa notte.' % (self.target.full_name)
            elif player == 'admin':
                return u'%s viene a sapere che il Necrofilo %s ha profanato la sua tomba.' % (self.player.full_name, self.target.full_name)

        else:
            raise Exception ('Unknown cause for RoleKnowledgeEvent')

        return None

class NegativeRoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    role_class = RoleField(default=None)

    KNOWLEDGE_CAUSE_TYPES = (
        (SOOTHSAYER, 'Soothsayer'),
    )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    REAL_RELEVANT_PHASES = {
        SOOTHSAYER: [DAWN],
    }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in NegativeRoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]
        assert self.player.canonical
        assert self.player.canonicalize().role.__class__.__name__ == 'Divinatore'

    def to_player_string(self, player):
        toa = self.target.oa
        poa = self.player.oa
        role_name = self.role_class.name

        if player == self.player:
            return u'Scopri che %s non ha il ruolo di %s.' % (self.target.full_name, role_name)
        elif player == 'admin':
            return u'Il Divinatore %s scopre che %s non ha il ruolo di %s.' % (self.player.full_name, self.target.full_name, role_name)

        return None

class MultipleRoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    target = models.ForeignKey(Player, related_name='+',on_delete=models.CASCADE)
    multiple_role_class = MultipleRoleField(default=None)
    KNOWLEDGE_CAUSE_TYPES = (
        (DEVIL, 'Diavolo'),
        (VISION_GHOST, 'VisionGhost'),
    )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)
    response = models.BooleanField(default=False)

    REAL_RELEVANT_PHASES = {
        DEVIL: [DAWN],
        VISION_GHOST: [DAWN],
    }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in MultipleRoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]
        assert (dynamics.get_apparent_role(self.target) in self.multiple_role_class) == self.response

    def to_player_string(self, player):
        toa = self.target.oa
        poa = self.player.oa
        roles = ", ".join(sorted([x.name for x in self.multiple_role_class]))

        if player == self.player:
            return u'Scopri che %s %s ha il ruolo tra i seguenti: %s.' % (self.target.full_name, u"non " if not self.response else u"", roles)
        elif player == 'admin':
            return u'%s scopre che %s %s ha il ruolo tra i seguenti: %s.' % (self.player.full_name, self.target.full_name, u"non " if not self.response else u"", roles)

        return None



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
        assert self.player.canonical
        assert self.target.canonicalize().team == self.team or self.target.canonicalize().has_confusion

    def to_player_string(self, player):
        team = TEAM_IT[ self.team ]

        if player == self.player:
            return u'Scopri che %s appartiene alla Fazione dei %s.' % (self.target.full_name, team)
        elif player == 'admin':
            return u'%s scopre che %s appartiene alla Fazione dei %s.' % (self.player.full_name, self.target.full_name, team)
        return None

class VoteKnowledgeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    voter = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    voted = models.ForeignKey(Player, related_name='+', null=True, on_delete=models.CASCADE)
    KNOWLEDGE_CAUSE_TYPES = (
        (SPY, 'Spy'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        pass

    def to_player_string(self, player):

        if player == self.player:
            if self.voted is None:
                return u'Scopri che ieri %s non ha votato nessuno.' % (self.voter.full_name)
            else:
                return u'Scopri che ieri %s ha votato %s.' % (self.voter.full_name, self.voted.full_name)
        elif player == 'admin':
            if self.voted is None:
                return u'%s scopre che ieri %s non ha votato nessuno.' % (self.player.full_name, self.voter.full_name)
            else:
                return u'%s scopre che ieri %s ha votato %s.' % (self.player.full_name, self.voter.full_name, self.voted.full_name)
        else:
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
    target2 = models.ForeignKey(Player, related_name='+', null=True, on_delete=models.CASCADE)
    KNOWLEDGE_CAUSE_TYPES = (
        (STALKER, 'Stalker'),
        (VOYEUR, 'Voyeur'),
        (KIDNAPPER, 'Kidnapper'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert (self.target2 is None) == (self.cause == KIDNAPPER)

    def to_player_string(self, player):
        if self.cause == KIDNAPPER:
            if player == self.player:
                return u'Scopri che stanotte %s aveva intenzione di utilizzare la propria abilità.' % (self.target.full_name)
            elif player == 'admin':
                return u'%s scopre che stanotte %s aveva intenzione di utilizzare la propria abilità.' % (self.player.full_name, self.target.full_name)
            else:
                return None

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
        (KIDNAPPER, 'Kidnapper'),
        )
    cause = models.CharField(max_length=1, choices=KNOWLEDGE_CAUSE_TYPES, default=None)

    def apply(self, dynamics):
        assert self.player.pk != self.target.pk

    def to_player_string(self, player):
        if player == self.player:
            if self.cause == STALKER:
                return u'Scopri che stanotte %s non si è recat%s da nessuna parte.' % (self.target.full_name, self.target.oa)
            elif self.cause == KIDNAPPER:
                return u'Scopri che stanotte %s non aveva intenzione di utilizzare alcuna abilità.' % (self.target.full_name)
            elif self.cause == VOYEUR:
                return u'Scopri che stanotte nessun personaggio si è recato da %s.' % (self.target.full_name)
            else:
                raise Exception ('Unknown cause')

        elif player == 'admin':
            if self.cause == STALKER:
                return u'%s scopre che stanotte %s non si è recat%s da nessuna parte.' % (self.player.full_name, self.target.full_name, self.target.oa)
            if self.cause == KIDNAPPER:
                return u'%s scopre che stanotte %s non aveva intenzione di utilizzare alcuna abilità.' % (self.player.full_name, self.target.full_name)
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
        assert self.player.canonical and self.hypnotist.canonical
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
    ghost = RoleField(default=None)

    GHOSTIFICATION_CAUSES = (
        (NECROMANCER, 'Necromancer'),
        (PHANTOM, 'Phantom'),
        (HYPNOTIST_DEATH, 'HypnotistDeath'),
        (SPECTRAL_SEQUENCE, 'SpectralSequence'),
        )
    cause = models.CharField(max_length=1, choices=GHOSTIFICATION_CAUSES, default=None)

    def check_validity(self, dynamics):
        return dynamics.rules.necromancers_team in dynamics.playing_teams

    def apply(self, dynamics):
        assert self.player.canonical
        player = self.player.canonicalize()

        assert not player.alive
        assert dynamics.rules.necromancers_team in dynamics.playing_teams
        assert self.ghost not in dynamics.used_ghost_powers
        assert self.ghost.ghost
        assert not(dynamics.death_ghost_created and self.cause == NECROMANCER)
        #assert not(dynamics.death_ghost_created and self.cause == HYPNOTIST_DEATH and not dynamics.death_ghost_just_created), (dynamics.death_ghost_created, dynamics.death_ghost_just_created, self.cause)
        assert not(self.cause == HYPNOTIST_DEATH and not isinstance(player.role, Ipnotista))
        assert not(self.cause == HYPNOTIST_DEATH and player.team != dynamics.rules.necromancers_team)
        #assert not(self.cause == HYPNOTIST_DEATH and self.ghost != IPNOSI)
        #assert not(self.cause != HYPNOTIST_DEATH and self.ghost == IPNOSI)
        #assert not(self.ghost == IPNOSI and [player2 for player2 in dynamics.get_alive_players() if isinstance(player2.role, Ipnotista) and player2.team == NEGROMANTI] != [])

        # Update global status
        if not self.ghost.allow_duplicates:
            dynamics.used_ghost_powers.add(self.ghost)

        # Real ghostification
        player.dead_power = self.ghost(player)
        player.dead_power.post_appearance(dynamics)
        player.specter = True
        player.team = dynamics.rules.necromancers_team

    def to_player_string(self, player):
        oa = self.player.oa
        power = self.ghost.verbose_name

        if self.cause == NECROMANCER:
            if player == self.player:
                return u'Credevi che i giochi fossero fatti? Pensavi che la morte fosse un evento definitivo? Certo che no! Come nelle migliori soap opera, non c\'è pace neanche dopo la sepoltura. Sei stat%s risvegliat%s come %s.' % (oa, oa, power)
            elif player == 'admin':
                return u'%s è stat%s risvegliat%s come %s.' % (self.player.full_name, oa, oa, power)

        elif self.cause == SPECTRAL_SEQUENCE:
            if player == self.player:
                return u'Credevi che i giochi fossero fatti? Pensavi che la morte fosse un evento definitivo? Certo che no! Come nelle migliori soap opera, non c\'è pace neanche dopo la sepoltura. Sei diventat%s uno %s.' % (oa, power)
            elif player == 'admin':
                return u'%s si è risvegliat%s come %s.' % (self.player.full_name, oa, power)

        elif self.cause == PHANTOM:
            if player == self.player:
                return u'La sopraggiunta morte ti dà un senso di beatitudine. Sei diventat%s uno %s.' % (oa, power)
            elif player == 'admin':
                return u'Il Fantasma %s è divenuto uno %s.' % (self.player.full_name, power)

        elif self.cause == HYPNOTIST_DEATH:
            if player == self.player:
                return u'Sei diventat%s uno %s.' % (oa, power)
            elif player == 'admin':
                return u'L\'Ipnotista %s è divenuto uno %s' % (self.player.full_name, power)

        else:
            raise Exception ('Unknown cause for GhostificationEvent')

        return None

class GhostificationFailedEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)

    def apply(self, dynamics):
        assert self.player.canonical
        player = self.player.canonicalize()

        assert not player.alive
        assert player.role.__class__.__name__ == 'Fantasma'

    def to_player_string(self, player):
        oa = self.player.oa

        if player == self.player:
            return u'Sembra che tu abbia aspettato troppo a morire: i poteri sono stati tutti assegnati, per cui sei condannat%s a rimanere un Fantasma.' % oa
        elif player == 'admin':
            return u'Il Fantasma %s non diventa uno Spettro per mancanza di poteri.' % self.player.full_name
        else:
            return None

class UnGhostificationEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)

    def apply(self, dynamics):
        assert self.player.canonical
        player = self.player.canonicalize()

        assert player.specter
        from game.roles.base import NoPower
        if not self.player.dead_power.allow_duplicates:
            dynamics.used_ghost_powers.remove(self.player.dead_power.__class__)
        player.dead_power.pre_disappearance(dynamics)
        player.dead_power = NoPower(player)
        player.specter = False

    def to_player_string(self, player):
        oa = self.player.oa

        if player == self.player:
            return u'Sembra che tu possa finalmente riposare... Non sei più uno Spettro.'
        elif player == 'admin':
            return u'%s non è più uno Spettro.' % self.player.full_name
        else:
            return None


class GhostSwitchEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    ghost = RoleField(default=None)

    GHOSTIFICATION_CAUSES = (
        (NECROMANCER, 'Necromancer'),
        (DEATH_GHOST, 'DeathGhost'),
        (LIFE_GHOST, 'LifeGhost'),
        (SHAMAN, 'Shaman'),
        )
    cause = models.CharField(max_length=1, choices=GHOSTIFICATION_CAUSES, default=None)

    def apply(self, dynamics):
        assert self.player.canonical
        player = self.player.canonicalize()

        assert self.ghost not in dynamics.used_ghost_powers, self.ghost
        assert self.player.specter
        #assert not(dynamics.death_ghost_created and self.cause == HYPNOTIST_DEATH and not dynamics.death_ghost_just_created), (dynamics.death_ghost_created, dynamics.death_ghost_just_created, self.cause)
        #assert not(self.cause == HYPNOTIST_DEATH and self.ghost != IPNOSI)
        #assert not(self.cause != HYPNOTIST_DEATH and self.ghost == IPNOSI)
        #assert not(self.ghost == IPNOSI and [player2 for player2 in dynamics.get_alive_players() if isinstance(player2.role, Ipnotista) and player2.team == NEGROMANTI] != [])

        # Update global status
        if not self.ghost.allow_duplicates:
            dynamics.used_ghost_powers.add(self.ghost)
        if not self.player.dead_power.allow_duplicates:
            dynamics.used_ghost_powers.remove(self.player.dead_power.__class__)

        # Power switch!
        player.dead_power.pre_disappearance(dynamics)
        player.dead_power = self.ghost(player)
        player.dead_power.post_appearance(dynamics)

    def to_player_string(self, player):
        oa = self.player.oa
        power = self.ghost.verbose_name

        if self.cause == NECROMANCER:
            if player == self.player:
                return u'Percepisci che qualcosa è cambiato intorno a te. Sei ora uno %s.' % (power)
            elif player == 'admin':
                return u'%s è ora uno %s.' % (self.player.full_name, power)

        elif self.cause == LIFE_GHOST or self.cause == SHAMAN:
            assert self.ghost.name == "Nessuno"
            if player == self.player:
                return u'Percepisci l\'effetto dell\'Incantesimo attivo su di te svanire, e con esso il tuo potere.'
            elif player == 'admin':
                return u'L\'Incantesimo attivo su %s si è spezzato.' % self.player.full_name

        else:
            raise Exception ('Unknown cause for GhostSwitchEvent')

        return None


class PowerOutcomeEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    command = models.OneToOneField(CommandEvent, on_delete=models.CASCADE)
    power = RoleField()
    success = models.BooleanField(default=False)

    def apply(self, dynamics):
        assert self.command.type == USEPOWER
        assert self.command.player.pk == self.player.pk
        assert self.command.target is not None
        assert self.power is not None
        assert self.player.canonical

        player = self.player.canonicalize()
        if self.success or not dynamics.rules.forgiving_failures:
            player.power.last_usage = dynamics.prev_turn
            player.power.last_target = self.command.target.canonicalize()
            if player.power.frequency == EVERY_OTHER_NIGHT:
                player.cooldown = True

    def to_player_string(self, player):
        target = self.command.target
        oa = self.player.oa

        if self.success:
            if player == self.player:
                return u'Hai utilizzato con successo %s su %s.' % ("il tuo potere" if self.power.dead_power else "la tua abilità", target.full_name)

            elif player == 'admin':
                return u'%s ha utilizzato con successo %s di %s su %s.' % (self.player.full_name, "il proprio potere" if self.power.dead_power else "la propria abilità", self.power.name, target.full_name)

        else:
            if player == self.player:
                return u'Ti risvegli confus%s e stordit%s: l\'unica cosa di cui sei cert%s è di non essere riuscit%s ad utilizzare %s su %s, questa notte.' % (oa, oa, oa, oa, "il tuo potere" if self.power.dead_power else "la tua abilità", target.full_name)

            elif player == 'admin':
                return '%s non è riuscit%s ad utilizzare %s di %s su %s.' % (self.player.full_name, oa, "il proprio potere" if self.power.dead_power else "la propria abilità", self.power.name, target.full_name)


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
        self.player = self.player.canonicalize(dynamics)

        assert self.player.active

        dynamics.pending_disqualifications.append(self)

    def to_player_string(self, player):
        oa = self.player.oa

        if player == self.player:
            return u'Sei stat%s squalificat%s. Il motivo della squalifica è: %s' % (oa, oa, self.private_message)
        elif player == 'admin':
            return u'%s è stat%s squalificat%s.' % (self.player.full_name, oa, oa)
        else:
            return None

class TelepathyEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+', on_delete=models.CASCADE)
    perceived_event = models.ForeignKey(Event, related_name='+', on_delete=models.CASCADE)

    def apply(self, dynamics):
        pass

    def get_perceived_message(self):
        return self.perceived_event.to_player_string(self.perceived_event.player)

    def to_player_string(self, player):
        if player == 'admin':
            return u'Lo Spettro %s percepisce che %s ha ottenuto la seguente informazione: %s' % (self.player, self.perceived_event.player, self.get_perceived_message())
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
        assert self.player.canonical
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
            player.role.post_not_alive(dynamics)
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
    RELEVANT_PHASES = [DAWN, DAY, SUNSET, NIGHT]
    AUTOMATIC = False

    winners = StringsSetField(max_length=10, default={}, null=True)

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
                'winners': list(self.winners),
                })
        return ret

    def load_from_dict(self, data, players_map):
        self.winners = set(data['winners'])

    def apply(self, dynamics):
        if dynamics.current_turn.phase in [DAWN, SUNSET]:
            if self.winners is not None:
                dynamics.generate_event(VictoryEvent(winners=self.winners, cause=FORCED, timestamp=self.timestamp))
        else:
            dynamics.recorded_winners = self.winners

    def to_player_string(self, player):
        return None


class VictoryEvent(Event):
    RELEVANT_PHASES = [DAWN, SUNSET]
    AUTOMATIC = True

    winners = StringsSetField(max_length=10, default={})

    VICTORY_CAUSES = (
        (NATURAL, 'Natural'),
        (FORCED, 'Forced'),
        )
    cause = models.CharField(max_length=1, choices=VICTORY_CAUSES, default=None)


    def apply(self, dynamics):
        dynamics.winners = self.winners
        dynamics.over = True
        dynamics.giove_is_happy = True
        dynamics.server_is_on_fire = True

    def to_player_string(self, player):
        winners = list(self.winners)
        if len(winners) == 1:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s.</b>' % (TEAM_IT[winners[0]])
        elif len(winners) == 2:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s e della Fazione dei %s.</b>' % (TEAM_IT[winners[0]], TEAM_IT[winners[1]])
        elif len(winners) == 3:
            # Questa cosa mi auguro che non possa davvero succedere
            return u'<b>La partita si è conclusa con la vittoria di tutte le Fazioni.</b>'
        else:
            raise Exception ('Number of winner is not reasonable')
