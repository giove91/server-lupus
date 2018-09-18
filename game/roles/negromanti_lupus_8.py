from .base import *
from ..constants import *

# Define variable used for the game

starting_teams = [POPOLANI, LUPI, NEGROMANTI]

class Divinatore(Divinatore):
    frequency = EVERY_OTHER_NIGHT
    priority = QUERY

    def get_targets(self):
        return {player for player in self.player.game.get_alive_players() if player.pk != self.player.pk}

    def get_targets_role_name(self):
        return {x.name for x in self.player.game.get_dynamics().rules.valid_roles if not x.ghost}

    def apply_dawn(self, dynamics):
        if dynamics.get_apparent_role(self.recorded_target).name == self.recorded_target_role_name:
            from ..events import RoleKnowledgeEvent
            dynamics.generate_event(RoleKnowledgeEvent(target=self.recorded_target, player=self.player, role_name=self.recorded_target_role_name, cause=SOOTHSAYER))
        else:
            from ..events import NegativeRoleKnowledgeEvent
            dynamics.generate_event(NegativeRoleKnowledgeEvent(target=self.recorded_target, player=self.player, role_name=self.recorded_target_role_name, cause=SOOTHSAYER))

    def needs_soothsayer_propositions(self):
        from ..events import SoothsayerModelEvent
        events = SoothsayerModelEvent.objects.filter(soothsayer=self.player)
        if len([ev for ev in events if ev.target == ev.soothsayer]) > 0:
            return KNOWS_ABOUT_SELF
        if len(events) != 4:
            return NUMBER_MISMATCH
        truths = [ev.target.canonicalize().role.name == ev.advertised_role for ev in events]
        if not (False in truths) or not (True in truths):
            return TRUTH_MISMATCH

        return False

class Lupo(Lupo):
    # Lupi can kill everybody! Yay!
    def pre_apply_dawn(self, dynamics):
        if dynamics.wolves_agree is None:
            dynamics.wolves_agree = dynamics.check_common_target([x for x in dynamics.get_alive_players() if isinstance(x.role, Lupo)])

        if dynamics.wolves_agree:
            # Check protection by Guardia
            if self.recorded_target.protected_by_guard:
                return False

        else:
            # Check if wolves tried to strike, but they didn't agree
            if self.recorded_target is not None:
                return False

        return True



class Alcolista(Rinnegato):
    name = 'Alcolista'
    frequency = EVERY_NIGHT
    priority = QUERY_INFLUENCE # Mah

    def get_targets(self):
        return {player for player in self.player.game.get_active_players() if player.pk != self.player.pk}

    def pre_apply_dawn(self, dynamics):
        return False # Lol

    def apply_dawn(self, dynamics):
        pass #out

class Diavolo(Diavolo):
    def get_targets_role_bisection(self):
        return {x.name for x in self.player.game.get_dynamics().rules.valid_roles if not x.ghost}

    def pre_apply_dawn(self, dynamics):
        # Will not fail on Negromenti
        return True

    def apply_dawn(self, dynamics):
        from ..events import RoleBisectionKnowledgeEvent
        dynamics.generate_event(RoleBisectionKnowledgeEvent(
                player=self.player,
                target=self.recorded_target,
                role_bisection=self.recorded_target_role_bisection,
                response=dynamics.get_apparent_role(self.recorded_target).name in self.recorded_target_role_bisection,
                cause=DEVIL
        ))

class Fattucchiera(Fattucchiera):
    def get_targets(self):
        return {player for player in self.player.game.get_active_players() if player.pk != self.player.pk}

    def get_targets_role_name(self):
        return {x.name for x in self.player.game.get_dynamics().rules.valid_roles if not x.ghost}

    def apply_dawn(self, dynamics):
        role = dynamics.rules.roles_list[self.recorded_target_role_name]
        target = self.recorded_target.canonicalize()
        target.apparent_aura = role.aura
        target.apparent_mystic = role.is_mystic
        target.apparent_role = role
        target.apparent_team = role.team


class Negromante(Negromante):
    priority = MODIFY
    has_power = True

    def can_use_power(self):
        if not self.player.alive:
            return self.has_power

        return True

    def get_targets_role_name(self):
        valid_powers = {Amnesia, Confusione, Illusione, Morte, Occultamento, Visione}
        dynamics = self.player.game.get_dynamics()
        powers = {x.name for x in valid_powers}
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def pre_apply_dawn(self, dynamics):
        if self.player.alive:
            return self.recorded_target.role.ghost
        else:
            return True

    def apply_dawn(self, dynamics):
        if self.recorded_target.role.ghost:
            from ..events import GhostSwitchEvent
            dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=self.recorded_target_role_name, cause=NECROMANCER))
        else:
            assert not self.player.alive
            from ..events import GhostificationEvent
            dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_target_role_name, cause=NECROMANCER))

        if not self.player.alive:
            self.has_power = False

class Delusione(Spettro):
    # Spettro yet to be initialized (or who has lost his power).
    frequency = NEVER
    priority = USELESS

class Amnesia(Amnesia):
    frequency = EVERY_OTHER_NIGHT
    priority = MODIFY

    def apply_dawn(self, dynamics):
        self.recorded_target.has_permanent_amnesia = True

class Confusione(Confusione):
    def get_targets(self):
        return {player for player in self.player.game.get_active_players() if player.pk != self.player.pk}

    def get_targets2(self):
        return None

    def get_targets_role_name(self):
        return {x.name for x in self.player.game.get_dynamics().rules.valid_roles if not x.ghost}

    def apply_dawn(self, dynamics):
        role = dynamics.rules.roles_list[self.recorded_target_role_name]
        target.apparent_aura = role.aura
        target.apparent_mystic = role.is_mystic
        target.apparent_role = role
        target.apparent_team = role.team

class Illusione(Illusione):
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

        if self.recorded_target2.role.recorded_target is not None and self.recorded_target2 in self.recorded_target2.role.recorded_target.visitors:
            self.recorded_target2.role.recorded_target.visitors.remove(self.recorded_target2)

        dynamics.illusion = (self.recorded_target2, self.recorded_target)
    
class Visione(Visione):
    def get_targets_role_bisection(self):
        return {x.name for x in self.player.game.get_dynamics().rules.valid_roles if not x.ghost}

    def pre_apply_dawn(self, dynamics):
        # Will not fail on Lupi
        return True

    def apply_dawn(self, dynamics):
        from ..events import RoleBisectionKnowledgeEvent
        dynamics.generate_event(RoleBisectionKnowledgeEvent(
                player=self.player,
                target=self.recorded_target,
                role_bisection=self.recorded_target_role_bisection,
                response=dynamics.get_apparent_role(self.recorded_target).name in self.recorded_target_role_bisection,
                cause=VISION_GHOST
        ))

# Roles that can appear in The Game
valid_roles = [Cacciatore, Contadino, Divinatore, Esorcista, Espansivo, Guardia,
    Investigatore, Mago, Massone, Messia, Sciamano, Stalker, Trasformista, Veggente,
    Voyeur, Lupo, Assassino, Avvocato, Diavolo, Fattucchiera, Alcolista, Necrofilo,
    Sequestratore, Stregone, Negromante, Fantasma,
    Amnesia, Confusione, Delusione, Illusione, Morte, Occultamento, Visione]

# Roles that can be assigned at game start
starting_roles = [role for role in valid_roles if not role.ghost]

# Roles that must be assigned at game start
required_roles = [Lupo, Negromante]

roles_list = dict([(x.name, x) for x in valid_roles])

needs_spectral_sequence = True

def post_death(dynamics, player):
    if player.team == POPOLANI and len(dynamics.spectral_sequence) > 0:
        if dynamics.spectral_sequence.pop(0):
            from ..events import GhostificationEvent
            dynamics.generate_event(GhostificationEvent(player=player, ghost=Delusione.name, cause=SPECTRAL_SEQUENCE))


