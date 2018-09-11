#!/usr/bin/python
# coding=utf8

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

def is_staff_check(user):
    # Checks that the user is an admin
    if not user.is_authenticated:
        return False
    return user.is_staff

def master_required(func):
    def decorator(request, *args, **kwargs):
        if request.is_master:
            return func(request, *args, **kwargs)
        elif request.user.is_authenticated:
            return redirect('game:status',game_name=request.game.name)
        else:
            return redirect_to_login(request.get_full_path())

    return decorator

def player_required(func):
    """Checks that the user is logged as a player."""
    def decorator(request, *args, **kwargs):
        if request.player is not None:
            return func(request, *args, **kwargs)
        else:
            return redirect('game:pointofview',game_name=request.game.name)

    return decorator

def player_or_master_required(func):
    """Checks that the user is taking part in the current game."""
    def decorator(request, *args, **kwargs):
        if request.master is not None or (request.player is not None and request.game.started):
            return func(request, *args, **kwargs)
        elif request.user.is_authenticated:
            return redirect('game:status',game_name=request.game.name)
        else:
            return redirect_to_login(request.get_full_path())

    return decorator


def registrations_open(func):
    """Checks that the game is not started."""
    def decorator(request, *args, **kwargs):
        if request.game is not None and not request.game.started:
            return func(request, *args, **kwargs)
        else:
            return redirect('game:status',game_name=request.game.name)

    return decorator


def can_access_admin_view(func):
    def decorator(request, *args, **kwargs):
        if request.is_master or ((request.player or request.master) and request.game.is_over and request.game.postgame_info):
            return func(request, *args, **kwargs)
        else:
            return redirect_to_login(request.get_full_path())

    return decorator
