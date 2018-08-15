from django.contrib.auth.models import Permission, User
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import get_object_or_404
from game.models import *
from game.utils import get_now
from threading import Lock

# Middleware for finding Game, Dynamics and current turn.
class GameMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):

        try:
            game_name = view_kwargs['game_name']
        except KeyError:
            request.game = None
            request.player = None
            request.current_turn = None
            request.dynamics = None
            request.is_master = False
            return None

        game = get_object_or_404(Game,name=game_name)
        dynamics = None
        current_turn = None
        
        if game is not None:
            dynamics = game.get_dynamics()
            current_turn = game.current_turn

        request.game = game
        request.dynamics = dynamics
        request.current_turn = current_turn
        
        user = request.user
        if user.is_authenticated:
            # Authenticated
            try:
                master = GameMaster.objects.get(user=user,game=game)
                request.is_master = True
            except GameMaster.DoesNotExist:
                request.is_master = False

            try:
                player = Player.objects.get(user=user,game=game).canonicalize()
            except Player.DoesNotExist:
                player = None
                
            if request.is_master:
                # The User is a Game Master, so she can become any Player
                player_id = request.session.get('player_id', None)
                if player_id is not None:
                    # A Player was already saved
                    try:
                        player = Player.objects.get(pk=player_id).canonicalize()
                    except Player.DoesNotExist:
                        pass

        else:
            # Not authenticated
            player = None
            request.is_master = False
        
        request.player = player
        
        return None

# Middleware for extending Sessions of Game Masters
class SessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = request.user
        if user.is_authenticated and user.is_staff:
            # User is a GM
            request.session.set_expiry(1209600) # Session timeout set to 2 weeks.
        return None


class PageRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = request.user
        if user.is_authenticated:
            ip_address = request.META['REMOTE_ADDR'] if 'REMOTE_ADDR' in request.META else ''
            hostname = request.META['REMOTE_HOST'] if 'REMOTE_HOST' in request.META else ''
            PageRequest.objects.create(user=user, timestamp=get_now(), path=request.path, ip_address=ip_address, hostname=hostname)


