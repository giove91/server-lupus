from ..models import KnowsChild, Player
from ..constants import *

import sys

class Role(object):
    full_name = 'Generic role'
    disambiguation_label = None
    team = None
    aura = None
    is_mystic = False
    ghost = False

    ''' Priority of actions.
    Lower values will act before during dawn computation.
    Equal values will act in random order.
    See constants.py for a list of priority constants. '''
    priority = None

    ''' How often the power can be used. Can be:
    - NEVER
    - EVERY_NIGHT
    - EVERY_OTHER_NIGHT
    - ONCE_A_GAME '''
    frequency = NEVER

    ''' Whether the role can act the first night of play (usually True, except for killers. '''
    can_act_first_night = True

    ''' A critical blocker is a role that can block powers that can block powers,
    so it must be handled with care to avoid paradoxes that can set the server on fire. '''
    critical_blocker = False

    ''' When the following is True, player blocked by this role will not be seen by roles
    that query movements, such as Voyeur and Stalker. '''
    sequester = False

    ''' Roles in the same knowledge class will be aware of each other at game start. '''
    knowledge_class = None

    message = 'Usa il tuo potere su:'
    message2 = 'Parametro secondario:'
    message_ghost = 'Potere soprannaturale:'

    def __init__(self, player):
        self.player = player.canonicalize()
        self.last_usage = None
        self.last_target = None
        self.recorded_target = None
        self.recorded_target2 = None
        self.recorded_target_ghost = None
        self.recorded_command = None

    def __unicode__(self):
        return u"%s" % self.name

    @staticmethod
    def get_from_name(role_name):
        [role_class] = [x for x in Role.__subclasses__() if x.__name__ == role_name]
        return role_class

    def get_disambiguated_name(self):
        if self.disambiguation_label is not None:
            return self.full_name + ' ' + self.disambiguation_label
        else:
            return self.full_name
    disambiguated_name = property(get_disambiguated_name)

    def can_use_power(self):
        if not self.ghost and not self.player.alive:
            return False

        if not self.can_act_first_night and self.player.game.current_turn.full_days_from_start() == 0:
            return False

        if self.frequency == NEVER:
            return False
        elif self.frequency == EVERY_NIGHT:
            return True
        elif self.frequency == EVERY_OTHER_NIGHT:
            return self.last_usage is None or self.days_from_last_usage() >= 2
        elif self.frequency == ONCE_A_GAME:
            return self.last_usage is None
        else:
            raise Exception("Invalid frequency value")

    def get_targets(self):
        '''Returns the list of possible targets.'''
        return None
    
    def get_targets2(self):
        '''Returns the list of possible second targets.'''
        return None
    
    def get_targets_ghost(self):
        '''Returns the list of possible ghost-power targets.'''
        return None
    
    def days_from_last_usage(self):
        if self.last_usage is None:
            return None
        else:
            return self.player.game.current_turn.date - self.last_usage.date

    def unrecord_targets(self):
        self.recorded_target = None
        self.recorded_target2 = None
        self.recorded_target_ghost = None
        self.recorded_command = None

    def apply_usepower(self, dynamics, event):
        # First checks
        assert event.player.pk == self.player.pk
        assert self.can_use_power(), (event, event.player, event.player.role)

        # Check target validity
        targets = self.get_targets()
        if targets is None:
            assert event.target is None
        else:
            assert event.target is None or event.target in targets, (event.target, targets, event, event.player, event.player.role)

        # Check target2 validity
        targets2 = self.get_targets2()
        if targets2 is None:
            assert event.target2 is None, event.player.role.power
        else:
            assert event.target2 is None or event.target2 in targets2

        # Check target_ghost validity
        targets_ghost = self.get_targets_ghost()
        if targets_ghost is None:
            assert event.target_ghost is None
        else:
            assert event.target_ghost is None or event.target_ghost in targets_ghost

        # Record targets and command
        self.recorded_target = event.target
        self.recorded_target2 = event.target2
        self.recorded_target_ghost = event.target_ghost
        self.recorded_command = event

    def pre_apply_dawn(self, dynamics):
        ''' Check any condition that must be met in order for the power to succeed.'''
        return True

    def pre_disappearance(self, dynamics):
        """To be called just before this role disappears (either because the
        player is disqualified or because they change role).

        """
        pass

    def post_appearance(self, dynamics):
        """To be called just after this role appears as a result of a
        Trasformista assuming it.

        """
        pass

    def post_death(self, dynamics):
        """To be called just after this role dies or is exiled while beong alive.

        """

    def apply_dawn(self, dynamics):
        raise NotImplementedError("Please extend this method in subclasses")

    def get_blocked(self, players):
        return []

    def needs_soothsayer_propositions(self):
        """Should return False unless the player is a Divinatore who has not received
        a propositions according to the rules. In that case, it should return a
        description of the problem."""
        return False

# Fazione dei Popolani

class Contadino(Role):
    full_name = 'Contadino'
    team = POPOLANI
    aura = WHITE
    priority = USELESS

class Cacciatore(Role):
    full_name = 'Cacciatore'
    team = POPOLANI
    aura = BLACK
    priority = KILLER
    frequency = ONCE_A_GAME
    can_act_first_night = False

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from ..events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=HUNTER))


class Custode(Role):
    full_name = 'Custode del cimitero'
    team = POPOLANI
    aura = WHITE
    priority = MODIFY_INFLUENCE
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_keeper = True
        visitors = [visitor for visitor in self.recorded_target.visitors if visitor.pk not in [self.player.pk, self.recorded_target.pk] or dynamics.illusion == (self.player, self.recorded_target)]
        from ..events import QuantitativeMovementKnowledgeEvent
        dynamics.generate_event(QuantitativeMovementKnowledgeEvent(player=self.player, target=self.recorded_target, visitors=len(visitors), cause=KEEPER))

class Divinatore(Role):
    full_name = 'Divinatore'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = USELESS

    def needs_soothsayer_propositions(self):
        from ..events import SoothsayerModelEvent
        events = SoothsayerModelEvent.objects.filter(soothsayer=self.player)
        if len([ev for ev in events if ev.target == ev.soothsayer]) > 0:
            return KNOWS_ABOUT_SELF
        if len(events) != 4:
            return NUMBER_MISMATCH
        if sorted([ev.target.canonicalize().role.full_name == ev.advertised_role for ev in events]) != sorted([False, False, True, True]):
            return TRUTH_MISMATCH

        return False


class Esorcista(Role):
    full_name = 'Esorcista'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    critical_blocker = True
    priority = BLOCK
    frequency = EVERY_OTHER_NIGHT

    # message = 'Benedici la casa di:'

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        ret = []
        for blocker in players:
            if blocker.pk == self.player.pk:
                continue
            if not blocker.role.ghost:
                continue
            if blocker.role.recorded_target is not None and \
                    blocker.role.recorded_target.pk == self.recorded_target.pk:
                ret.append(blocker.pk)
        return ret

    def apply_dawn(self, dynamics):
        # Nothing to do here...
        pass


class Espansivo(Role):
    full_name = 'Espansivo'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, full_role_name=self.full_name, cause=EXPANSIVE))


class Guardia(Role):
    full_name = 'Guardia del corpo'
    team = POPOLANI
    aura = WHITE
    priority = MODIFY_INFLUENCE
    frequency = EVERY_NIGHT

    # message = 'Proteggi:'

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_guard = True
        visitors = [visitor for visitor in self.recorded_target.visitors if visitor.pk not in [self.player.pk, self.recorded_target.pk] or dynamics.illusion == (self.player, self.recorded_target)]
        from ..events import QuantitativeMovementKnowledgeEvent
        dynamics.generate_event(QuantitativeMovementKnowledgeEvent(player=self.player, target=self.recorded_target,visitors=len(visitors), cause=GUARD))


class Investigatore(Role):
    full_name = 'Investigatore'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=dynamics.get_apparent_aura(self.recorded_target), cause=DETECTIVE))


class Mago(Role):
    full_name = 'Mago'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import MysticityKnowledgeEvent
        dynamics.generate_event(MysticityKnowledgeEvent(player=self.player, target=self.recorded_target, is_mystic=dynamics.get_apparent_mystic(self.recorded_target), cause=MAGE))


class Massone(Role):
    full_name = 'Massone'
    team = POPOLANI
    aura = WHITE
    knowledge_class = 0
    priority = USELESS

class Messia(Role):
    full_name = 'Messia'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = MODIFY
    frequency = ONCE_A_GAME

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # Power fails on Spettri
        if self.recorded_target.role.ghost:
            return False
        return True

    def apply_dawn(self, dynamics):
        if not self.recorded_target.just_resurrected:
            self.recorded_target.just_resurrected = True
            from ..events import PlayerResurrectsEvent
            dynamics.generate_event(PlayerResurrectsEvent(player=self.recorded_target))


class Sciamano(Role):
    full_name = 'Sciamano'
    team = POPOLANI
    aura = BLACK
    is_mystic = True
    critical_blocker = True
    priority = BLOCK
    frequency = EVERY_OTHER_NIGHT


    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        if self.recorded_target.role.ghost:
            return [self.recorded_target.pk]
        else:
            return []

    def apply_dawn(self, dynamics):
        # Nothing to do here...
        pass


class Stalker(Role):
    full_name = 'Stalker'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import MovementKnowledgeEvent, NoMovementKnowledgeEvent
        gen_set = set()
        gen_num = 0
        for visiting in self.recorded_target.visiting:
            if visiting.pk != self.recorded_target.pk:
                dynamics.generate_event(MovementKnowledgeEvent(player=self.player, target=self.recorded_target, target2=visiting, cause=STALKER))
                gen_set.add(visiting.pk)
                gen_num += 1
        assert len(gen_set) <= 1
        assert len(gen_set) == gen_num
        if gen_num == 0:
            # Generate NoMovementKnowledgeEvent
            dynamics.generate_event(NoMovementKnowledgeEvent(player=self.player, target=self.recorded_target, cause=STALKER))


class Trasformista(Role):
    full_name = 'Trasformista'
    team = POPOLANI
    aura = BLACK
    priority = MODIFY
    frequency = ONCE_A_GAME

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # There are some forbidden roles
        if self.recorded_target.team != POPOLANI and not self.recorded_target.role.ghost:
            return False
        if self.recorded_target.role.frequency in [NEVER, ONCE_A_GAME]:
            return False

        return True

    def apply_dawn(self, dynamics):
        from ..events import TransformationEvent
        new_role_class = self.recorded_target.role.__class__
        if self.recorded_target.role.ghost:
            new_role_class = self.recorded_target.role_class_before_ghost
        assert new_role_class.team == POPOLANI
        dynamics.generate_event(TransformationEvent(player=self.player, target=self.recorded_target, full_role_name=new_role_class.full_name, cause=TRANSFORMIST))
        self.player.just_transformed = True


class Veggente(Role):
    full_name = 'Veggente'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=dynamics.get_apparent_aura(self.recorded_target), cause=SEER))


class Voyeur(Role):
    full_name = 'Voyeur'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import MovementKnowledgeEvent, NoMovementKnowledgeEvent
        gen_set = set()
        gen_num = 0
        for visitor in self.recorded_target.visitors:
            if visitor.pk != self.recorded_target.pk and (visitor.pk != self.player.pk or dynamics.illusion == (self.player, self.recorded_target)):
                dynamics.generate_event(MovementKnowledgeEvent(player=self.player, target=self.recorded_target, target2=visitor, cause=VOYEUR))
                gen_set.add(visitor.pk)
                gen_num += 1
        assert len(gen_set) == gen_num
        if gen_num == 0:
            # Generate NoMovementKnowledgeEvent
            dynamics.generate_event(NoMovementKnowledgeEvent(player=self.player, target=self.recorded_target, cause=VOYEUR))


# Fazione dei Lupi

class Lupo(Role):
    full_name = 'Lupo'
    team = LUPI
    aura = BLACK
    knowledge_class = 1
    priority = KILLER
    frequency = EVERY_NIGHT
    can_act_first_night = False


    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if dynamics.wolves_agree is None:
            dynamics.wolves_agree = dynamics.check_common_target([x for x in dynamics.get_alive_players() if isinstance(x.role, Lupo)])

        if dynamics.wolves_agree:
            # Lupi cannot kill non-Popolani
            if self.recorded_target.team != POPOLANI:
                return False

            # Check protection by Guardia
            if self.recorded_target.protected_by_guard:
                return False

        else:
            # Check if wolves tried to strike, but they didn't agree
            if self.recorded_target is not None:
                return False

        return True

    def apply_dawn(self, dynamics):
        assert dynamics.wolves_agree

        # Assert checks in pre_dawn_apply(), just to be sure
        assert not isinstance(self.recorded_target.role, Negromante)
        assert not self.recorded_target.protected_by_guard

        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from ..events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=WOLVES))

    def post_death(self, dynamics):
        if [player for player in dynamics.get_alive_players() if isinstance(player.role, self.__class__)] == []:
            dynamics.dying_teams += self.team

class Assassino(Role):
    full_name = 'Assassino'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = KILLER
    frequency = EVERY_OTHER_NIGHT
    can_act_first_night = False


    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import PlayerDiesEvent
        assert self.recorded_target is not None
        visitors = [x for x in self.recorded_target.visitors if x.pk != self.player.pk and x.role.recorded_target == self.recorded_target and not x.sequestrated]
        if len(visitors) > 0:
            victim = dynamics.random.choice(visitors)
            if not victim.just_dead:
                assert victim.alive
                dynamics.generate_event(PlayerDiesEvent(player=victim, cause=ASSASSIN))


class Avvocato(Role):
    full_name = 'Avvocato del diavolo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = MODIFY
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()
        def sentence_modification(winner, cause):
            if winner is target:
                return None, ADVOCATE
            return winner, cause

        dynamics.sentence_modifications.append(sentence_modification)


class Diavolo(Role):
    full_name = 'Diavolo'
    team = LUPI
    aura = BLACK
    is_mystic = True
    knowledge_class = 3
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if self.recorded_target.team == NEGROMANTI:
            return False

        return True

    def apply_dawn(self, dynamics):
        from ..events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, full_role_name=dynamics.get_apparent_role(self.recorded_target).full_name, cause=DEVIL))


class Fattucchiera(Role):
    full_name = 'Fattucchiera'
    team = LUPI
    aura = WHITE
    is_mystic = True
    knowledge_class = 3
    priority = QUERY_INFLUENCE + 1 # Must act after Confusione
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()
        assert target.apparent_aura in [BLACK, WHITE]
        target.apparent_aura = WHITE if target.apparent_aura is BLACK else BLACK

class Necrofilo(Role):
    full_name = 'Necrofilo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = MODIFY
    frequency = ONCE_A_GAME

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # There are some forbidden roles
        if self.recorded_target.team != LUPI:
            return False

        return True

    def apply_dawn(self, dynamics):
        from ..events import TransformationEvent, RoleKnowledgeEvent
        new_role_class = self.recorded_target.role.__class__
        assert new_role_class.team == LUPI
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, full_role_name=self.full_name, cause=NECROPHILIAC))
        dynamics.generate_event(TransformationEvent(player=self.player, target=self.recorded_target, full_role_name=new_role_class.full_name, cause=NECROPHILIAC))


class Rinnegato(Role):
    full_name = 'Rinnegato'
    team = LUPI
    aura = WHITE
    knowledge_class = 2
    priority = USELESS

class Sequestratore(Role):
    full_name = 'Sequestratore'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    critical_blocker = True
    sequester = True
    priority = BLOCK
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_blocked(self, players):
        if self.recorded_target is not None:
            return [self.recorded_target.pk]
        else:
            return []

    def apply_dawn(self, dynamics):
        self.recorded_target.sequestrated = True
        pass


class Stregone(Role):
    full_name = 'Stregone'
    team = LUPI
    aura = BLACK
    is_mystic = True
    knowledge_class = 3
    critical_blocker = True
    priority = BLOCK
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        ret = []
        for blocked in players:
            if blocked.pk == self.player.pk:
                continue
            if blocked.role.ghost:
                continue
            if blocked.role.recorded_target is not None and blocked.role.recorded_target.pk == self.recorded_target.pk:
                ret.append(blocked.pk)
        return ret

    def apply_dawn(self, dynamics):
        pass


# Fazione dei Negromanti

class Negromante(Role):
    full_name = 'Negromante'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 4
    priority = MODIFY + 1 # Must act after Messia
    frequency = EVERY_NIGHT

    valid_powers = [AMNESIA, CONFUSIONE, CORRUZIONE, ILLUSIONE, IPNOSI, MORTE, OCCULTAMENTO, VISIONE]

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def get_targets_ghost(self):
        dynamics = self.player.game.get_dynamics()
        powers = set(self.valid_powers)
        available_powers = powers - dynamics.used_ghost_powers
        return list(available_powers)

    def pre_apply_dawn(self, dynamics):
        if dynamics.necromancers_agree is None:
            dynamics.necromancers_agree = dynamics.check_common_target([x for x in dynamics.get_alive_players() if isinstance(x.role, Negromante)], ghosts=True)

        if dynamics.necromancers_agree:
            # Negromanti cannot ghostify people in Lupi team
            if self.recorded_target.team == LUPI:
                return False

            # Negromanti cannot ghostify people in their team
            if self.recorded_target.team == NEGROMANTI and not self.recorded_target.just_ghostified:
                return False

            # Check protection by Custode
            if self.recorded_target.protected_by_keeper:
                return False

            # Check that target has not just been resurrected by
            # Messia
            if self.recorded_target.just_resurrected:
                return False

            # MORTE and CORRUZIONE must be applied on mystic
            if self.recorded_target_ghost in [CORRUZIONE, MORTE] and not self.recorded_target.is_mystic:
                return False

        else:
            # Check if necromancers tried to strike, but they didn't
            # agree
            if self.recorded_target is not None:
                return False

        return True

    def apply_dawn(self, dynamics):
        # Assert checks in pre_dawn_apply(), just to be sure
        assert not isinstance(self.recorded_target.role, (Lupo, Fattucchiera))
        assert self.recorded_target.team != NEGROMANTI or self.recorded_target.just_ghostified
        assert not self.recorded_target.protected_by_keeper

        assert not self.recorded_target.alive
        from ..events import GhostificationEvent, RoleKnowledgeEvent

        if not self.recorded_target.just_ghostified:
            assert not self.recorded_target.role.ghost
            dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_target_ghost, cause=NECROMANCER))
            self.recorded_target.just_ghostified = True

        else:
            # Since GhostificationEvent is not applied during simulation,
            # we must not check the following during simulation
            assert self.recorded_target.role.ghost or dynamics.simulating

        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, full_role_name=Negromante.full_name, cause=GHOST))

    def post_death(self, dynamics):
        if [player for player in dynamics.get_alive_players() if isinstance(player.role, self.__class__)] == []:
            dynamics.dying_teams += self.team


class Fantasma(Role):
    full_name = 'Fantasma'
    team = NEGROMANTI
    aura = BLACK
    priority = USELESS

    valid_powers = [AMNESIA, CONFUSIONE, ILLUSIONE, IPNOSI, OCCULTAMENTO, VISIONE]

    def post_death(self, dynamics):
        available_powers = set(self.valid_powers) - dynamics.used_ghost_powers
        if len(available_powers) >= 1:
            power = dynamics.random.choice(sorted(list(available_powers)))
            from ..events import RoleKnowledgeEvent, GhostificationEvent
            dynamics.generate_event(GhostificationEvent(player=self.player, cause=PHANTOM, ghost=power))
            for negromante in dynamics.players:
                if isinstance(negromante.role, Negromante):
                    dynamics.generate_event(RoleKnowledgeEvent(player=self.player,
                                                               target=negromante,
                                                               full_role_name=Negromante.full_name,
                                                               cause=GHOST))
                    dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                               target=self.player,
                                                               full_role_name=dynamics.roles_list[POWER_NAMES[power]].full_name,
                                                               cause=PHANTOM))
        else:
            from ..events import GhostificationFailedEvent
            dynamics.generate_event(GhostificationFailedEvent(player=self.player))


class Ipnotista(Role):
    full_name = 'Ipnotista'
    team = NEGROMANTI
    aura = WHITE
    knowledge_class = 5
    priority = MODIFY
    frequency = EVERY_OTHER_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_disappearance(self, dynamics):
        # If the player was an Ipnotista, dishypnotize everyone
        # depending on him
        for player in dynamics.players:
            if player.hypnotist is self.player:
                player.hypnotist = None

    def apply_dawn(self, dynamics):
        from ..events import HypnotizationEvent
        dynamics.generate_event(HypnotizationEvent(player=self.recorded_target, hypnotist=self.player))


class Medium(Role):
    full_name = 'Medium'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 5
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from ..events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, full_role_name=dynamics.get_apparent_role(self.recorded_target).full_name, cause=MEDIUM))


class Scrutatore(Role):
    full_name = 'Scrutatore'
    team = NEGROMANTI
    aura = WHITE
    knowledge_class = 5
    priority = MODIFY
    frequency = EVERY_OTHER_NIGHT

    message2 = 'Aggiungi un voto per:'

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()

        def fraud(ballots):
            if target.alive and self.player.alive:
                for voter, voted in ballots.items():
                    if voted == target:
                        ballots[voter] = ballots[self.player.pk]
            return ballots

        dynamics.electoral_frauds.append(fraud)

class Spettro(Role):
    full_name = 'Spettro'
    team = NEGROMANTI
    aura = None
    is_mystic = None
    ghost = True

    def get_power_name(self):
        return self.__class__.__name__
    power_name = property(get_power_name)

    def __init__(self, player):
        Role.__init__(self, player)
        self.has_power = True


class Amnesia(Spettro):
    full_name = 'Spettro dell\'Amnesia'
    priority = MODIFY + 1 # Must act after ipnosi
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_targets2(self):
        return None

    def pre_apply_dawn(self, dynamics):
        return True

    def apply_dawn(self, dynamics):
        assert self.has_power
        target = self.recorded_target.canonicalize()

        def vote_influence(ballots):
            if target.alive:
                ballots[target.pk] = None

            return ballots

        target.temp_dehypnotized = True
        dynamics.vote_influences.append(vote_influence)

class Confusione(Spettro):
    full_name = 'Spettro della Confusione'
    priority = QUERY_INFLUENCE
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def get_targets2(self):
        return self.player.game.get_active_players()

    def pre_apply_dawn(self, dynamics):
        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        target = self.recorded_target.canonicalize()
        target2 = self.recorded_target2.canonicalize()

        target.has_confusion = True
        # Apply to target target2's apparent status
        target.apparent_aura = target2.apparent_aura
        target.apparent_mystic = target2.apparent_mystic
        target.apparent_role = target2.apparent_role
        target.apparent_team = target2.apparent_team


class Corruzione(Spettro):
    full_name = 'Spettro della Corruzione'
    priority = POST_MORTEM
    frequency = ONCE_A_GAME

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_targets2(self):
        return None

    def pre_apply_dawn(self, dynamics):
        if self.recorded_target.aura == BLACK or not self.recorded_target.is_mystic \
                or not self.recorded_target.team == POPOLANI or self.recorded_target.just_dead \
                or self.recorded_target.just_transformed:
            return False

        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        from ..events import CorruptionEvent, RoleKnowledgeEvent
        dynamics.generate_event(CorruptionEvent(player=self.recorded_target))
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, full_role_name=self.full_name, cause=CORRUPTION))

class Illusione(Spettro):
    full_name = 'Spettro dell\'Illusione'
    priority = QUERY_INFLUENCE
    frequency = EVERY_OTHER_NIGHT

    message2 = 'Genera l\'illusione di:'

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def get_targets2(self):
        return self.player.game.get_alive_players()

    def apply_dawn(self, dynamics):
        assert self.has_power

        assert self.recorded_target2.alive

        # Visiting: Stalker illusion, we have to replace the
        # original location
        self.recorded_target2.visiting = [self.recorded_target]

        # Visitors: Voyeur illusion, we have to add to the
        # original list
        if self.recorded_target2 not in self.recorded_target.visitors:
            self.recorded_target.visitors.append(self.recorded_target2)

        dynamics.illusion = (self.recorded_target2, self.recorded_target)

class Ipnosi(Spettro):
    full_name = 'Spettro dell\'Ipnosi'
    priority = MODIFY
    frequency = EVERY_OTHER_NIGHT

    message2 = 'Sposta il voto su:'

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_targets2(self):
        return self.player.game.get_alive_players()

    def apply_dawn(self, dynamics):
        assert self.has_power
        target = self.recorded_target.canonicalize()
        target2 = self.recorded_target2.canonicalize()

        def vote_influence(ballots):
            if target.alive and target2.alive:
                ballots[target.pk] = target2

            return ballots

        target.temp_dehypnotized = True
        dynamics.vote_influences.append(vote_influence)

class Morte(Spettro):
    full_name = 'Spettro della Morte'
    priority = KILLER
    frequency = EVERY_OTHER_NIGHT
    can_act_first_night = False

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):

        if self.recorded_target.team != POPOLANI:
            return False

        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        assert not isinstance(self.recorded_target.role, Lupo)
        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from ..events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=DEATH_GHOST))

class Occultamento(Spettro):
    full_name = 'Spettro dell\'Occultamento'
    critical_blocker = True
    priority = BLOCK
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        # Nothing to do here...
        pass

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        ret = []
        for blocker in players:
            if isinstance(blocker.role, Esorcista):
                continue
            if blocker.pk == self.player.pk:
                continue
            if blocker.role.recorded_target is not None and \
                    blocker.role.recorded_target.pk == self.recorded_target.pk:
                ret.append(blocker.pk)
        return ret

class Visione(Spettro):
    full_name = 'Spettro della Visione'
    priority = QUERY
    frequency = EVERY_NIGHT

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if self.recorded_target.team == LUPI:
            return False

        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        from ..events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, full_role_name=dynamics.get_apparent_role(self.recorded_target).full_name, cause=VISION_GHOST))


'''
ABOUT ORDER
Roles will be applied in the following order, according to
the constant assigned in priority.
Sometimes, in the same group, certain roles must act before
some others; in this case a +1/-1 can be added to anticipate
or delay the application of some roles.

QUERY_INFLUENCE
Powers that influence querying powers: Fattucchiera, Spettro
della Confusione, Spettro dell'Illusione
    * Fattucchiera must act after Confusione

MODIFY_INFLUENCE
Powers that influence modifying powers:
Guardia del Corpo and Custode del Cimitero

QUERY
Powers that query the state: Espansivo, Investigatore, Mago,
Stalker, Veggente, Voyeur, Diavolo, Medium and Spettro della
Visione

MODIFY
Powers that modify the state: Cacciatore, Messia,
Trasformista, Lupi, Assassino, Avvocato del Diavolo, Negromante,
Ipnotista, Spettro dell'Amnesia and Spettro della Morte. The
order is important: in particular, these inequalities have
to be satisfied ("<" means "must act before"):

 * Messia must act before Negromante (resurrection has precedence over
   ghostification)

 * Amnesia must act after Ipnosi (Amnesia will have the last word)

KILLER
Powers that kill (duh):
Lupi, Assassino, Spettro della Morte, Cacciatore

POST_MORTEM
Powers that must act after killers have killed:
Spettro della Corruzione

USELESS
Roles with no power: Contadino, Divinatore, Massone,
Rinnegato, Fantasma.
Will be applied at the end, but seriously, who cares.
'''
