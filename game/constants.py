
# The leading underscore is required, because otherwise importing *
# from constants would also import datetime (and overwrite the real
# definition of datetime there)
import datetime as _datetime

# Turn phases
DAY = 'D'
SUNSET = 'S'
NIGHT = 'N'
DAWN = 'W'
CREATION = 'C'

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

FIRST_PHASE = CREATION
FIRST_DATE = 0
FIRST_PHASE_BEGIN_TIME = _datetime.time(hour=22)

HALF_PHASES = [SUNSET, DAWN, CREATION]
FULL_PHASES = [DAY, NIGHT]

FULL_PHASE_END_TIMES = {
    NIGHT: _datetime.time(hour=8),
    DAY: _datetime.time(hour=22),
    }

# Teams
POPOLANI = 'P'
LUPI = 'L'
NEGROMANTI = 'N'

# Auras
WHITE = 'W'
BLACK = 'B'

# Supernatural powers
AMNESIA = 'A'
DUPLICAZIONE = 'D'
ILLUSIONE = 'I'
MISTIFICAZIONE = 'M'
MORTE = 'R'
OCCULTAMENTO = 'O'
OMBRA = 'B'
VISIONE = 'V'

# Commands
USEPOWER = 'P'
VOTE = 'V'
ELECT = 'E'
