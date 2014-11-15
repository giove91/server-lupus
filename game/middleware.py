from django.contrib.auth.models import Permission, User

from game.models import *
from game.utils import get_now

# Middleware for assigning a Player to the (possibly) logged User
class PlayerMiddleware:
    def process_request(self, request):
        
        user = request.user
        
        if user.is_authenticated():
            # Authenticated
            try:
                player = user.player.canonicalize()
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

# Middleware for extending Session for Game Masters
class SessionMiddleware:
    def process_request(self, request):
        user = request.user
        if user.is_authenticated() and user.is_staff:
            # User is a GM
            request.session.set_expiry(1209600) # Session timeout set to 2 weeks.
        return None


class PageRequestMiddleware:
    def process_request(self, request):
        user = request.user
        if user.is_authenticated():
            ip_address = request.META['REMOTE_ADDR'] if 'REMOTE_ADDR' in request.META else ''
            hostname = request.META['REMOTE_HOST'] if 'REMOTE_HOST' in request.META else ''
            PageRequest.objects.create(user=user, timestamp=get_now(), path=request.path, ip_address=ip_address, hostname=hostname)


