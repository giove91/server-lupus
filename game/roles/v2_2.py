from .v2 import *
from ..constants import *

class Rules(Rules):
    teams = [POPOLANI, LUPI]
    necromancers_team = LUPI
    @staticmethod
    def post_death(dynamics, player):
        if player.team == POPOLANI and len(dynamics.spectral_sequence) > 0 and not LUPI in dynamics.dying_teams:
            if dynamics.spectral_sequence.pop(0):
                from ..events import GhostificationEvent, RoleKnowledgeEvent
                dynamics.schedule_event(GhostificationEvent(player=player, ghost=Delusione, cause=SPECTRAL_SEQUENCE))
                for negromante in dynamics.players:
                    if negromante.role.necromancer:
                        dynamics.schedule_event(RoleKnowledgeEvent(player=player,
                                                                   target=negromante,
                                                                   role_class=negromante.role.__class__,
                                                                   cause=GHOST))
                        dynamics.schedule_event(RoleKnowledgeEvent(player=negromante,
                                                                   target=player,
                                                                   role_class=Delusione,
                                                                   cause=SPECTRAL_SEQUENCE))


##############
#  POPOLANI  #
##############

class Cacciatore(Cacciatore):
    pass

class Contadino(Contadino):
    pass

class Divinatore(Divinatore):
    pass

class Esorcista(Esorcista):
    pass

class Espansivo(Espansivo):
    pass

class Guardia(Guardia):
    pass

class Investigatore(Investigatore):
    pass

class Mago(Mago):
    pass

class Massone(Massone):
    pass

class Messia(Messia):
    pass

class Sciamano(Sciamano):
    # Same as before, but with correct Delusione
    def apply_dawn(self, dynamics):
        self.recorded_target.protected_by_keeper = True
        if self.recorded_target.specter and not isinstance(self.recorded_target.dead_power, Delusione):
            from ..events import GhostSwitchEvent
            dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=Delusione, cause=SHAMAN))

class Stalker(Stalker):
    pass

class Spia(Spia):
    pass

class Trasformista(Trasformista):
    pass

class Veggente(Veggente):
    pass

class Voyeur(Voyeur):
    pass

##############
#    LUPI    #
##############

class Lupo(Lupo):
    pass

class Assassino(Assassino):
    pass

class Diavolo(Diavolo):
    pass

class Fattucchiera(Fattucchiera):
    pass

class Alcolista(Alcolista):
    pass

class Sequestratore(Sequestratore):
    pass

class Stregone(Stregone):
    pass

##############
# NEGROMANTI #
##############

class Negromante(Negromante):
    knowledge_class = 1
    team = LUPI

    def post_not_alive(self, dynamics):
        # Nothing happens when they die
        pass

    # We need to redefine powers so they use the correct instance.
    def get_targets_role_class(self, dynamics):
        powers = {Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia, Vita, Delusione}
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def get_target_role_class_default(self, dynamics):
        return Delusione

    def apply_dawn(self, dynamics):
        assert self.recorded_target.specter
        from ..events import GhostSwitchEvent
        spell = self.recorded_role_class if self.recorded_role_class is not None else Delusione
        dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=spell, cause=NECROMANCER))

    def post_death(self, dynamics):
        if isinstance(self.player.dead_power, NoPower):
            self.player.dead_power = Spettrificazione(self.player)

class Spettrificazione(Spettrificazione):
    team = LUPI

    # Use the updated powers
    def get_targets_role_class(self, dynamics):
        powers = {Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia, Vita, Delusione}
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def get_target_role_class_default(self, dynamics):
        return Delusione

class Fantasma(Fantasma):
    team = LUPI
    knowledge_class = 1

    def get_valid_powers(self):
        return [Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia]

    def post_death(self, dynamics):
        powers = self.get_valid_powers()
        available_powers = [x for x in powers if x not in dynamics.used_ghost_powers and x not in dynamics.just_used_powers]
        if len(available_powers) >= 1:
            power = dynamics.random.choice(available_powers)
        else:
            power = Delusione

        from ..events import RoleKnowledgeEvent, GhostificationEvent
        dynamics.generate_event(GhostificationEvent(player=self.player, cause=PHANTOM, ghost=power))

class Delusione(Delusione):
    pass

class Amnesia(Amnesia):
    pass

class Assoluzione(Assoluzione):
    pass

class Diffamazione(Diffamazione):
    pass

class Confusione(Confusione):
    pass

class Illusione(Illusione):
    pass

class Morte(Morte):
    pass

class Occultamento(Occultamento):
    pass

class Telepatia(Telepatia):
    pass

class Vita(Vita):
    # Same as before, correct Delusione
    def post_death(self, dynamics):
        from ..events import GhostSwitchEvent
        dynamics.generate_event(GhostSwitchEvent(player=self.player, ghost=Delusione, cause=LIFE_GHOST))
## ORDER COSTRAINTS
#
# Necromancers must act after every other ghost.
# If not, they will change power before they can use it.
#
# The same applies for Shamans, who must act after every other ghost but before necromancers.
