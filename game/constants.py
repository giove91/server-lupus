
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
FIRST_PHASE_BEGIN_TIME = _datetime.time(hour=22)

HALF_PHASES = [SUNSET, DAWN, CREATION]
FULL_PHASES = [DAY, NIGHT]

FULL_PHASE_END_TIMES = {
    NIGHT: _datetime.time(hour=8),
    DAY: _datetime.time(hour=22),
    }

# 0 is Monday, 6 is Sunday: here we say that DAY cannot finish on
# Friday or Saturday; moreover it cannot finish on some dates
DAY_END_SKIP_WEEKDAYS = [ 4, 5 ]
DAY_END_SKIP_DATES = [ _datetime.date(2015, 12, 6), _datetime.date(2015, 12, 7), _datetime.date(2018, 3, 4) ]

# Creation subphases
SIGNING_UP = 0
CHOOSING_ROLES = 1
SOOTHSAYING = 2
PUBLISHING_INFORMATION = 3

# User genders
MALE = 'M'
FEMALE = 'F'

# Teams
POPOLANI = 'P'
LUPI = 'L'
NEGROMANTI = 'N'

TEAM_IT = {
    POPOLANI: 'Popolani',
    LUPI: 'Lupi',
    NEGROMANTI: 'Negromanti',
}

# Auras
WHITE = 'W'
BLACK = 'B'

AURA_IT = {
    WHITE: 'Bianca',
    BLACK: 'Nera',
}

# Power frequency
UNA_TANTUM = 'U'

# Power priorities
BLOCK = 10
QUERY_INFLUENCE = 20
MODIFY_INFLUENCE = 30
QUERY = 40
MODIFY = 50
KILLER = 60
POST_MORTEM = 70
USELESS = 80

# Supernatural powers
AMNESIA = 'A'
CONFUSIONE = 'C'
ILLUSIONE = 'I'
MORTE = 'R'
OCCULTAMENTO = 'O'
VISIONE = 'V'
IPNOSI = 'P'
CORRUZIONE = 'U'

POWER_NAMES = {
    AMNESIA: 'Amnesia',
    CONFUSIONE: 'Confusione',
    CORRUZIONE: 'Corruzione',
    ILLUSIONE: 'Illusione',
    IPNOSI: 'Ipnosi',
    MORTE: 'Morte',
    OCCULTAMENTO: 'Occultamento',
    VISIONE: 'Visione'
}

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

# Stake failure causes
MISSING_QUORUM = 'Q'
ADVOCATE = 'A'

# Ghostification causes
NECROMANCER = 'N'
PHANTOM = 'P'
HYPNOTIST_DEATH = 'H'

# Role knowledge causes (PHANTOM clashes with the ghostification cause
# and so must set to the same value --- curse insufficient namespace
# separation! Same for HYPNOTIST_DEATH)
SOOTHSAYER = 'S'
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

# Aura knowledge causes
SEER = 'S'
DETECTIVE = 'D'

# Misticity knowledge causes
MAGE = 'M'

# Team knowledge causes
# None!

# Movement knowledge causes
STALKER = 'S'
VOYEUR = 'V'
KEEPER = 'K'
GUARD = 'G'

# Transformation causes
NECROPHILIAC = 'N'
TRANSFORMIST = 'T'

# Exile causes
DISQUALIFICATION = 'D'
TEAM_DEFEAT = 'T'

# Victory causes
NATURAL = 'N'
FORCED = 'F'
