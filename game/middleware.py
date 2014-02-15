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
                            player = Player.objects.get(pk=player_id)
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
        
        request.player = player.canonicalize()
        
        return None


