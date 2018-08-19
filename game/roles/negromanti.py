from .base import *
from ..constants import *

# Define variable used for the game

starting_teams = [POPOLANI, LUPI, NEGROMANTI]

# Roles that can appear in The Game
valid_roles = [Cacciatore, Contadino, Custode, Divinatore, Esorcista, Espansivo, Guardia,
    Investigatore, Mago, Massone, Messia, Sciamano, Stalker, Trasformista, Veggente,
    Voyeur, Lupo, Assassino, Avvocato, Diavolo, Fattucchiera, Rinnegato, Necrofilo,
    Sequestratore, Stregone, Negromante, Fantasma, Ipnotista, Medium, Scrutatore,
    Amnesia, Confusione, Corruzione, Illusione, Ipnosi, Morte, Occultamento, Visione]

# Roles that can be assigned at game start
starting_roles = [role for role in valid_roles if not role.ghost]

# Roles that must be assigned at game start
required_roles = [Lupo, Negromante]

roles_list = dict([(x.__name__, x) for x in valid_roles])
