from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views import generic
from django.views.generic.base import View
from django.views.generic import ListView
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core import exceptions

from django import forms

from django.contrib.auth.models import User
from game.models import *
from game.ruleset import *


def is_player_check(user):
    # Checks that the user has an associated Player
    if not user.is_authenticated():
        return False
    try:
        p = user.player
        return True
    except Player.DoesNotExist:
        return False



def home(request):
    return render(request, 'index.html')


def logout_view(request):
    logout(request)
    return redirect(home)


def setup(request):
    #setup_roles()
    setup_game()
    setup_dummy_players()
    
    return HttpResponse("Aggiunti al database i Ruoli e le Fazioni indicate.")


class VillageStatusView(View):
    def get(self, request):
        alive_players = Player.objects.filter(active=True).filter(alive=True)
        dead_players = Player.objects.filter(active=True).filter(alive=False)
        exiled_players = Player.objects.filter(active=False)
        
        game_running = None
        day = None
        phase = None
        
        try:
            game = Game.objects.get()
            day = game.current_turn.day
            phase = game.current_turn.phase_as_italian_string()
            game_running = game.running
        except Game.DoesNotExist:
            game_running = False
        
        
        context = {
            'alive_players': alive_players,
            'dead_players': dead_players,
            'exiled_players': exiled_players,
            'game_running': game_running,
            'day': day,
            'phase': phase,
        }   
        return render(request, 'status.html', context)





class ActionForm(forms.Form):
    # Generic form for submitting actions
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super(ActionForm, self).__init__(*args, **kwargs)
        for field in fields:
            self.fields[field['name']] = forms.ModelChoiceField(
                queryset=field['queryset'],
                empty_label="(Nessuno)",
                required=False,
                initial=field['initial'],
                label=field['label']
            )


class ActionView(View):
    
    template_name = 'action.html'
    
    def check(self, request):
        # Checks if the action can be done
        return request.user.player.game.running
    
    def get_fields(self, request):
        # Returns a description of the fields required
        
        queryset = Player.objects.all()
        initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Agisci su'} ]
        return fields
    
    def not_allowed(self, request):
        return render(request, 'action_not_allowed.html', {'message': "Non puoi eseguire quest'azione."})
    
    def submitted(self, request):
        return render(request, 'action_submitted.html')
    
    def save_action(self, request, cleaned_data):
        # Saves the form data
        player = request.user.player
        target = cleaned_data['target']
        
        action = Action(player=player, type='P', target=target, day=player.game.current_turn.day)
        action.save()
    
    
    def post(self, request):
        if not self.check(request):
            return self.not_allowed(request)
        
        form = ActionForm(request.POST, fields=self.get_fields(request))
        if form.is_valid():
            self.save_action(request, form.cleaned_data)
            return self.submitted(request)
        else:
            return render(request, self.template_name, {'form': form})
    
    def get(self, request):
        if not self.check(request):
            return self.not_allowed(request)
        
        form = ActionForm(fields=self.get_fields(request))
        return render(request, self.template_name, {'form': form})



class UsePowerView(ActionView):
    
    template_name = 'action_usepower.html'
    
    def check(self, request):
        # Checks if the action can be done
        return request.user.player.can_use_power()
    
    def get_fields(self, request):
        # Returns a description of the fields required
        
        #TODO: caso dei ruoli che devono agire su piu' personaggi
        
        player = request.user.player
        game = player.game
        queryset = player.get_targets()
        initial = None
        
        try:
            old_action = Action.objects.filter(day=game.current_turn.day).filter(type='P').filter(player=player).order_by('-pk')[0:1].get()
            initial = old_action.target
        except Action.DoesNotExist:
            initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Utilizza il tuo potere su'} ]
        return fields
    
    def save_action(self, request, cleaned_data):
        # Saves the form data
        player = request.user.player
        target = cleaned_data['target']
        
        action = Action(player=player, type='P', target=target, day=player.game.current_turn.day)
        action.save()


class VoteView(ActionView):
    
    template_name = 'action_vote.html'
    
    def check(self, request):
        # Checks if the action can be done
        return request.user.player.can_vote()
    
    def get_fields(self, request):
        # Returns a description of the fields required
        
        player = request.user.player
        game = player.game
        queryset = Player.objects.filter(active=True).filter(alive=True)
        initial = None
        
        try:
            old_action = Action.objects.filter(day=game.current_turn.day).filter(type='V').filter(player=player).order_by('-pk')[0:1].get()
            initial = old_action.target
        except Action.DoesNotExist:
            initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Vota per condannare a morte'} ]
        return fields
    
    def save_action(self, request, cleaned_data):
        # Saves the form data
        player = request.user.player
        target = cleaned_data['target']
        
        action = Action(player=player, type='V', target=target, day=player.game.current_turn.day)
        action.save()


class ElectView(ActionView):
    
    template_name = 'action_elect.html'
    
    def check(self, request):
        # Checks if the action can be done
        return request.user.player.can_vote()
    
    def get_fields(self, request):
        # Returns a description of the fields required
        
        player = request.user.player
        game = player.game
        queryset = Player.objects.filter(active=True).filter(alive=True)
        initial = None
        
        try:
            old_action = Action.objects.filter(day=game.current_turn.day).filter(type='E').filter(player=player).order_by('-pk')[0:1].get()
            initial = old_action.target
        except Action.DoesNotExist:
            initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Vota per eleggere'} ]
        return fields
    
    def save_action(self, request, cleaned_data):
        # Saves the form data
        player = request.user.player
        target = cleaned_data['target']
        
        action = Action(player=player, type='E', target=target, day=player.game.current_turn.day)
        action.save()


class PersonalInfoView(View):
    def get(self, request):
        game = Game.objects.get()
        
        team = '-'
        role = '-'
        aura = '-'
        is_mystic = False
        status = '-'
        
        if game.running:
            # Everything should be set
            player = request.user.player
            team = player.team.team_name
            role = player.role.role_name
            aura = player.aura_as_italian_string()
            is_mystic = player.is_mystic
            status = player.status_as_italian_string()
        
        context = {
            'team': team,
            'role': role,
            'aura': aura,
            'is_mystic': is_mystic,
            'status': status,
        }
        
        return render(request, 'personal_info.html', context)



