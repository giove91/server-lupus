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
        from my_random import WichmannHill
        dynamics.random = WichmannHill()
        dynamics.random.seed(int(self.seed))


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
            event.cause = BEGINNING
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
        role = Role.get_from_name(self.role_name).name
        
        if player == self.player:
            return u'Ti è stato assegnato il ruolo di %s.' % role
        elif player == 'admin':
            return u'A%s %s è stato assegnato il ruolo di %s.' % ('d' if self.player.full_name[0] in ['A','E','I','O','U', 'a', 'e', 'i', 'o', 'u'] else '', self.player.full_name, role)
        else:
            return None


class SetMayorEvent(Event):
    RELEVANT_PHASES = [CREATION, SUNSET, DAWN]
    AUTOMATIC = True
    CAN_BE_SIMULATED = False

    player = models.ForeignKey(Player, null=True, related_name='+')

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
        # This event is processed separately
        return None


class VoteAnnouncedEvent(Event):
    RELEVANT_PHASES = [SUNSET]
    AUTOMATIC = True
    CAN_BE_SIMULATED = True

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
    CAN_BE_SIMULATED = True

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


class PlayerResurrectsEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        assert not player.alive

        # If the player is a ghost, their power gets deactivated. Poor
        # they!
        if isinstance(player.role, Spettro):
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

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200, default=None)

    def apply(self, dynamics):
        player = self.player.canonicalize()
        target = self.target.canonicalize()

        assert player.alive
        assert not target.alive

        # Check for forbidden roles
        assert not isinstance(target.role, (Lupo, Negromante, Fantasma))

        # Check that power is not una tantum or that role is powerless
        assert not isinstance(target.role, tuple(UNA_TANTUM_ROLES))
        assert not isinstance(target.role, tuple(POWERLESS_ROLES))

        # Take original role class if the target is a ghost
        new_role_class = target.role.__class__
        if isinstance(target.role, Spettro):
            new_role_class = target.role_class_before_ghost
            assert new_role_class is not None
        assert self.role_name == new_role_class.__name__

        # Instantiate new role class and copy attributes
        player.role = new_role_class(player)
        player.aura = target.aura
        player.is_mystic = target.is_mystic
        assert player.team == POPOLANI

        # Call any role-specific code
        player.role.post_appearance(dynamics)

    def to_player_string(self, player):
        role = Role.get_from_name(self.role_name).name
        
        if player == self.player:
            return u'Dopo aver utilizzato il tuo potere su %s hai assunto il ruolo di %s.' % (self.target.full_name, role)
        elif player == 'admin':
            return u'%s ha utilizzato il proprio potere di Trasformista su %s assumendo il ruolo di %s.' % (self.player.full_name, self.target.full_name, role)


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

    player = models.ForeignKey(Player, related_name='+')
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

        # Fantasma death
        if isinstance(player.role, Fantasma):
            powers = set(Spettro.POWER_NAMES.keys())
            available_powers = powers - dynamics.used_ghost_powers - set([MORTE, IPNOSI])
            if len(available_powers) >= 1:
                power = dynamics.random.choice(list(available_powers))
                dynamics.generate_event(GhostificationEvent(player=player, cause=PHANTOM, ghost=power))
                for negromante in dynamics.players:
                    if isinstance(negromante.role, Negromante):
                        dynamics.generate_event(RoleKnowledgeEvent(player=player,
                                                                   target=negromante,
                                                                   role_name=Negromante.__name__,
                                                                   cause=GHOST))
                        dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                                   target=player,
                                                                   role_name=Spettro.__name__,
                                                                   cause=PHANTOM))
            else:
                dynamics.generate_event(GhostificationFailedEvent(player=player))

        # Ipnotista death
        if isinstance(player.role, Ipnotista) and player.team == NEGROMANTI:
            # Note: the condition "player.team == NEGROMANTI" is not explicitly written in the ruleset, but it is implied by it
            if IPNOSI not in dynamics.used_ghost_powers:
                dynamics.generate_event(GhostificationEvent(player=player, cause=HYPNOTIST_DEATH, ghost=IPNOSI))
                for negromante in dynamics.players:
                    if isinstance(negromante.role, Negromante):
                        dynamics.generate_event(RoleKnowledgeEvent(player=player,
                                                                   target=negromante,
                                                                   role_name=Negromante.__name__,
                                                                   cause=GHOST))
                        dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                                   target=player,
                                                                   role_name=Spettro.__name__,
                                                                   cause=HYPNOTIST_DEATH))

        # Yeah, finally kill player!
        player.alive = False
        player.just_dead = False

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

    player_role = models.CharField(max_length=200, default=None)
    advertised_role = models.CharField(max_length=200, default=None)
    soothsayer_num = models.IntegerField()

    def to_dict(self):
        ret = Event.to_dict(self)
        ret.update({
            'player_role': self.player_role,
            'advertised_role': self.advertised_role,
            'soothsayer_num': self.soothsayer_num,
        })
        return ret

    def load_from_dict(self, data, players_map):
        self.player_role = data['player_role']
        self.advertised_role = data['advertised_role']
        self.soothsayer_num = int(data['soothsayer_num'])

    def apply(self, dynamics):
        soothsayer = [pl for pl in dynamics.players if isinstance(pl.role, Divinatore)][self.soothsayer_num]
        target = dynamics.random.choice([pl for pl in dynamics.players if pl.role.__class__.__name__ == self.player_role and pl is not soothsayer])
        event = RoleKnowledgeEvent(player=soothsayer, target=target, role_name=self.advertised_role, cause=SOOTHSAYER)
        dynamics.generate_event(event)

class RoleKnowledgeEvent(Event):
    RELEVANT_PHASES = [CREATION, DAWN, SUNSET]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    role_name = models.CharField(max_length=200, default=None)
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
        (MEDIUM, 'Medium'),
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
        }

    def apply(self, dynamics):
        assert dynamics.current_turn.phase in RoleKnowledgeEvent.REAL_RELEVANT_PHASES[self.cause]

        if self.cause == SOOTHSAYER:
            assert isinstance(self.player.canonicalize().role, Divinatore)

        elif self.cause == EXPANSIVE:
            assert isinstance(self.target.canonicalize().role, Espansivo)

        elif self.cause == GHOST:
            assert isinstance(self.player.canonicalize().role, Spettro)
            assert isinstance(self.target.canonicalize().role, Negromante)

        elif self.cause == PHANTOM or self.cause == HYPNOTIST_DEATH:
            assert isinstance(self.player.canonicalize().role, Negromante)
            assert isinstance(self.target.canonicalize().role, Spettro)

        elif self.cause == KNOWLEDGE_CLASS:
            assert self.player.canonicalize().role.knowledge_class is not None
            assert self.target.canonicalize().role.knowledge_class is not None
            assert self.player.canonicalize().role.knowledge_class == self.target.canonicalize().role.knowledge_class

        elif self.cause == DEVIL:
            assert isinstance(self.player.canonicalize().role, Diavolo)
            assert self.target.canonicalize().alive

        elif self.cause == MEDIUM:
            assert isinstance(self.player.canonicalize().role, Medium)
            assert not self.target.canonicalize().alive

        elif self.cause == HYPNOTIST_DEATH:
            # TODO: implement
            pass

        if self.cause in [EXPANSIVE, GHOST, PHANTOM, HYPNOTIST_DEATH, KNOWLEDGE_CLASS]:
            role_class = roles_map[self.role_name]
            assert isinstance(self.target.canonicalize().role, role_class)
    
    
    def to_player_string(self, player):
        toa = self.target.oa
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

        elif self.cause == PHANTOM:
            # self.player is a Necromancer, self.target has just become a Ghost
            if player == self.player:
                return u'Percepisci che %s era un Fantasma: dopo la morte è diventat%s uno Spettro.' % (self.target.full_name, toa)
            elif player == 'admin':
                return u'Il Negromante %s viene a sapere che il Fantasma %s è diventato uno Spettro.' % (self.player.full_name, self.target.full_name)

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
        
        else:
            raise Exception ('Unknown cause for RoleKnowledgeEvent')
        
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
            return u'Scopri che %s %sè un mistico.' % (self.target.full_name, result)
        elif player == 'admin':
            return u'%s scopre che %s %sè un mistico.' % (self.player.full_name, self.target.full_name, result)


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
        assert self.target.canonicalize().team == self.team
    
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
    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    target2 = models.ForeignKey(Player, related_name='+')
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
    player = models.ForeignKey(Player, related_name='+')
    target = models.ForeignKey(Player, related_name='+')
    
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



class HypnotizationEvent(Event):
    RELEVANT_PHASES = [DAWN]
    AUTOMATIC = True

    player = models.ForeignKey(Player, related_name='+')
    hypnotist = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()
        hypnotist = self.hypnotist.canonicalize()

        assert not isinstance(player.role, Ipnotista)
        assert isinstance(hypnotist.role, Ipnotista)

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

    player = models.ForeignKey(Player, related_name='+')
    ghost = models.CharField(max_length=1, choices=Spettro.POWERS_LIST, default=None)
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
        assert not(dynamics.ghosts_created_last_night and self.cause == NECROMANCER)
        assert not(self.cause == HYPNOTIST_DEATH and not isinstance(player.role, Ipnotista))
        assert not(self.cause == HYPNOTIST_DEATH and player.team != NEGROMANTI)
        #assert not(self.cause == HYPNOTIST_DEATH and self.ghost != IPNOSI)
        #assert not(self.cause != HYPNOTIST_DEATH and self.ghost == IPNOSI)
        #assert not(self.ghost == IPNOSI and [player2 for player2 in dynamics.get_alive_players() if isinstance(player2.role, Ipnotista) and player2.team == NEGROMANTI] != [])

        # Update global status
        if self.cause == NECROMANCER:
            dynamics.ghosts_created_last_night = True
        dynamics.used_ghost_powers.add(self.ghost)
        if self.ghost == MORTE:
            dynamics.death_ghost_created = True
            dynamics.death_ghost_just_created = True

        # Call pre disappearance code
        player.role.pre_disappearance(dynamics)

        # Save original role for Trasformista
        assert player.role_class_before_ghost is None
        player.role_class_before_ghost = player.role.__class__

        # Real ghostification
        player.role = Spettro(player, power=self.ghost)
        player.team = NEGROMANTI

    def to_player_string(self, player):
        oa = self.player.oa
        power = Spettro.POWER_NAMES[self.ghost]
        
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

    player = models.ForeignKey(Player, related_name='+')

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert not player.alive
        assert isinstance(player.role, Fantasma)

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

    player = models.ForeignKey(Player, related_name='+')
    command = models.OneToOneField(CommandEvent)
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
            desc = role.name
            if isinstance(role, Spettro):
                desc += ' %s, ex %s' % (Spettro.POWER_NAMES[role.power], rcbf.name)
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

    player = models.ForeignKey(Player, related_name='+')
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

    player = models.ForeignKey(Player, related_name='+')
    EXILE_CAUSES = (
        (DISQUALIFICATION, 'Disqualification'),
        (TEAM_DEFEAT, 'TeamDefeat'),
        )
    cause = models.CharField(max_length=1, choices=EXILE_CAUSES, default=None)
    disqualification = models.OneToOneField(DisqualificationEvent, null=True, blank=True, default=None)

    def apply(self, dynamics):
        player = self.player.canonicalize()

        assert player.active

        player.role.pre_disappearance(dynamics)

        if self.cause == DISQUALIFICATION:
            assert self.disqualification is not None
        else:
            assert self.disqualification is None

        player.active = False
        if self.cause == DISQUALIFICATION:
            player.disqualified = True
    
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

    def get_winners(self, dynamics):
        winners = []
        if self.popolani_win:
            winners.append(POPOLANI)
        if self.lupi_win:
            winners.append(LUPI)
        if self.negromanti_win:
            winners.append(NEGROMANTI)
        return winners

    def apply(self, dynamics):
        winners = self.get_winners(dynamics)
        dynamics.winners = winners
        dynamics.over = True
        dynamics.giove_is_happy = True
        dynamics.server_is_on_fire = True
    
    def to_player_string(self, player):
        dynamics = self.turn.game.get_dynamics()
        winners = self.get_winners(dynamics)
        if len(winners) == 1:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s.</b>' % (TEAM_IT[winners[0]])
        elif len(winners) == 2:
            return u'<b>La partita si è conclusa con la vittoria della Fazione dei %s e della Fazione dei %s.</b>' % (TEAM_IT[winners[0]], TEAM_IT[winners[1]])
        elif len(winners) == 3:
            # Questa cosa mi auguro che non possa davvero succedere
            return u'<b>La partita si è conclusa con la vittoria di tutte le Fazioni.</b>'
        else:
            raise Exception ('Number of winner is not reasonable')



