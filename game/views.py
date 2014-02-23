from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse

from django.db.models import Q

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
from game.letter_renderer import LetterRenderer

from datetime import datetime

import urllib
import xml.etree.ElementTree as ET


def is_GM_check(user):
    # Checks that the user is a GM
    if not user.is_authenticated():
        return False
    return user.is_staff


def get_events(request, player):
    # player can be a Player, 'admin' or 'public' (depending on the view)
    game = request.game
    
    if player == 'admin':
        turns = Turn.objects.filter(game=game)
    else:
        turns = Turn.objects.filter(game=game).filter( Q(phase=CREATION) | Q(phase=DAWN) | Q(phase=SUNSET) )
    
    events = Event.objects.filter(turn__game=game)
    
    result = { turn: { 'standard': [], VOTE: {}, ELECT: {} } for turn in turns }
    
    for e in events:
        event = e.as_child()
        message = event.to_player_string(player)
        if message is not None:
            result[event.turn]['standard'].append(message)
        
        if event.subclass == 'VoteAnnouncedEvent':
            if event.voted not in result[event.turn][event.type]:
                result[event.turn][event.type][event.voted] = { 'votes': 0, 'voters': [] }
            
            result[event.turn][event.type][event.voted]['voters'].append(event.voter)
        
        if event.subclass == 'TallyAnnouncedEvent':
            if event.voted not in result[event.turn][event.type]:
                # This shouldn't happen if VoteAnnounvedEvents come before TallyAnnouncedEvents
                result[event.turn][event.type][event.voted] = { 'votes': 0, 'voters': [] }
            
            result[event.turn][event.type][event.voted]['votes'] = event.vote_num
    
    return result



def home(request):
    return render(request, 'index.html')


def logout_view(request):
    logout(request)
    return redirect(home)


@user_passes_test(is_GM_check)
def setup(request):
    setup_game(get_now())
    return render(request, 'index.html')


@user_passes_test(is_GM_check)
def create_letters(request):
    game = request.game
    players = game.get_players()
    for player in players:
        lr = LetterRenderer(player)
        lr.render_all()
    return render(request, 'index.html')


@user_passes_test(is_GM_check)
def advance_turn(request):
    game = request.game
    turn = game.current_turn
    turn.end = get_now()
    turn.save()
    game.advance_turn()
    return render(request, 'index.html')


def ruleset(request):
    return render(request, 'ruleset.html')



class Weather:
    def __init__(self):
        self.temperature = None
        self.wind_direction = None
        self.wind_speed = None
        self.weather = None
    
    def get(self):
        # Fetching weather data from openweathermap.org
        url = 'http://api.openweathermap.org/data/2.5/weather?q=Pisa&mode=xml'
        u = urllib.FancyURLopener(None)
        usock = u.open(url)
        rawdata = usock.read()
        usock.close()
        root = ET.fromstring(rawdata)
        
        self.temperature = float( root.find('temperature').get('value') )
        self.wind_direction = root.find('wind').find('direction').get('code')
        self.wind_speed = float( root.find('wind').find('speed').get('value') )
        self.weather = int( root.find('weather').get('number') )
        # sunrise = root.find('city').find('sun').get('rise')
        # sunset = root.find('city').find('sun').get('set')
    
    def weather_type(self):
        # see http://bugs.openweathermap.org/projects/api/wiki/Weather_Condition_Codes
        if self.weather is None:
            return 'Unknown'
        if 200 <= self.weather <= 232:
            return 'Thunderstorm'
        elif 500 <= self.weather <= 531:
            return 'Rain'
        elif 802 <= self.weather <= 804:
            return 'Clouds'
        elif 800 <= self.weather <= 801:
            return 'Clear'
        else:
            return 'Unknown'
    type = property(weather_type)


# View of village status
class VillageStatusView(View):
    def get(self, request):
        
        game = request.game
        
        if game is not None:
            date = game.current_turn.date
            phase = game.current_turn.phase_as_italian_string()
            alive_players = game.get_alive_players()
            dead_players = game.get_dead_players()
            inactive_players = game.get_inactive_players()
            mayor = game.mayor()
            
        else:
            alive_players = None
            dead_players = None
            inactive_players = None
            mayor = None
        
        weather = Weather()
        weather.get()
        
        context = {
            'alive_players': alive_players,
            'dead_players': dead_players,
            'inactive_players': inactive_players,
            'mayor': mayor,
            'weather': weather,
        }   
        return render(request, 'status.html', context)


# View of public events
class PublicEventsView(View):
    def get(self, request):
        events = get_events(request, 'public')
        context = {'events': events}
        return render(request, 'public_events.html', context)


# "Generic" form for submitting actions
class CommandForm(forms.Form):
    
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
            fields['target'] = {'choices': targets, 'initial': initial, 'label': role.message}
        if targets2 is not None:
            fields['target2'] = {'choices': targets2, 'initial': initial2, 'label': role.message2}
        if targets_ghost is not None:
            fields['target_ghost'] = {'choices': targets_ghost, 'initial': initial_ghost, 'label': role.message_ghost}
        
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


# View for appointing a successor (for mayor only)
class AppointView(CommandView):
    
    template_name = 'command_appoint.html'
    
    def check(self, request):
        return request.player is not None and request.player.is_mayor
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = [p for p in game.get_alive_players() if p.pk != player.pk]
        initial = None
        
        try:
            # FIXME: se il sindaco muore, resuscita e poi viene nominato di nuovo sindaco,
            # compare come designato l'ultimo giocatore che aveva designato
            old_command = CommandEvent.objects.filter(type=APPOINT).filter(player=player).order_by('-pk')[0:1].get()
            initial = old_command.target
        except CommandEvent.DoesNotExist:
            initial = None
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Designa come successore:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        if target is not None and target == player:
            return False
        
        command = CommandEvent(player=player, type=APPOINT, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True




class PersonalInfoView(View):
    def get(self, request):
        
        if request.player is None:
            # TODO: fare qualcosa di piu' ragionevole, tipo reindirizzare alla pagina in cui l'amministratore puo' trasformarsi in un altro giocatore.
            return render(request, 'index.html')
        
        player = request.player.canonicalize()
        game = player.game
        # TODO : forse bisognerebbe fare dei controlli per verificare (tipo) che la partita sia in corso
        
        events = get_events(request, player)
        
        context = {
            'events': events,
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


# Form for changing point of view (for GMs only)
class ChangePointOfViewForm(forms.Form):
    
    player = forms.ModelChoiceField(
                queryset=Player.objects.all(),
                empty_label='(Nessuno)',
                required=False,
                label='Scegli un giocatore:'
            )


# View for changing point of view (for GMs only)
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



