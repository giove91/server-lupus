from django.contrib.auth.models import Permission, User

from game.models import *

# Middleware for assigning a Player to the (possibly) logged User
class PlayerMiddleware:
    def process_request(self, request):
        
        user = request.user
        
        if user.is_authenticated():
            # Authenticated
            try:
                player = user.player
            except Player.DoesNotExist:
                if user.is_staff:
                    # The User is a Game Master, so she can become any Player
                    player_id = request.session.get('player_id', None)
                    if player_id is not None:
                        # A Player was already saved
                        try:
                            player = Player.objects.get(pk=player_id).canonicalize()
                        except Player.DoesNotExist:
                            player = None
                    else:
                        # No Player was saved
                        player = None
                else:
                    player = None
        else:
            # Not authenticated
            player = None
        
        request.player = player
        
        return None


# Middleware for finding the Game and the Dynamics
# TODO: forse e' il caso di unificarla alla precedente, assicurando che player.game==game quando esistono entrambi
class GameMiddleware:
    def process_request(self, request):
        
        game = Game.get_running_game()
        dynamics = None
        
        if game is not None:
            dynamics = game.get_dynamics()
        
        request.game = game
        request.dynamics = dynamics
        
        return None





