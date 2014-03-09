
# The leading underscore is required, because otherwise importing *
# from constants would also import datetime (and overwrite the real
# definition of datetime there)
import datetime as _datetime
import pytz as _pytz

REF_TZINFO = _pytz.timezone('Europe/Rome')

# Turn phases (we used to have letters here, but we need something
# that preserves the order in the database; FIXME: find a better
# solution)
DAY = '3'
SUNSET = '4'
NIGHT = '1'
DAWN = '2'
CREATION = '0'

PHASE_CYCLE = {
    DAY: SUNSET,
    SUNSET: NIGHT,
    NIGHT: DAWN,
    DAWN: DAY,
}
REV_PHASE_CYCLE = {}
for key, value in PHASE_CYCLE.iteritems():
    REV_PHASE_CYCLE[value] = key
PHASE_CYCLE[CREATION] = NIGHT

# This must be the phase that compares the lowest (excluding creation)
DATE_CHANGE_PHASE = NIGHT

FIRST_PHASE = CREATION
FIRST_DATE = 0
FIRST_PHASE_BEGIN_TIME = _datetime.time(hour=22, tzinfo=REF_TZINFO)

HALF_PHASES = [SUNSET, DAWN, CREATION]
FULL_PHASES = [DAY, NIGHT]

FULL_PHASE_END_TIMES = {
    NIGHT: _datetime.time(hour=8, tzinfo=REF_TZINFO),
    DAY: _datetime.time(hour=22, tzinfo=REF_TZINFO),
    }

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

# Supernatural powers
AMNESIA = 'A'
DUPLICAZIONE = 'D'
ILLUSIONE = 'I'
MISTIFICAZIONE = 'M'
MORTE = 'R'
OCCULTAMENTO = 'O'
VISIONE = 'V'

# Commands
USEPOWER = 'P'
VOTE = 'V'
ELECT = 'E'
APPOINT = 'A'

# Death causes
STAKE = 'S'
HUNTER = 'H'
WOLVES = 'W'
DEATH_GHOST = 'D'

# Stake failure causes
MISSING_QUORUM = 'Q'
ADVOCATE = 'A'

# Ghostification causes
NECROMANCER = 'N'
PHANTOM = 'P'

# Role knowledge causes (PHANTOM clashes with the ghostification cause
# and so must set to the same value --- curse insufficient namespace
# separation!)
SOOTHSAYER = 'S'
EXPANSIVE = 'E'
KNOWLEDGE_CLASS = 'C'
GHOST = 'G'
PHANTOM = 'P'
DEVIL = 'D'

# Aura knowledge causes
SEER = 'S'
DETECTIVE = 'D'

# Misticity knowledge causes
MAGE = 'M'

# Team knowledge causes
VISION_GHOST = 'V'

# Movement knowledge causes
STALKER = 'S'
VOYEUR = 'V'

# Medium knowledge causes
MEDIUM = 'M'

# Exile causes
DISQUALIFICATION = 'D'
TEAM_DEFEAT = 'T'

# Victory causes
NATURAL = 'N'
FORCED = 'F'
