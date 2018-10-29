from .models import Game, Announcement
from .constants import *
from .utils import get_now


def context_player_and_game(request):
    player = request.player
    game = request.game

    return {
        'player': player,
        'game': game,
        'master': request.master,
        'is_master': request.is_master
    }

def context_current_turn(request):
    current_turn = request.current_turn
    if current_turn is None:
        return {}

    current_date = current_turn.date
    current_phase = current_turn.phase_as_italian_string()

    return {
        'current_turn': current_turn,
        'current_date': current_date, # Maybe useless
        'current_phase': current_phase, # Maybe useless
    }

def context_rules(request):
    dynamics = request.dynamics
    if dynamics is None or not hasattr(dynamics, 'rules'):
        return {}
    else:
        return {
            'rules': dynamics.rules
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

    return {
        'latest_announcement': Announcement.objects
            .filter(game=game)
            .filter(visible=True)
            .order_by('-timestamp')
            .first()
    }


def context_lupus(request):
    context_functions = [
        context_player_and_game,
        context_current_turn,
        context_constants,
        context_latest_announcement,
        context_rules,
    ]
    result = dict()
    for f in context_functions:
        result = dict( result.items() | f(request).items() )
    return result






