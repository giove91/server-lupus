from .base import *
from ..constants import *

# Define variable used for the game

starting_teams = [POPOLANI, LUPI, NEGROMANTI]

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

# Roles that can appear in The Game
valid_roles = [Cacciatore, Contadino, Divinatore, Esorcista, Espansivo, Guardia,
    Investigatore, Mago, Massone, Messia, Sciamano, Stalker, Trasformista, Veggente,
    Voyeur, Lupo, Assassino, Avvocato, Diavolo, Fattucchiera, Rinnegato, Necrofilo,
    Sequestratore, Stregone, Negromante, Fantasma,
    Confusione, Corruzione, Delusione, Illusione, Morte, Occultamento, Visione]

# Roles that can be assigned at game start
starting_roles = [role for role in valid_roles if not role.ghost]

# Roles that must be assigned at game start
required_roles = [Lupo, Negromante]

roles_list = dict([(x.name, x) for x in valid_roles])

needs_spectral_sequence = True

def post_death(dynamics, player):
    if player.team == POPOLANI and len(dynamics.spectral_sequence) > 0:
        if dynamics.spectral_sequence.pop():
            from ..events import GhostificationEvent
            dynamics.generate_event(GhostificationEvent(player=player, ghost=Delusione.name, cause=SPECTRAL_SEQUENCE))


