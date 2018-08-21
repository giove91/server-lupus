from ..constants import *
from .base import *

# Define variable used for the game

starting_teams = [POPOLANI, LUPI]

# Roles that can appear in The Game
valid_roles = [Cacciatore, Contadino, Divinatore, Espansivo, Guardia,
    Investigatore, Mago, Massone, Messia, Stalker, Trasformista, Veggente,
    Voyeur, Lupo, Assassino, Avvocato, Diavolo, Fattucchiera, Rinnegato, Necrofilo,
    Sequestratore, Stregone]

# Roles that can be assigned at game start
starting_roles = valid_roles

# Roles that must be assigned at game start
required_roles = [Lupo]

roles_list = dict([(x.__name__, x) for x in valid_roles])
