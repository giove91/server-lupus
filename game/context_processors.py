
def user_and_player(request):
    # TODO: se davvero lo user e' gia' messo automaticamente nel context, come sospetto, togliere questo TODO.
    return {
        'player': request.player,
    }
