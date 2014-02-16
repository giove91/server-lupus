from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse

from django.views import generic
from django.views.generic.base import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.core import exceptions

from django import forms

from django.contrib.auth.models import User
from game.models import *
from game.events import *
from game.roles import *
from game.ruleset import *
from game.utils import get_now

from datetime import datetime


def is_GM_check(user):
    # Checks that the user is a GM
    if not user.is_authenticated():
        return False
    return user.is_staff



def home(request):
    return render(request, 'index.html')


def logout_view(request):
    logout(request)
    return redirect(home)


def setup(request):
    setup_game(get_now())
    return render(request, 'index.html')


def advance_turn(request):
    game = Game.get_running_game()
    turn = game.current_turn
    turn.end = get_now()
    turn.save()
    game.advance_turn()
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


class PublicEventsView(View):
    def get(self, request):
        # TODO: write
        
        context = {}
        return render(request, 'public_events.html', context)


class CommandForm(forms.Form):
    # "Generic" form for submitting actions
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super(CommandForm, self).__init__(*args, **kwargs)
        
        for key, field in fields.iteritems():
            if key == 'target' or key == 'target2':
                choices = [ (None, '(Nessuno)') ]
                choices.extend( [ (player.pk, player.full_name) for player in field['choices'] ] )
            elif key == 'target_ghost':
                choices = [ (None, '(Nessuno)') ]
                choices.extend( [ (power, Spettro.POWER_NAMES[power]) for power in field['choices'] ] )
            else:
                raise Exception ('Unknown form field.')
            
            self.fields[key] = forms.ChoiceField(choices=choices, required=False, label=field['label'])
            
            if key == 'target' or key == 'target2':
                if field['initial'] is not None:
                    self.fields[key].initial = field['initial'].pk
                else:
                    self.fields[key].initial = None
            elif key == 'target_ghost':
                self.fields[key].initial = field['initial']
    
    def clean(self):
        cleaned_data = super(CommandForm, self).clean()
        
        for key, field in self.fields.iteritems():
            if key == 'target' or key == 'target2':
                player_id = cleaned_data.get(key)
                if player_id:
                    if player_id == u'None':
                        cleaned_data[key] = None
                    else:
                        try:
                            player = Player.objects.get(pk=player_id).canonicalize()
                        except Player.DoesNotExist:
                            raise forms.ValidationError('Player does not exist')
                        cleaned_data[key] = player
        
        return cleaned_data



class CommandView(View):
    
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
        if request.player is None:
            # TODO: fare qualcosa di piu' ragionevole, tipo reindirizzare alla pagina in cui l'amministratore puo' trasformarsi in un altro giocatore.
            return render(request, 'index.html')
        
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(fields=self.get_fields(request))
        return render(request, self.template_name, {'form': form})
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CommandView, self).dispatch(*args, **kwargs)


class UsePowerView(CommandView):
    
    template_name = 'command_usepower.html'
    
    def check(self, request):
        return request.player is not None and request.player.can_use_power()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        role = player.role
        
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
        
        fields = {}
        if targets is not None:
            fields['target'] = {'choices': targets, 'initial': initial, 'label': player.role.message}
        if targets2 is not None:
            fields['target2'] = {'choices': targets2, 'initial': initial2, 'label': player.role.message2}
        if targets_ghost is not None:
            fields['target_ghost'] = {'choices': targets_ghost, 'initial': initial_ghost, 'label': player.role.message_ghost}
        
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        role = player.role
        
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
        
        command = CommandEvent(player=player, type=USEPOWER, target=target, target2=target2, target_ghost=target_ghost, turn=player.game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class VoteView(CommandView):
    
    template_name = 'command_vote.html'
    
    def check(self, request):
        return request.player is not None and request.player.can_vote()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = game.get_alive_players()
        initial = None
        
        try:
            old_command = CommandEvent.objects.filter(turn=game.current_turn).filter(type=VOTE).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
        except CommandEvent.DoesNotExist:
            initial = None
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per condannare a morte:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=VOTE, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class ElectView(CommandView):
    
    template_name = 'command_elect.html'
    
    def check(self, request):
        return request.player is not None and request.player.can_vote()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = game.get_alive_players()
        initial = None
        
        try:
            old_command = CommandEvent.objects.filter(turn=game.current_turn).filter(type=ELECT).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
        except CommandEvent.DoesNotExist:
            initial = None
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per eleggere:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=ELECT, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class PersonalInfoView(View):
    def get(self, request):
        
        if request.player is None:
            # TODO: fare qualcosa di piu' ragionevole, tipo reindirizzare alla pagina in cui l'amministratore puo' trasformarsi in un altro giocatore.
            return render(request, 'index.html')
        
        team = '-'
        role = '-'
        aura = '-'
        is_mystic = False
        status = '-'
        
        player = request.player.canonicalize()
        game = player.game
        # TODO : forse bisognerebbe fare dei controlli per verificare (tipo) che la partita sia in corso
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
        }
        
        return render(request, 'personal_info.html', context)
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(PersonalInfoView, self).dispatch(*args, **kwargs)


class ContactsView(ListView):
    
    model = Player
    
    template_name = 'contacts.html'
    
    # TODO: forse un giorno bisognerebbe filtrare con il Game giusto
    '''
    def get_queryset(self):
        return User.objects.filter(player__isnull=False)
    '''
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ContactsView, self).dispatch(*args, **kwargs)


# Form for changing point of view (for GM only)
class ChangePointOfViewForm(forms.Form):
    
    player = forms.ModelChoiceField(
                queryset=Player.objects.all(),
                empty_label='(Nessuno)',
                required=False,
                label='Scegli un giocatore:'
            )


# View for changing point of view (for GM only)
class PointOfView(View):
    def get(self, request):
        player = request.player
        form = ChangePointOfViewForm(initial={'player': player})
        return render(request, 'point_of_view.html', {'form': form, 'message': None})
    
    def post(self, request):
        player = request.player
        form = ChangePointOfViewForm(request.POST)
        
        if form.is_valid():
            player = form.cleaned_data['player']
            if player is not None:
                request.session['player_id'] = player.pk
            else:
                request.session['player_id'] = None
            
            # Metto il nuovo giocatore nella request corrente
            request.player = player
            
            form2 = ChangePointOfViewForm(initial={'player': player})
            return render(request, 'point_of_view.html', {'form': form, 'message': 'Punto di vista cambiato con successo'})
        else:
            return render(request, 'point_of_view.html', {'form': form, 'message': 'Scelta non valida'})
    
    @method_decorator(user_passes_test(is_GM_check))
    def dispatch(self, *args, **kwargs):
        return super(PointOfView, self).dispatch(*args, **kwargs)



