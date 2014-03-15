from models import KnowsChild, Player
from constants import *

import sys

class Role(object):
    name = 'Generic role'
    team = None
    aura = None
    is_mystic = False
    knowledge_class = None
    
    message = 'Usa il tuo potere su:'
    message2 = 'Parametro secondario:'
    message_ghost = 'Potere soprannaturale:'
    
    def __init__(self, player):
        self.player = player
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
            assert event.target2 is None
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

    def apply_dawn(self, dynamics):
        raise NotImplementedError("Please extend this method in subclasses")

    def get_blocked(self, players):
        return []


# Fazione dei Popolani

class Contadino(Role):
    name = 'Contadino'
    team = POPOLANI
    aura = WHITE


class Cacciatore(Role):
    name = 'Cacciatore'
    team = POPOLANI
    aura = BLACK
    
    def can_use_power(self):
        return self.player.alive and self.player.game.current_turn.date > 1 and not self.player.hunter_shooted
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=HUNTER))
            self.player.hunter_shooted = True


class Custode(Role):
    name = 'Custode del cimitero'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        excluded = [self.player.pk]
        if self.last_usage is not None and self.days_from_last_usage() <= 1:
            excluded.append(self.last_target.pk)
        return [player for player in self.player.game.get_dead_players() if player.pk not in excluded]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_keeper = True


class Divinatore(Role):
    name = 'Divinatore'
    team = POPOLANI
    aura = WHITE
    is_mystic = True


class Esorcista(Role):
    name = 'Esorcista'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    # message = 'Benedici la casa di:'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_active_players()

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        ret = []
        for blocker in players:
            if blocker.pk == self.player.pk:
                continue
            if not isinstance(blocker.role, Spettro):
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
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=EXPANSIVE))


class Guardia(Role):
    name = 'Guardia del corpo'
    team = POPOLANI
    aura = WHITE
    
    # message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_guard = True


class Investigatore(Role):
    name = 'Investigatore'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=self.recorded_target.apparent_aura, cause=DETECTIVE))


class Mago(Role):
    name = 'Mago'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import MysticityKnowledgeEvent
        dynamics.generate_event(MysticityKnowledgeEvent(player=self.player, target=self.recorded_target, is_mystic=self.recorded_target.apparent_mystic, cause=MAGE))


class Massone(Role):
    name = 'Massone'
    team = POPOLANI
    aura = WHITE
    knowledge_class = 0


class Messia(Role):
    name = 'Messia'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import PlayerResurrectsEvent
        dynamics.generate_event(PlayerResurrectsEvent(player=self.recorded_target))


class Necrofilo(Role):
    name = 'Necrofilo'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        # There are some forbidden roles
        if isinstance(self.recorded_target.role, (Lupo, Negromante, Fantasma)):
            return False
        if isinstance(self.recorded_target.role, tuple(UNA_TANTUM_ROLES)):
            return False
        if isinstance(self.recorded_target.role, tuple(POWERLESS_ROLES)):
            return False

        return True

    def apply_dawn(self, dynamics):
        from events import NecrofilizationEvent
        new_role_class = self.recorded_target.role.__class__
        if isinstance(self.recorded_target.role, Spettro):
            new_role_class = self.recorded_target.role_class_before_ghost
        dynamics.generate_event(NecrofilizationEvent(player=self.player, target=self.recorded_target, role_name=new_role_class.__name__))


class Stalker(Role):
    name = 'Stalker'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import MovementKnowledgeEvent
        gen_set = set()
        gen_num = 0
        for visiting in self.recorded_target.visiting:
            if visiting.pk != self.recorded_target.pk:
                dynamics.generate_event(MovementKnowledgeEvent(player=self.player, target=self.recorded_target, target2=visiting, cause=STALKER))
                gen_set.add(visiting.pk)
                gen_num += 1
        assert len(gen_set) <= 1
        assert len(gen_set) == gen_num


class Veggente(Role):
    name = 'Veggente'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import AuraKnowledgeEvent
        dynamics.generate_event(AuraKnowledgeEvent(player=self.player, target=self.recorded_target, aura=self.recorded_target.apparent_aura, cause=SEER))


class Voyeur(Role):
    name = 'Voyeur'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import MovementKnowledgeEvent
        gen_set = set()
        gen_num = 0
        for visitor in self.recorded_target.visitors:
            if visitor.pk != self.recorded_target.pk and visitor.pk != self.player.pk:
                dynamics.generate_event(MovementKnowledgeEvent(player=self.player, target=self.recorded_target, target2=visitor, cause=VOYEUR))
                gen_set.add(visitor.pk)
                gen_num += 1
        assert len(gen_set) == gen_num


# Fazione dei Lupi

class Lupo(Role):
    name = 'Lupo'
    team = LUPI
    aura = BLACK
    knowledge_class = 1
    
    def can_use_power(self):
        return self.player.alive and self.player.game.current_turn.date > 1
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def pre_apply_dawn(self, dynamics):
        if dynamics.wolves_target is not None:
            assert self.recorded_target.pk == dynamics.wolves_target.pk

            # Lupi cannot kill Negromanti
            if isinstance(self.recorded_target.role, Negromante):
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
                from events import PlayerDiesEvent
                dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=WOLVES))

        else:
            assert self.recorded_target is None


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    
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
    knowledge_class = 2
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, role_name=self.recorded_target.role.__class__.__name__, cause=DEVIL))


class Fattucchiera(Role):
    name = 'Fattucchiera'
    team = LUPI
    aura = BLACK
    is_mystic = True
    knowledge_class = 1
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()
        assert target.apparent_aura in [BLACK, WHITE]
        target.apparent_aura = WHITE if target.apparent_aura is BLACK else BLACK


class Profanatore(Role):
    name = 'Profanatore di Tombe'
    team = LUPI
    aura = BLACK
    knowledge_class = 3

    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )

    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def get_blocked(self, players):
        if self.recorded_target is None:
            return []
        if isinstance(self.recorded_target.role, Spettro):
            return [self.recorded_target.pk]
        else:
            return []

    def apply_dawn(self, dynamics):
        # Nothing to do here...
        pass


class Rinnegato(Role):
    name = 'Rinnegato'
    team = LUPI
    aura = WHITE
    knowledge_class = 3


class Sequestratore(Role):
    name = 'Sequestratore'
    team = LUPI
    aura = BLACK
    knowledge_class = 3
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        excluded = [self.player.pk]
        if self.last_usage is not None and self.days_from_last_usage() <= 1:
            excluded.append(self.last_target.pk)
        return [player for player in self.player.game.get_alive_players() if player.pk not in excluded]

    def get_blocked(self, players):
        if self.recorded_target is not None:
            return [self.recorded_target.pk]
        else:
            return []

    def apply_dawn(self, dynamics):
        # Nothing to do here...
        pass


# Fazione dei Negromanti

class Negromante(Role):
    name = 'Negromante'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 4
    
    def can_use_power(self):
        dynamics = self.player.game.get_dynamics()
        if dynamics.death_ghost_created:
            return False
        if dynamics.ghosts_created_last_night:
            return False
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]
    
    def get_targets_ghost(self):
        dynamics = self.player.game.get_dynamics()
        powers = set(Spettro.POWER_NAMES.keys())
        available_powers = powers - dynamics.used_ghost_powers
        return list(available_powers)

    def pre_apply_dawn(self, dynamics):
        if dynamics.necromancers_target is not None:
            necromancers_target_player, necromancers_target_ghost = dynamics.necromancers_target
            assert self.recorded_target.pk == necromancers_target_player.pk
            assert self.recorded_target_ghost == necromancers_target_ghost

            # Negromanti cannot ghostify Lupi and Fattucchiere
            if isinstance(self.recorded_target.role, (Lupo, Fattucchiera)):
                return False

            # Negromanti cannot ghostify people in their team
            if self.recorded_target.team == NEGROMANTI:
                return False

            # Check protection by Custode
            if self.recorded_target.protected_by_keeper:
                return False

            # Check that target has not just been resurrected by
            # Messia
            if self.recorded_target.alive:
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
            assert self.recorded_target.team != NEGROMANTI
            assert not self.recorded_target.protected_by_keeper

            assert not self.recorded_target.alive
            from events import GhostificationEvent, RoleKnowledgeEvent

            if not self.recorded_target.just_ghostified:
                assert not isinstance(self.recorded_target.role, Spettro)
                dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_target_ghost, cause=NECROMANCER))
                self.recorded_target.just_ghostified = True

            else:
                assert isinstance(self.recorded_target.role, Spettro)

            dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=Negromante.__name__, cause=GHOST))

        else:
            assert self.recorded_target is None


class Fantasma(Role):
    name = 'Fantasma'
    team = NEGROMANTI
    aura = WHITE


class Ipnotista(Role):
    name = 'Ipnotista'
    team = NEGROMANTI
    aura = WHITE
    knowledge_class = 5
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import HypnotizationEvent
        dynamics.generate_event(HypnotizationEvent(player=self.recorded_target, hypnotist=self.player))


class Medium(Role):
    name = 'Medium'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    knowledge_class = 5
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        from events import MediumKnowledgeEvent
        dynamics.generate_event(MediumKnowledgeEvent(player=self.player,
                                                     target=self.recorded_target,
                                                     aura=self.recorded_target.apparent_aura,
                                                     is_ghost=isinstance(self.recorded_target.role, Spettro),
                                                     cause=MEDIUM))


class Spettro(Role):
    name = 'Spettro'
    team = NEGROMANTI
    aura = None
    is_mystic = None
    
    message2 = 'Genera l\'illusione di:'
    
    POWER_NAMES = {
        AMNESIA: 'Amnesia',
        DUPLICAZIONE: 'Duplicazione',
        ILLUSIONE: 'Illusione',
        MISTIFICAZIONE: 'Mistificazione',
        MORTE: 'Morte',
        OCCULTAMENTO: 'Occultamento',
        VISIONE: 'Visione',
    }
    
    POWERS_LIST = POWER_NAMES.items()

    def __init__(self, player, power):
        Role.__init__(self, player)
        self.power = power
        self.has_power = True

    def can_use_power(self):
        if self.player.alive or not self.has_power:
            return False
        
        if self.power == AMNESIA or self.power == DUPLICAZIONE or self.power == MISTIFICAZIONE or self.power == OCCULTAMENTO or self.power == VISIONE:
            return True
        elif self.power == ILLUSIONE or self.power == MORTE:
            return self.last_usage is None or self.days_from_last_usage() >= 2
        else:
            raise ValueError('Invalid ghost type')
    
    def get_targets(self):
        if self.power == AMNESIA:
            excluded = [self.player.pk]
            if self.last_usage is not None and self.days_from_last_usage() <= 1:
                excluded.append(self.last_target.pk)
            targets = [player for player in self.player.game.get_alive_players() if player.pk not in excluded]
        elif self.power == DUPLICAZIONE or self.power == MORTE or self.power == VISIONE:
            targets = [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]
        elif self.power == MISTIFICAZIONE or self.power == OCCULTAMENTO or self.power == ILLUSIONE:
            targets = [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]
        else:
            raise ValueError('Invalid ghost type')
        return targets
    
    def get_targets2(self):
        if self.power == ILLUSIONE:
            return self.player.game.get_alive_players()
        else:
            return None

    def pre_apply_dawn(self, dynamics):
        if self.power == AMNESIA:
            if isinstance(self.recorded_target.role, Ipnotista):
                return False

        elif self.power == MORTE:
            if isinstance(self.recorded_target.role, Lupo):
                return False

        return True

    def apply_dawn(self, dynamics):
        assert self.has_power

        if self.power == MISTIFICAZIONE:
            target = self.recorded_target.canonicalize()
            assert target.apparent_mystic is not None
            target.apparent_mystic = True

        elif self.power == VISIONE:
            from events import TeamKnowledgeEvent
            dynamics.generate_event(TeamKnowledgeEvent(player=self.player, target=self.recorded_target, team=self.recorded_target.team, cause=VISION_GHOST))

        elif self.power == AMNESIA:
            assert dynamics.amnesia_target is None
            assert not isinstance(self.recorded_target.role, Ipnotista)
            dynamics.amnesia_target = self.recorded_target.canonicalize()

        elif self.power == DUPLICAZIONE:
            assert dynamics.duplication_target is None
            dynamics.duplication_target = self.recorded_target.canonicalize()

        elif self.power == OCCULTAMENTO:
            # Nothing to do here...
            pass

        elif self.power == ILLUSIONE:
            assert self.recorded_target2.alive

            # Visiting: Stalker illusion, we have to replace the
            # original location
            self.recorded_target2.visiting = [self.recorded_target]

            # Visitors: Voyeur illusion, we have to add to the
            # original list
            if self.recorded_target2 not in self.recorded_target.visitors:
                self.recorded_target.visitors.append(self.recorded_target2)

        elif self.power == MORTE:
            assert not isinstance(self.recorded_target.role, Lupo)
            if not self.recorded_target.just_dead:
                assert self.recorded_target.alive
                from events import PlayerDiesEvent
                dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=DEATH_GHOST))

        else:
            raise ValueError("Invalid ghost type")

    def get_blocked(self, players):
        if self.power == OCCULTAMENTO:
            if self.recorded_target is None:
                return []
            ret = []
            for blocker in players:
                if blocker.role.__class__ == Esorcista:
                    continue
                if blocker.pk == self.player.pk:
                    continue
                if blocker.role.recorded_target is not None and \
                        blocker.role.recorded_target.pk == self.recorded_target.pk:
                    ret.append(blocker.pk)
            return ret
        else:
            return []

roles_map = dict([(x.__name__, x) for x in Role.__subclasses__()])

UNA_TANTUM_ROLES = [Cacciatore, Messia, Necrofilo]
POWERLESS_ROLES = [Contadino, Divinatore, Massone, Rinnegato, Fantasma]
