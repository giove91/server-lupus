
# The leading underscore is required, because otherwise importing *
# from constants would also import datetime (and overwrite the real
# definition of datetime there)
import datetime as _datetime
import pytz as _pytz

# The game is based in Italy!
REF_TZINFO = _pytz.timezone('Europe/Rome')

# Turn phases (we used to have letters here, but we need something
# that preserves the order in the database; FIXME: find a better
# solution)
DAY = '2'
SUNSET = '3'
NIGHT = '4'
DAWN = '1'
CREATION = '0'

PHASE_CYCLE = {
    DAY: SUNSET,
    SUNSET: NIGHT,
    NIGHT: DAWN,
    DAWN: DAY,
}
REV_PHASE_CYCLE = {}
for key, value in iter(PHASE_CYCLE.items()):
    REV_PHASE_CYCLE[value] = key
PHASE_CYCLE[CREATION] = NIGHT

# This must be the phase that compares the lowest (excluding creation)
DATE_CHANGE_PHASE = DAWN

FIRST_PHASE = CREATION
FIRST_DATE = 0

HALF_PHASES = [SUNSET, DAWN]
FULL_PHASES = [DAY, NIGHT]

# User genders
MALE = 'M'
FEMALE = 'F'

# Teams
POPOLANI = 'P'
LUPI = 'L'
NEGROMANTI = 'N'

TEAMS = [POPOLANI, LUPI, NEGROMANTI]

TEAM_IT = {
    POPOLANI: 'Popolani',
    LUPI: 'Lupi',
    NEGROMANTI: 'Negromanti',
    None: 'Nessuna'
}

# Auras
WHITE = 'W'
BLACK = 'B'

AURA_IT = {
    WHITE: 'Bianca',
    BLACK: 'Nera',
    None: 'Nessuna'
}

# Soothsayer errors
NUMBER_MISMATCH = 'N'
TRUTH_MISMATCH = 'T'
KNOWS_ABOUT_SELF = 'S'

# Power frequency

NEVER = 0
EVERY_NIGHT = 1
EVERY_OTHER_NIGHT = 2
ONCE_A_GAME = 3
EXCEPT_THE_FIRST = 4

# Power priorities
EVENT_INFLUENCE = 0
BLOCK = 10
QUERY_INFLUENCE = 20
MODIFY_INFLUENCE = 30
QUERY = 40
MODIFY = 50
KILLER = 60
POST_MORTEM = 70
USELESS = 80

# Power targets
ALIVE = 'A'
DEAD = 'D'
EVERYBODY = 'E'

# Commands
USEPOWER = 'P'
VOTE = 'V'
ELECT = 'E'
APPOINT = 'A'

# Mayor set causes (ELECT clashes with above)
BEGINNING = 'B'
ELECT = 'E'
SUCCESSION_RANDOM = 'R'
SUCCESSION_CHOSEN = 'C'

# Death causes
STAKE = 'S'
HUNTER = 'H'
WOLVES = 'W'
ASSASSIN = 'A'
DEATH_GHOST = 'D'
LIFE_GHOST = 'L'

# Stake failure causes
MISSING_QUORUM = 'Q'
ADVOCATE = 'A'

# Ghostification causes
NECROMANCER = 'N'
PHANTOM = 'P'
HYPNOTIST_DEATH = 'H'
SPECTRAL_SEQUENCE = 'S'
LIFE_GHOST = 'L'

# Role knowledge causes (PHANTOM clashes with the ghostification cause
# and so must set to the same value --- curse insufficient namespace
# separation! Same for HYPNOTIST_DEATH)
SOOTHSAYER = 'S' # His night power
EXPANSIVE = 'E'
KNOWLEDGE_CLASS = 'C'
GHOST = 'G'
PHANTOM = 'P'
DEVIL = 'D'
VISION_GHOST = 'V'
HYPNOTIST_DEATH = 'H'
MEDIUM = 'M'
NECROPHILIAC = 'N'
CORRUPTION = 'O'
SPECTRAL_SEQUENCE = 'Q'

# Aura knowledge causes
SEER = 'S'
DETECTIVE = 'I'

# Misticity knowledge causes
MAGE = 'M'

# Team knowledge causes
# None!

# VoteKnowledge causes
SPY = 'S'

# Movement knowledge causes
STALKER = 'S'
VOYEUR = 'V'
KEEPER = 'K'
GUARD = 'G'
KIDNAPPER = 'D'

# Transformation causes
NECROPHILIAC = 'N'
TRANSFORMIST = 'T'

# Exile causes
DISQUALIFICATION = 'D'
TEAM_DEFEAT = 'T'

# Victory causes
NATURAL = 'N'
FORCED = 'F'

