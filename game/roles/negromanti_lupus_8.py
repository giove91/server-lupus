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
        if self.recorded_target.role.name == self.recorded_target_role_name:
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

class Alcolista(Rinnegato):
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
                response=self.recorded_target.role.name in self.recorded_target_role_bisection,
                cause=DEVIL
        ))

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
                response=self.recorded_target.role.name in self.recorded_target_role_bisection,
                cause=VISION_GHOST
        ))

class Negromante(Negromante):
    priority = MODIFY

    def get_targets_role_name(self):
        valid_powers = {Amnesia, Confusione, Illusione, Morte, Occultamento, Visione}
        dynamics = self.player.game.get_dynamics()
        powers = {x.name for x in valid_powers}
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def pre_apply_dawn(self, dynamics):
        return self.recorded_target.role.ghost

    def apply_dawn(self, dynamics):
        from ..events import GhostSwitchEvent
        dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=self.recorded_target_role_name, cause=NECROMANCER))

class Delusione(Spettro):
    # Spettro yet to be initialized (or who has lost his power).
    frequency = NEVER
    priority = USELESS

class Amnesia(Amnesia):
    frequency = EVERY_OTHER_NIGHT
    priority = MODIFY

    def apply_dawn(self, dynamics):
        self.recorded_target.has_permanent_amnesia = True

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


