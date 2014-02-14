from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.views import generic
from django.views.generic.base import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core import exceptions

from django import forms

from django.contrib.auth.models import User
from game.models import *
from game.events import *
from game.roles import *
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
    setup_game()
    
    return render(request, 'index.html')


def advance_turn(request):
    return render(request, 'index.html')


def ruleset(request):
    return render(request, 'ruleset.html')


class VillageStatusView(View):
    def get(self, request):
        
        game_running = None
        date = None
        phase = None
        alive_players = None
        dead_players = None
        inactive_players = None
        
        try:
            game = Game.get_running_game()
            game_running = game.running
            if game.current_turn is not None:
                date = game.current_turn.date
                phase = game.current_turn.phase_as_italian_string()
            alive_players = game.get_alive_players()
            dead_players = game.get_dead_players()
            inactive_players = game.get_inactive_players()
        except Game.DoesNotExist:
            game_running = False
        
        context = {
            'alive_players': alive_players,
            'dead_players': dead_players,
            'inactive_players': inactive_players,
            'game_running': game_running,
            'date': date,
            'phase': phase,
        }   
        return render(request, 'status.html', context)



class CommandForm(forms.Form):
    # Generic form for submitting actions
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super(CommandForm, self).__init__(*args, **kwargs)
        for field in fields:
            self.fields[field['name']] = forms.ModelChoiceField(
                queryset=field['queryset'],
                empty_label="(Nessuno)",
                required=False,
                initial=field['initial'],
                label=field['label']
            )

class CommandView(View):
    
    template_name = 'command.html'
    
    def check(self, request):
        # Checks if the action can be done
        raise Exception ('Command not specified.')
    
    def get_fields(self, request):
        # Returns a description of the fields required
        raise Exception ('Command not specified.')
    
    def not_allowed(self, request):
        return render(request, 'command_not_allowed.html', {'message': 'Non puoi eseguire questa azione.'})
    
    def submitted(self, request):
        return render(request, 'command_submitted.html')
    
    def save_command(self, request, cleaned_data):
        # Validates the form data and possibly saves the command, returning True in case of success and False otherwise
        raise Exception ('Command not specified.')
    
    def post(self, request):
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(request.POST, fields=self.get_fields(request))
        if form.is_valid():
            if self.save_command(request, form.cleaned_data):
                return self.submitted(request)
            else:
                return render(request, 'command_not_allowed.html', {'message': 'La scelta effettuata non &egrave; valida.'})
        else:
            return render(request, self.template_name, {'form': form})
    
    def get(self, request):
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(fields=self.get_fields(request))
        return render(request, self.template_name, {'form': form})


class UsePowerView(CommandView):
    
    template_name = 'command_usepower.html'
    
    def check(self, request):
        return request.user.player.can_use_power()
    
    def get_fields(self, request):
        player = request.user.player
        game = player.game
        role = player.role.as_child()
        
        targets = role.get_targets()
        targets2 = role.get_targets2()
        targets_ghost = role.get_targets_ghost()
        
        initial = None
        initial2 = None
        initial_ghost = None
        
        try:
            old_command = CommandEvent.objects.filter(turn=game.current_turn).filter(type=USEPOWER).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
            initial2 = old_command.target2
            initial_ghost = old_command.target_ghost
        except CommandEvent.DoesNotExist:
            pass
        
        # "target" field is always assumed to be present
        fields = [ {'name': 'target', 'queryset': targets, 'initial': initial, 'label': player.role.as_child().message} ]
        if targets2 is not None:
            fields.append( {'name': 'target2', 'queryset': targets2, 'initial': initial2, 'label': player.role.as_child().message2} )
        if targets_ghost is not None:
            fields.append( {'name': 'target_ghost', 'queryset': targets_ghost, 'initial': initial_ghost, 'label': player.role.as_child().message_ghost} )
        
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.user.player
        role = player.role.as_child()
        
        targets = role.get_targets()
        targets2 = role.get_targets2()
        targets_ghost = role.get_targets_ghost()
        
        target = cleaned_data['target']
        target2 = None
        target_ghost = None
        
        if target is not None and not target in targets:
            return False
        
        if targets2 is not None:
            target2 = cleaned_data['target2']
            if not target2 in targets2:
                return False
        if targets_ghost is not None:
            target_ghost = cleaned_data['target_ghost']
            if not target_ghost in targets_ghost:
                return False
        
        # If target is None, then the other fields are set to None
        if target is None:
            target2 = None
            target_ghost = None
        
        command = CommandEvent(player=player, type=USEPOWER, target=target, target2=target2, target_ghost=target_ghost, turn=player.game.current_turn)
        command.save()
        return True


class VoteView(CommandView):
    
    template_name = 'command_vote.html'
    
    def check(self, request):
        return request.user.player.can_vote()
    
    def get_fields(self, request):
        player = request.user.player
        game = player.game
        queryset = game.get_alive_players()
        initial = None
        
        try:
            old_command = CommandEvent.objects.filter(turn=game.current_turn).filter(type=VOTE).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
        except CommandEvent.DoesNotExist:
            initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Vota per condannare a morte:'} ]
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.user.player
        game = player.game
        target = cleaned_data['target']
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=VOTE, target=target, turn=game.current_turn)
        command.save()
        return True


class ElectView(CommandView):
    
    template_name = 'command_elect.html'
    
    def check(self, request):
        return request.user.player.can_vote()
    
    def get_fields(self, request):
        player = request.user.player
        game = player.game
        queryset = game.get_alive_players()
        initial = None
        
        try:
            old_command = CommandEvent.objects.filter(turn=game.current_turn).filter(type=ELECT).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
        except CommandEvent.DoesNotExist:
            initial = None
        
        fields = [ {'name': 'target', 'queryset': queryset, 'initial': initial, 'label': 'Vota per eleggere:'} ]
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.user.player
        game = player.game
        target = cleaned_data['target']
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=ELECT, target=target, turn=game.current_turn)
        command.save()
        return True


class PersonalInfoView(View):
    def get(self, request):
        game = request.user.player.game
        
        
        if request.session.get('has_visited', False):
            prova = u'Non sei passato di qua recentemente'
        else:
            prova = u'Bentornato!'
        request.session['has_visited'] = True
        
        
        team = '-'
        role = '-'
        aura = '-'
        is_mystic = False
        status = '-'
        
        if game.running:
            # Everything should be set
            player = request.user.player.canonicalize()
            team = player.team
            role = player.role.name
            aura = player.aura_as_italian_string()
            is_mystic = player.is_mystic
            status = player.status_as_italian_string()
        
        context = {
            'team': team,
            'role': role,
            'aura': aura,
            'is_mystic': is_mystic,
            'status': status,
            'prova': prova,
        }
        
        return render(request, 'personal_info.html', context)


class ContactsView(ListView):
    
    model = Player
    
    template_name = 'contacts.html'
    
    # TODO: forse un giorno bisognerebbe filtrare con il Game giusto
    '''
    def get_queryset(self):
        return User.objects.filter(player__isnull=False)
    '''

