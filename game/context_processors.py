from models import Game


def context_player(request):
    return {
        'player': request.player,
    }

def context_current_turn(request):
    game = Game.get_running_game()
    
    if game is None:
        return {}
    
    dynamics = game.get_dynamics()
    current_turn = dynamics.current_turn
    
    current_date = current_turn.date
    current_phase = current_turn.phase_as_italian_string()
    
    return {
        'current_date': current_date,
        'current_phase': current_phase,
    }
