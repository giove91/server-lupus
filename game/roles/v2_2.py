from .v2 import *
from ..constants import *

class Rules(Rules):
    teams = [POPOLANI, LUPI]
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
    pass

class Stalker(Stalker):
    pass

class Spia(Role):
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

class Spettrificazione(Spettrificazione):
    team = LUPI

class Fantasma(Fantasma):
    knowledge_class = 1

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

class Telepatia(Spettro):
    pass

class Vita(Spettro):
    pass

## ORDER COSTRAINTS
#
# Necromancers must act after every other ghost.
# If not, they will change power before they can use it.
#
# The same applies for Shamans, who must act after every other ghost but before necromancers.
