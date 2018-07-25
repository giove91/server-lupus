from ..models import KnowsChild, Player
from ..constants import *

import sys

class Role(object):
    name = 'Generic role'
    team = None
    aura = None
    is_mystic = False
    ghost = False
    priority = None            # Priority of actions. Lower values act before
    critical_blocker = False   # Power that blocks powers that block powers
    sequester = False          # When True, blocked roles will not be seen moving
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
    
    def can_use_power(self):
        return False
    
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
        """To be called just after this role dies.

        """

    def apply_dawn(self, dynamics):
        raise NotImplementedError("Please extend this method in subclasses")

    def get_blocked(self, players):
        return []


# Fazione dei Popolani

class Contadino(Role):
    name = 'Contadino'
    team = POPOLANI
    aura = WHITE
    priority = USELESS

class Cacciatore(Role):
    name = 'Cacciatore'
    team = POPOLANI
    aura = BLACK
    priority = KILLER
    
    def can_use_power(self):
        return self.player.alive and self.player.game.current_turn.full_days_from_start() > 0 and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from .events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=HUNTER))


class Custode(Role):
    name = 'Custode del cimitero'
    team = POPOLANI
    aura = WHITE
    priority = MODIFY_INFLUENCE

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_keeper = True
        visitors = [visitor for visitor in self.recorded_target.visitors if visitor.pk not in [self.player.pk, self.recorded_target.pk] or dynamics.illusion == (self.player, self.recorded_target)]
        from .events import QuantitativeMovementKnowledgeEvent
        dynamics.generate_event(QuantitativeMovementKnowledgeEvent(player=self.player, target=self.recorded_target, visitors=len(visitors), cause=KEEPER))

class Divinatore(Role):
    name = 'Divinatore'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = USELESS

class Esorcista(Role):
    name = 'Esorcista'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    critical_blocker = True
    priority = BLOCK

    # message = 'Benedici la casa di:'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
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
    name = 'Espansivo'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=EXPANSIVE))


class Guardia(Role):
    name = 'Guardia del corpo'
    team = POPOLANI
    aura = WHITE
    priority = MODIFY_INFLUENCE
    
    # message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_guard = True
        visitors = [visitor for visitor in self.recorded_target.visitors if visitor.pk not in [self.player.pk, self.recorded_target.pk] or dynamics.illusion == (self.player, self.recorded_target)]
        from .events import QuantitativeMovementKnowledgeEvent
        dynamics.generate_event(QuantitativeMovementKnowledgeEvent(player=self.player, target=self.recorded_target,visitors=len(visitors), cause=GUARD))


class Investigatore(Role):
    name = 'Investigatore'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=dynamics.get_apparent_aura(self.recorded_target), cause=DETECTIVE))


class Mago(Role):
    name = 'Mago'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import MysticityKnowledgeEvent
        dynamics.generate_event(MysticityKnowledgeEvent(player=self.player, target=self.recorded_target, is_mystic=dynamics.get_apparent_mystic(self.recorded_target), cause=MAGE))


class Massone(Role):
    name = 'Massone'
    team = POPOLANI
    aura = WHITE
    knowledge_class = 0
    priority = USELESS

class Messia(Role):
    name = 'Messia'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = MODIFY
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
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
            from .events import PlayerResurrectsEvent
            dynamics.generate_event(PlayerResurrectsEvent(player=self.recorded_target))


class Sciamano(Role):
    name = 'Sciamano'
    team = POPOLANI
    aura = BLACK
    is_mystic = True
    critical_blocker = True
    priority = BLOCK

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )

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
    name = 'Stalker'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import MovementKnowledgeEvent, NoMovementKnowledgeEvent
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
    name = 'Trasformista'
    team = POPOLANI
    aura = BLACK
    priority = MODIFY

    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # There are some forbidden roles
        if self.recorded_target.team != POPOLANI and not self.recorded_target.role.ghost:
            return False
        if isinstance(self.recorded_target.role, tuple(UNA_TANTUM_ROLES)):
            return False
        if isinstance(self.recorded_target.role, tuple(POWERLESS_ROLES)):
            return False

        return True

    def apply_dawn(self, dynamics):
        from .events import TransformationEvent
        new_role_class = self.recorded_target.role.__class__
        if self.recorded_target.role.ghost:
            new_role_class = self.recorded_target.role_class_before_ghost
        assert new_role_class.team == POPOLANI
        dynamics.generate_event(TransformationEvent(player=self.player, target=self.recorded_target, role_name=new_role_class.__name__, cause=TRANSFORMIST))
        self.player.just_transformed = True


class Veggente(Role):
    name = 'Veggente'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    priority = QUERY

    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=dynamics.get_apparent_aura(self.recorded_target), cause=SEER))


class Voyeur(Role):
    name = 'Voyeur'
    team = POPOLANI
    aura = WHITE
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import MovementKnowledgeEvent, NoMovementKnowledgeEvent
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
    name = 'Lupo'
    team = LUPI
    aura = BLACK
    knowledge_class = 1
    priority = KILLER

    def can_use_power(self):
        return self.player.alive and self.player.game.current_turn.full_days_from_start() > 0
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if dynamics.wolves_target is not None:
            assert self.recorded_target.pk == dynamics.wolves_target.pk

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
        if dynamics.wolves_target is not None:
            assert self.recorded_target.pk == dynamics.wolves_target.pk

            # Assert checks in pre_dawn_apply(), just to be sure
            assert not isinstance(self.recorded_target.role, Negromante)
            assert not self.recorded_target.protected_by_guard

            if not self.recorded_target.just_dead:
                assert self.recorded_target.alive
                from .events import PlayerDiesEvent
                dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=WOLVES))

        else:
            assert self.recorded_target is None

    def post_death(self, dynamics):
        if [player for player in dynamics.get_alive_players() if isinstance(player.role, self.__class__)] == []:
            dynamics.dying_teams += self.team

class Assassino(Role):
    name = 'Assassino'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = KILLER

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 ) and self.player.game.current_turn.full_days_from_start() > 0
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]
    
    def apply_dawn(self, dynamics):
        from .events import PlayerDiesEvent
        assert self.recorded_target is not None
        visitors = [x for x in self.recorded_target.visitors if x.pk != self.player.pk and x.role.recorded_target == self.recorded_target and not x.sequestrated]
        if len(visitors) > 0:
            victim = dynamics.random.choice(visitors)
            if not victim.just_dead:
                assert victim.alive
                dynamics.generate_event(PlayerDiesEvent(player=victim, cause=ASSASSIN))
        


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = MODIFY
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if self.recorded_target not in dynamics.advocated_players:
            dynamics.advocated_players.append(self.recorded_target)


class Diavolo(Role):
    name = 'Diavolo'
    team = LUPI
    aura = BLACK
    is_mystic = True
    knowledge_class = 3
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if self.recorded_target.team == NEGROMANTI:
            return False

        return True

    def apply_dawn(self, dynamics):
        from .events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, role_name=dynamics.get_apparent_role(self.recorded_target).__name__, cause=DEVIL))


class Fattucchiera(Role):
    name = 'Fattucchiera'
    team = LUPI
    aura = WHITE
    is_mystic = True
    knowledge_class = 3
    priority = QUERY_INFLUENCE + 1 # Must act after Confusione
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()
        assert target.apparent_aura in [BLACK, WHITE]
        target.apparent_aura = WHITE if target.apparent_aura is BLACK else BLACK

class Necrofilo(Role):
    name = 'Necrofilo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    priority = MODIFY
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # There are some forbidden roles
        if self.recorded_target.team != LUPI:
            return False

        return True

    def apply_dawn(self, dynamics):
        from .events import TransformationEvent, RoleKnowledgeEvent
        new_role_class = self.recorded_target.role.__class__
        assert new_role_class.team == LUPI
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=NECROPHILIAC))
        dynamics.generate_event(TransformationEvent(player=self.player, target=self.recorded_target, role_name=new_role_class.__name__, cause=NECROPHILIAC))


class Rinnegato(Role):
    name = 'Rinnegato'
    team = LUPI
    aura = WHITE
    knowledge_class = 2
    priority = USELESS

class Sequestratore(Role):
    name = 'Sequestratore'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    critical_blocker = True
    sequester = True
    priority = BLOCK
    
    def can_use_power(self):
        return self.player.alive
    
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
    name = 'Stregone'
    team = LUPI
    aura = BLACK
    is_mystic = True
    knowledge_class = 3
    critical_blocker = True
    priority = BLOCK

    def can_use_power(self):
        return self.player.alive
    
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
    name = 'Negromante'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 4
    priority = MODIFY

    valid_powers = [Amnesia, Confusione, Corruzione, Illusione, Ipnosi, Morte, Occultamento, Visione]

    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]
    
    def get_targets_ghost(self):
        dynamics = self.player.game.get_dynamics()
        powers = set(self.valid_powers)
        available_powers = powers - dynamics.used_ghost_powers
        return list(available_powers)

    def pre_apply_dawn(self, dynamics):
        if dynamics.necromancers_target is not None:
            necromancers_target_player, necromancers_target_ghost = dynamics.necromancers_target
            assert self.recorded_target.pk == necromancers_target_player.pk
            assert self.recorded_target_ghost == necromancers_target_ghost

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
        if dynamics.necromancers_target is not None:
            necromancers_target_player, necromancers_target_ghost = dynamics.necromancers_target
            assert self.recorded_target.pk == necromancers_target_player.pk
            assert self.recorded_target_ghost == necromancers_target_ghost

            # Assert checks in pre_dawn_apply(), just to be sure
            assert not isinstance(self.recorded_target.role, (Lupo, Fattucchiera))
            assert self.recorded_target.team != NEGROMANTI or self.recorded_target.just_ghostified
            assert not self.recorded_target.protected_by_keeper

            assert not self.recorded_target.alive
            from .events import GhostificationEvent, RoleKnowledgeEvent

            if not self.recorded_target.just_ghostified:
                assert not isinstance(self.recorded_target.role, Spettro)
                dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_target_ghost, cause=NECROMANCER))
                self.recorded_target.just_ghostified = True

            else:
                # Since GhostificationEvent is not applied during simulation,
                # we must not check the following during simulation
                assert isinstance(self.recorded_target.role, Spettro) or dynamics.simulating

            dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=Negromante.__name__, cause=GHOST))

        else:
            assert self.recorded_target is None

    def post_death(self, dynamics):
        if [player for player in dynamics.get_alive_players() if isinstance(player.role, self.__class__)] == []:
            dynamics.dying_teams += self.team


class Fantasma(Role):
    name = 'Fantasma'
    team = NEGROMANTI
    aura = BLACK
    priority = USELESS

    def post_death(self, dynamics):
        powers = set([role for role in dynamics.roles_list if role.ghost])
        available_powers = powers - dynamics.used_ghost_powers - set([Morte, Corruzione])
        if len(available_powers) >= 1:
            power = dynamics.random.choice(sorted(list(available_powers)))
            dynamics.generate_event(GhostificationEvent(player=player, cause=PHANTOM, ghost=power))
            for negromante in dynamics.players:
                if isinstance(negromante.role, Negromante):
                    dynamics.generate_event(RoleKnowledgeEvent(player=player,
                                                               target=negromante,
                                                               role_name='Negromante',
                                                               cause=GHOST))
                    dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                               target=player,
                                                               role_name=power.__class__.__name__,
                                                               cause=PHANTOM))
        else:
            dynamics.generate_event(GhostificationFailedEvent(player=player))
        

class Ipnotista(Role):
    name = 'Ipnotista'
    team = NEGROMANTI
    aura = WHITE
    knowledge_class = 5
    priority = MODIFY

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_disappearance(self, dynamics):
        # If the player was an Ipnotista, dishypnotize everyone
        # depending on him
        for player in dynamics.players:
            if player.hypnotist is self.player:
                player.hypnotist = None

    def apply_dawn(self, dynamics):
        from .events import HypnotizationEvent
        dynamics.generate_event(HypnotizationEvent(player=self.recorded_target, hypnotist=self.player))


class Medium(Role):
    name = 'Medium'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 5
    priority = QUERY
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from .events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, role_name=dynamics.get_apparent_role(self.recorded_target).__name__, cause=MEDIUM))


class Scrutatore(Role):
    name = 'Scrutatore'
    team = NEGROMANTI
    aura = WHITE
    knowledge_class = 5
    priority = MODIFY

    message2 = 'Aggiungi un voto per:'

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        dynamics.redirected_ballots.append((self.recorded_target, self.player))


class Spettro(Role):
    name = 'Spettro'
    team = NEGROMANTI
    aura = None
    is_mystic = None

    @property
    def message2(self):
        if self.power == ILLUSIONE:
            return 'Genera l\'illusione di:'
        elif self.power == IPNOSI:
            return 'Sposta il voto su:'
        else:
            raise ValueError('Invalid ghost type')
    
    POWER_NAMES = {
        AMNESIA: 'Amnesia',
        CONFUSIONE: 'Confusione',
        CORRUZIONE: 'Corruzione',
        ILLUSIONE: 'Illusione',
        IPNOSI: 'Ipnosi',
        MORTE: 'Morte',
        OCCULTAMENTO: 'Occultamento',
        VISIONE: 'Visione'
    }
    
    POWERS_LIST = POWER_NAMES.items()
    
    def get_power_name(self):
        return self.POWER_NAMES[self.power]
    power_name = property(get_power_name)

    def __init__(self, player, power):
        Role.__init__(self, player)
        self.power = power
        self.has_power = True

    def can_use_power(self):
        if self.player.alive or not self.has_power:
            return False

        if self.power == AMNESIA or self.power == CONFUSIONE or self.power == OCCULTAMENTO or self.power == VISIONE:
            return True
        elif self.power == ILLUSIONE or self.power == MORTE or self.power == IPNOSI:
            return self.last_usage is None or self.days_from_last_usage() >= 2
        elif self.power == CORRUZIONE:
            return self.last_usage is None
        else:
            raise ValueError('Invalid ghost type')

    def get_targets(self):
        if self.power == AMNESIA or self.power == MORTE or self.power == VISIONE or self.power == IPNOSI or self.power == CORRUZIONE:
            targets = [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]
        elif self.power == CONFUSIONE or self.power == OCCULTAMENTO or self.power == ILLUSIONE:
            targets = [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]
        else:
            raise ValueError('Invalid ghost type')
        return targets
    
    def get_targets2(self):
        if self.power == ILLUSIONE or self.power == IPNOSI:
            return self.player.game.get_alive_players()
        elif self.power == CONFUSIONE:
            return self.player.game.get_active_players()
        else:
            return None

    def pre_apply_dawn(self, dynamics):

        if self.power == MORTE:
            if self.recorded_target.team != POPOLANI:
                return False

        elif self.power == CORRUZIONE:
            if self.recorded_target.aura == BLACK or not self.recorded_target.is_mystic \
                    or not self.recorded_target.team == POPOLANI or self.recorded_target.just_dead \
                    or self.recorded_target.just_transformed:
                return False

        elif self.power == VISIONE:
            if self.recorded_target.team == LUPI:
                return False

        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        if self.power == VISIONE:
            from .events import RoleKnowledgeEvent
            dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, role_name=dynamics.get_apparent_role(self.recorded_target).__name__, cause=VISION_GHOST))

        elif self.power == AMNESIA:
            assert dynamics.amnesia_target is None
            dynamics.amnesia_target = self.recorded_target.canonicalize()
        
        
        elif self.power == OCCULTAMENTO:
            # Nothing to do here...
            pass
            
        elif self.power == CONFUSIONE:
            target = self.recorded_target.canonicalize()
            target2 = self.recorded_target2.canonicalize()

            target.has_confusion = True
            # Apply to target target2's apparent status
            target.apparent_aura = target2.apparent_aura
            target.apparent_mystic = target2.apparent_mystic
            target.apparent_role = target2.apparent_role
            target.apparent_team = target2.apparent_team

        elif self.power == ILLUSIONE:
            assert self.recorded_target2.alive

            # Visiting: Stalker illusion, we have to replace the
            # original location
            self.recorded_target2.visiting = [self.recorded_target]

            # Visitors: Voyeur illusion, we have to add to the
            # original list
            if self.recorded_target2 not in self.recorded_target.visitors:
                self.recorded_target.visitors.append(self.recorded_target2)

            dynamics.illusion = (self.recorded_target2, self.recorded_target)

        elif self.power == MORTE:
            assert not isinstance(self.recorded_target.role, Lupo)
            if not self.recorded_target.just_dead:
                assert self.recorded_target.alive
                from .events import PlayerDiesEvent
                dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=DEATH_GHOST))

        elif self.power == IPNOSI:
            assert dynamics.hypnosis_ghost_target is None
            dynamics.hypnosis_ghost_target = (self.recorded_target, self.recorded_target2)

        elif self.power == CORRUZIONE:
            from .events import CorruptionEvent, RoleKnowledgeEvent
            dynamics.generate_event(CorruptionEvent(player=self.recorded_target))
            dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=CORRUPTION))

        else:
            raise ValueError("Invalid ghost type")

    def get_blocked(self, players):
        if self.power == OCCULTAMENTO:
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
        else:
            return []

class Amnesia(Role):
    name = 'Spettro'
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

    def can_use_power(self):
        return not self.player.alive and self.has_power

    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]
 
    def get_targets2(self):
        return None

    def pre_apply_dawn(self, dynamics):
        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        assert dynamics.amnesia_target is None
        dynamics.amnesia_target = self.recorded_target.canonicalize()

class Confusione(Role):
    name = 'Spettro'
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

    def can_use_power(self):
        if self.player.alive or not self.has_power:
            return False

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


class Corruzione(Role):
    name = 'Spettro'
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

    def can_use_power(self):
        if self.player.alive or not self.has_power:
            return False

        return self.last_usage is None

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

        from .events import CorruptionEvent, RoleKnowledgeEvent
        dynamics.generate_event(CorruptionEvent(player=self.recorded_target))
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=CORRUPTION))



UNA_TANTUM_ROLES = [Cacciatore, Messia, Trasformista]
POWERLESS_ROLES = [Contadino, Divinatore, Massone, Rinnegato, Fantasma]
valid_roles = [Cacciatore, Contadino, Divinatore, Esorcista, Espansivo, Guardia, Investigatore, Mago, Massone, Messia, Sciamano, Stalker, Trasformista, Veggente, Voyeur, Lupo, Assassino, Avvocato, Diavolo, Fattucchiera, Rinnegato, Sequestratore, Stregone, Negromante, Fantasma, Ipnotista, Medium, Scrutatore, Spettro]
roles_list = dict([(x.__name__, x) for x in valid_roles])


# ABOUT ORDER
# Powers that influence querying powers: Fattucchiera, Spettro
# della Confusione, Spettro dell'Illusione
#
# Fattucchiera must act after Confusione

# Then powers that influence modifying powers: Guardia del
# Corpo and Custode del Cimitero

# Powers that query the state: Espansivo, Investigatore, Mago,
# Stalker, Veggente, Voyeur, Diavolo, Medium and Spettro della
# Visione

# Powers that modify the state: Cacciatore, Messia,
# Trasformista, Lupi, Assassino, Avvocato del Diavolo, Negromante,
# Ipnotista, Spettro dell'Amnesia and Spettro della Morte. The
# order is important: in particular, these inequalities have
# to be satisfied ("<" means "must act before"):
#
#  * Messia < Negromante (resurrection has precedence over
#    ghostification)
#
#  * anything < Cacciatore, Lupo, Assassino, MORTE (deaths happen at the
#    and of the turn) except CORRUZIONE

# Roles with no power: Contadino, Divinatore, Massone,
# Rinnegato, Fantasma.

