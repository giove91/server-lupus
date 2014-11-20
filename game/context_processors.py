from models import Game, Announcement
from constants import *
from utils import get_now


def context_player_and_game(request):
    return {
        'player': request.player,
        'game': request.game,
    }

def context_current_turn(request):
    dynamics = request.dynamics
    if dynamics is None:
        return {}

    current_turn = dynamics.current_turn

    # If the current turn has actually finished, automatically assume
    # that we are in the following one
    if current_turn.end is not None and get_now() >= current_turn.end:
        current_turn = current_turn.next_turn()

    current_date = current_turn.date
    current_phase = current_turn.phase_as_italian_string()

    return {
        'current_turn': current_turn,
        'current_date': current_date, # Maybe useless
        'current_phase': current_phase, # Maybe useless
    }

def context_constants(request):
    return {
        'CREATION': CREATION,
        'DAY': DAY,
        'NIGHT': NIGHT,
        'DAWN': DAWN,
        'SUNSET': SUNSET,
        'VOTE': VOTE,
        'ELECT': ELECT,
    }

def context_latest_announcement(request):
    game = request.game
    try:
        latest_announcement = Announcement.objects.filter(game=game).filter(visible=True).order_by('-timestamp')[0]
    except IndexError:
        latest_announcement = None
    
    # TODO: se servisse, fare in modo che vengano mostrati anche gli announcements con game=None
    
    return {
        'latest_announcement': latest_announcement
    }



def context_lupus(request):
    context_functions = [
        context_player_and_game,
        context_current_turn,
        context_constants,
        context_latest_announcement,
    ]
    result = dict()
    for f in context_functions:
        result = dict( result.items() + f(request).items() )
    return result






