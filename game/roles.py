from django.db import models
from models import KnowsChild, Player
from constants import *

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
        # TODO: check that last_usage and last_target are correctly
        # set and unset
        self.last_usage = None
        self.last_target = None
        self.recorded_target = None
        self.recorded_target2 = None
        self.recorded_target_ghost = None

    def __unicode__(self):
        return u"%s" % self.name
    
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
        if last_usage is None:
            return None
        else:
            return self.player.game.current_turn.date - self.last_usage.date

    def unrecord_targets(self):
        self.recorded_target = None
        self.recorded_target2 = None
        self.recorded_target_ghost = None

    def apply_usepower(self, dynamics, event):
        # First checks
        assert event.player.pk == self.player.pk
        assert self.can_use_power()

        # Check target validity
        targets = self.get_targets()
        if targets is None:
            assert event.target is None
        else:
            assert event.target is None or event.target in targets, (event.target, targets)

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

        # Record targets
        self.recorded_target = event.target
        self.recorded_target2 = event.target2
        self.recorded_target_ghost = event.target_ghost

    def apply_dawn(self, dynamics):
        raise NotImplementedError("Please extend this method in subclasses")

    def get_blocked(self, blockers, ghost):
        raise NotImplementedError("Please extend this method in relevant subclasses")


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
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]


class Custode(Role):
    name = 'Custode del cimitero'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]


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
    
    message = 'Benedici la casa di:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()

    def get_blocked(self, blockers, ghost):
        if ghost is not None and \
                ghost.role.recorded_target is not None and \
                self.recorded_target is not None and \
                self.recorded_target.pk == ghost.role.recorded_target.pk:
            return [ghost.pk]
        else:
            return []


class Espansivo(Role):
    name = 'Espansivo'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if self.recorded_target is not None:
            from events import RoleKnowledgeEvent
            dynamics.generate_event(RoleKnowledgeEvent(player=self.recorded_target, target=self.player, role_name=self.__class__.__name__, cause=EXPANSIVE))


class Guardia(Role):
    name = 'Guardia'
    team = POPOLANI
    aura = WHITE
    
    message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]


class Investigatore(Role):
    name = 'Investigatore'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]

    def apply_dawn(self, dynamics):
        if self.recorded_target is not None:
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
        if self.recorded_target is not None:
            from events import MysticityKnowledgeEvent
            dynamics.generate_event(MysticityKnowledgeEvent(player=self.player, target=self.recorded_target, is_mystic=self.recorded_target.apparent_mystic))


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


class Necrofilo(Role):
    name = 'Necrofilo'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return [player for player in self.player.game.get_dead_players() if player.pk != self.player.pk]


class Stalker(Role):
    name = 'Stalker'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]


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
        if self.recorded_target is not None:
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


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = LUPI
    aura = BLACK
    knowledge_class = 2
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]


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
        if self.recorded_target is not None:
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
        return [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]

    def get_blocked(self, blockers, ghost):
        if ghost is not None and self.recorded_target is not None and ghost.pk == self.recorded_target.pk:
            return [ghost.pk]
        else:
            return []


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
        if self.last_usage is not None and self.days_from_last_usage <= 1:
            excluded.append(self.last_target.pk)
        return [player for player in self.player.game.get_alive_players() if player.pk not in excluded]

    def get_blocked(self, blockers, ghost):
        if self.recorded_target is not None:
            return [self.recorded_target.pk]
        else:
            return []


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


class Spettro(Role):
    name = 'Spettro'
    team = NEGROMANTI
    aura = None
    
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
    
    power = models.CharField(max_length=1, choices=POWERS_LIST)
    has_power = models.BooleanField(default=True)   # Should be set to False when revived by the Messiah
    
    def can_use_power(self):
        return not self.player.alive and self.has_power
    
    def get_targets(self):
        if self.power == AMNESIA:
            excluded = [self.player.pk]
            if self.last_usage is not None and self.days_from_last_usage <= 1:
                excluded.append(self.last_target.pk)
            targets = [player for player in self.player.game.get_alive_players() if player.pk not in excluded]
        elif self.power == DUPLICAZIONE or self.power == ILLUSIONE or self.power == MORTE or self.power == OMBRA or self.power == VISIONE:
            targets = [player for player in self.player.game.get_alive_players() if player.pk != self.player.pk]
        elif self.power == MISTIFICAZIONE or self.power == OCCULTAMENTO:
            targets = [player for player in self.player.game.get_active_players() if player.pk != self.player.pk]
        else:
            raise ValueError('Missing supernatural power.')
        return targets
    
    def get_targets2(self):
        if self.power == ILLUSIONE:
            return self.player.game.get_active_players()
        elif self.power == OMBRA:
            return self.player.game.get_alive_players()
        else:
            return None

    def apply_dawn(self):
        if self.power == MISTIFICAZIONE:
            if self.recorded_target is not None:
                target = self.recorded_target.canonicalize()
                assert target.apparent_mystic is not None
                target.apparent_mystic = True
        else:
            raise NotImplementedError()

    def get_blocked(self, blockers, ghost):
        if self.power == OCCULTAMENTO:
            if self.recorded_target is None:
                return []
            ret = []
            for blocker in blockers:
                if blocker.role.__class__ == Esorcista:
                    continue
                if blocker.pk == self.player.pk:
                    continue
                if blocker.role.recorded_target is not None and \
                        blocker.role.recorded_target.pk == self.recorded_target.pk:
                    ret.append(blocker.pk)
                return ret
        else:
            raise ValueError("Invalid ghost type")

roles_map = dict([(x.__name__, x) for x in Role.__subclasses__()])
