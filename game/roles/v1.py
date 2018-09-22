from .base import *
from ..constants import *

class Rules(Rules):
    pass

class Cacciatore(Cacciatore):
    pass

class Contadino(Contadino):
    pass

class Custode(Custode):
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

class Trasformista(Trasformista):
    pass

class Veggente(Veggente):
    pass

class Voyeur(Voyeur):
    pass

class Lupo(Lupo):
    required = True

class Assassino(Assassino):
    pass

class Avvocato(Avvocato):
    pass

class Diavolo(Diavolo):
    pass

class Fattucchiera(Fattucchiera):
    pass

class Rinnegato(Rinnegato):
    pass

class Necrofilo(Necrofilo):
    pass

class Sequestratore(Sequestratore):
    pass

class Stregone(Stregone):
    pass

class Negromante(Negromante):
    required = True

class Fantasma(Fantasma):
    # We must refer to the correct definitions of the powers
    def get_valid_powers(self):
        return {Amnesia, Confusione, Illusione, Ipnosi, Occultamento, Visione}

class Ipnotista(Ipnotista):
    pass

class Medium(Medium):
    pass

class Scrutatore(Scrutatore):
    pass

class Amnesia(Amnesia):
    pass

class Confusione(Confusione):
    pass

class Corruzione(Corruzione):
    on_mystic_only = True

class Illusione(Illusione):
    pass

class Ipnosi(Ipnosi):
    pass

class Morte(Morte):
    on_mystic_only = True

class Occultamento(Occultamento):
    pass

class Visione(Visione):
    pass
