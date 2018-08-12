#!/usr/bin/python
# coding=utf8

from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
#from django.core.urlresolvers import reverse

from django.db.models import Q

from django.views import generic
from django.views.generic.base import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView
from django.views.generic.edit import CreateView

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.utils.decorators import method_decorator
from django.utils.text import slugify
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

from datetime import datetime, timedelta

from urllib.request import urlopen
import xml.etree.ElementTree as ET


def is_GM_check(user):
    # Checks that the user is a GM
    # FIXME: in many cases throughout the app, user.is_staff is checked (and not is_GM_check(user)).
    if not user.is_authenticated:
        return False
    return user.is_staff

def master_required(func):
    def decorator(request, *args, **kwargs):
        if request.is_master:
            return func(request, *args, **kwargs)
        else:
            return redirect('game:status',game_name=request.game.name)

    return decorator

def player_required(func):
    """Checks that the user is taking part in the current game. If s/he is not
    a game master, s/he must have been accepted in the game (that is, the game must
    be started)."""
    def decorator(request, *args, **kwargs):
        if request.is_master or (request.player and request.game.started):
            return func(request, *args, **kwargs)
        else:
            return redirect('game:status',game_name=request.game.name)

    return decorator

def can_access_admin_view(func):
    def decorator(request, *args, **kwargs):
        if request.is_master or (request.player and game.is_over and game.postgame_info):
            return func(request, *args, **kwargs)
        else:
            return redirect('game:status',game_name=request.game.name)

    return decorator
    
def get_events(request, player):
    # player can be a Player, 'admin' or 'public' (depending on the view)
    game = request.game
    dynamics = game.get_dynamics()
    assert not dynamics.simulating
    if player == 'admin':
        turns = dynamics.turns
        dynamics.update(simulation=True)
        if dynamics.simulated_turn is not None and dynamics.simulated:
            turns = turns + [dynamics.simulated_turn]
    else:
        turns = [turn for turn in dynamics.turns if turn.phase in [CREATION, DAWN, SUNSET]]
    
    if player == 'admin':
        events = dynamics.events + dynamics.simulated_events
    else:
        events = dynamics.events

    if player == 'admin':
        comments = Comment.objects.filter(turn__game=game).filter(visible=True).order_by('timestamp')
    else:
        comments = []

    result = dict([(turn, { 'standard': [], VOTE: {}, ELECT: {}, 'initial_propositions': [], 'soothsayer_propositions': [], 'comments': [] }) for turn in turns ])
    for event in events:
        message = event.to_player_string(player)
        if message is not None:
            assert event.turn in result.keys(), event.turn
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
        
        if event.subclass == 'InitialPropositionEvent':
            result[event.turn]['initial_propositions'].append(event.text)
        
        if event.subclass == 'RoleKnowledgeEvent' and event.cause == SOOTHSAYER and event.player == player:
            result[event.turn]['soothsayer_propositions'].append(event.to_soothsayer_proposition())
    
    for comment in comments:
        result[comment.turn]['comments'].append(comment)
    
    ordered_result = [ (turn, result[turn]) for turn in turns ]
    
    return ordered_result

def not_implemented(request):
    raise NotImplementedError("View not implemented")

def home(request):
    return render(request, 'index.html')

class SignUpForm(UserCreationForm):
    GENDERS = (
        ('M','Maschio'), ('F','Femmina')
    )
    first_name = forms.CharField(label='Nome')
    last_name = forms.CharField(label='Cognome')
    gender = forms.ChoiceField(label='Genere', choices=GENDERS)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'gender', 'password1', 'password2')

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = Profile(user=user)
            profile.save()
            user.refresh_from_db()  # load the profile instance created by the signal
            user.profile.gender = form.cleaned_data.get('gender')
            user.save()
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=user.username, password=raw_password)
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect(home)

def ruleset(request):
    return render(request, 'ruleset.html')

def credits(request):
    return render(request, 'credits.html')

def trailer(request):
    return render(request, 'trailer.html')

def prototypes(request):
    return render(request, 'prototypes.html')

def errorpage(request):
    return render(request, 'error.html')

class Weather:
    
    dtformat = '%Y-%m-%d %H:%M:%S'
    update_interval = timedelta(minutes=10)
    
    def __init__(self, stored_weather):
        if stored_weather is None:
            self.last_update = None
            
            #self.temperature = None
            #self.wind_direction = None
            #self.wind_speed = None
            self.description = None
        
        else:
            self.last_update = datetime.strptime( stored_weather['last_update'], self.dtformat )
            self.description = stored_weather['description']
    
    
    def stored(self):
        # Returns the dictionary to be stored in session
        res = {}
        res['last_update'] = self.last_update.strftime(self.dtformat)
        res['description'] = self.description
        
        return res
    
    def is_uptodate(self):
        # True if the weather was update recently
        now = datetime.strptime( get_now().strftime(self.dtformat), self.dtformat )
        return self.last_update is not None and now - self.last_update < self.update_interval
        
    
    def get_data(self):
        # Returns False if an actual update was performed
        if self.is_uptodate():
            return True
        
        # Fetching weather data from openweathermap.org
        url = 'http://api.openweathermap.org/data/2.5/weather?q=Pisa&mode=xml&APPID=a7956a78c44d8f1d55ce58ad08e0e2b3'
        # TODO: When publishing the code, make this configurable
        try:
            data = urllib2.urlopen(url, timeout = 3)
            rawdata = data.read()
            root = ET.fromstring(rawdata)
            self.description = int( root.find('weather').get('number') )
            #self.temperature = float( root.find('temperature').get('value') )
            #self.wind_direction = root.find('wind').find('direction').get('code')
            #self.wind_speed = float( root.find('wind').find('speed').get('value') )
            #self.sunrise = root.find('city').find('sun').get('rise')
            #self.sunset = root.find('city').find('sun').get('set')
        
        except Exception:
            self.description = None
        
        self.last_update = get_now()
        return False
    
    def weather_type(self):
        # see http://bugs.openweathermap.org/projects/api/wiki/Weather_Condition_Codes
        if self.description is None:
            return 'unknown'
        elif 300 <= self.description <= 321 or 500 == self.description:
            return 'light rain'
        elif 200 <= self.description <= 232 or 501 <= self.description <= 531:
            return 'heavy rain'
        elif 803 <= self.description <= 804 or 701 <= self.description <= 741:
            # 7** sarebbero nebbia o affini
            return 'cloudy'
        elif 800 <= self.description <= 802:
            return 'clear'
        else:
            return 'unknown'
    type = property(weather_type)
    
    def adjective(self):
        if self.type == 'light rain':
            return u'umid'
        elif self.type == 'heavy rain':
            return u'piovos'
        elif self.type == 'cloudy':
            return u'nuvolos'
        elif self.type == 'clear':
            return u'seren'
        else:
            return u'nuov'
    adjective = property(adjective)


def get_weather(request):
    stored_weather = request.session.get('weather', None)
    weather = Weather(stored_weather)
    uptodate = weather.get_data()
    if not uptodate:
        request.session['weather'] = weather.stored()
    return weather

class GameView(View):
    def dispatch(self, request, game_name, *args, **kwargs):
        #Do not pass game_name to view, because it's handled by the middleware
        return super().dispatch(request, *args, **kwargs)

# View of village status and public events
class VillageStatusView(GameView):
    def get(self, request):
        
        game = request.game
        if game is None:
            return redirect('home')
        
        if request.dynamics is None:
            return redirect('error')
        
        events = get_events(request, 'public')
        weather = get_weather(request)
        
        context = {
            'events': events,
            'weather': weather,
            'display_time': False
        }   
        return render(request, 'public_info.html', context)


# View of personal info and events
class PersonalInfoView(GameView):
    def get(self, request):
        
        if request.player is None:
            return redirect('pointofview')
        
        if request.dynamics is None:
            return redirect('error')
        
        player = request.player.canonicalize()
        game = player.game
        
        events = get_events(request, player)
        weather = get_weather(request)
        
        context = {
            'events': events,
            'weather': weather,
            'classified': True,
        }
        
        return render(request, 'personal_info.html', context)
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(PersonalInfoView, self).dispatch(*args, **kwargs)


# View of all info (for GM only)
class AdminStatusView(GameView):
    def get(self, request):
        events = get_events(request, 'admin')
        weather = get_weather(request)
        game = request.game

        context = {
            'events': events,
            'weather': weather,
            'classified': True,
            'display_time': True
        }

        return render(request, 'public_info.html', context)

    @method_decorator(can_access_admin_view)
    def dispatch(self, *args, **kwargs):
        return super(AdminStatusView, self).dispatch(*args, **kwargs)


# "Generic" form for submitting actions
class CommandForm(forms.Form):
    
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super(CommandForm, self).__init__(*args, **kwargs)
        
        # Create form fields in the following order.
        for key in ['target', 'target2', 'target_ghost']:
            if key in fields.keys():
                field = fields[key]
                
                if key == 'target' or key == 'target2':
                    choices = [ (None, '(Nessuno)') ]
                    choices.extend( [ (player.pk, player.full_name) for player in field['choices'] ] )
                elif key == 'target_ghost':
                    choices = [ (None, '(Nessuno)') ]
                    choices.extend( [ (power, POWER_NAMES[power]) for power in field['choices'] ] )
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
        
        for key, field in self.fields.items():
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



class CommandView(GameView):
    
    template_name = 'command.html'
    
    def check(self, request):
        # Checks if the action can be done
        raise Exception ('Command not specified.')
    
    def get_fields(self, request):
        # Returns a description of the fields required
        raise Exception ('Command not specified.')
    
    def not_allowed(self, request):
        return render(request, 'command_not_allowed.html', {'message': 'Non puoi eseguire questa azione.', 'title': self.title, 'classified': True})
    
    def submitted(self, request):
        return render(request, 'command_submitted.html', {'title': self.title, 'classified': True})
    
    def save_command(self, request, cleaned_data):
        # Validates the form data and possibly saves the command, returning True in case of success and False otherwise
        raise Exception ('Command not specified.')
    
    def post(self, request):
        if request.dynamics is None:
            return redirect('error')
        
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(request.POST, fields=self.get_fields(request))
        if form.is_valid():
            if self.save_command(request, form.cleaned_data):
                return self.submitted(request)
            else:
                return render(request, 'command_not_allowed.html', {'message': 'La scelta effettuata non è valida.', 'classified': True})
        else:
            return render(request, self.template_name, {'form': form, 'classified': True})
    
    def get(self, request):
        if request.player is None:
            return redirect('pointofview')
        
        if request.dynamics is None:
            return redirect('error')
        
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(fields=self.get_fields(request))
        context = {
            'form': form,
            'title': self.title,
            'url_name': self.url_name,
            'classified': True,
        }
        return render(request, self.template_name, context)
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CommandView, self).dispatch(*args, **kwargs)


class UsePowerView(CommandView):
    
    title = 'Potere notturno'
    url_name = 'game:usepower'
    
    def check(self, request):
        return request.player is not None and request.player.can_use_power()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        role = player.role
        
        targets = role.get_targets()
        targets2 = role.get_targets2()
        targets_ghost = role.get_targets_ghost()
        
        initial = role.recorded_target
        initial2 = role.recorded_target2
        initial_ghost = role.recorded_target_ghost
        
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
        
        if target == '':
            target = None
        
        if target is not None and not target in targets:
            return False
        
        if targets2 is not None:
            target2 = cleaned_data['target2']
            if target2 == '':
                target2 = None
            if not target2 in targets2 and target is not None:
                # If target2 is not valid (or None), make the command not valid
                # unless target is None (which means that the power will not be used)
                return False
        
        if targets_ghost is not None:
            target_ghost = cleaned_data['target_ghost']
            if target_ghost == '':
                target_ghost = None
            if not target_ghost in targets_ghost and target is not None:
                # If target_ghost is not valid (or None), make the command not valid
                # unless target is None (which means that the power will not be used)
                return False
        
        # If target is None, then the other fields are set to None
        if target is None:
            target2 = None
            target_ghost = None
        
        command = CommandEvent(player=player, type=USEPOWER, target=target, target2=target2, target_ghost=target_ghost, turn=player.game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=request.current_turn):
            return False
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class VoteView(CommandView):
    
    title = 'Votazione per il rogo'
    url_name = 'game:vote'
    
    def check(self, request):
        return request.player is not None and request.player.can_vote()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = game.get_alive_players()
        initial = player.recorded_vote
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per condannare a morte:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target == '':
            target = None
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=VOTE, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=request.current_turn):
            return False
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class ElectView(CommandView):
    
    title = 'Elezione del Sindaco'
    url_name = 'game:elect'
    
    def check(self, request):
        return request.player is not None and request.player.can_vote()
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = game.get_alive_players()
        initial = player.recorded_elect
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per eleggere:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target == '':
            target = None
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=ELECT, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=request.current_turn):
            return False
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


# View for appointing a successor (for mayor only)
class AppointView(CommandView):
    
    title = 'Nomina del successore'
    url_name = 'game:appoint'
    
    def check(self, request):
        return request.player is not None and request.player.is_mayor() and request.game is not None and (request.game.current_turn.phase == DAY or request.game.current_turn.phase == NIGHT)
    
    def get_fields(self, request):
        player = request.player
        game = player.game
        choices = [p for p in game.get_alive_players() if p.pk != player.pk]
        initial = game.get_dynamics().appointed_mayor
        
        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Designa come successore:'} }
        return fields
    
    def save_command(self, request, cleaned_data):
        player = request.player
        game = player.game
        target = cleaned_data['target']
        
        if target == '':
            target = None
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        if target is not None and target == player:
            return False
        
        command = CommandEvent(player=player, type=APPOINT, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=request.current_turn):
            return False
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True

class ContactsView(GameView):
    def get(self, request):
        return render(request, 'contacts.html', {})

    @method_decorator(player_required)
    def dispatch(self, *args, **kwargs):
        return super(ContactsView, self).dispatch(*args, **kwargs)


class AnnouncementsView(ListView):
    model = Announcement
    template_name = 'announcements.html'
    
    def get_queryset(self):
        game = Game.get_running_game()
        return Announcement.objects.filter(game=game).filter(visible=True).order_by('-timestamp')

class CreateGameView(CreateView):
    model = Game
    fields = ['name', 'description']
    template_name = 'create_game.html'

    def form_valid(self, form):
        player = self.request.player
        user = self.request.user

        game_name = slugify(form.cleaned_data['name'])
        description = form.cleaned_data['description']
        (game, created) = Game.objects.get_or_create(name=game_name, description=description)
        if created:
            game.initialize(get_now())
            master = GameMaster(user=user,game=game)
            master.save()
            return redirect('game:settings', game_name=game_name)
        else:
            return render(self.request, 'create_game.html', {'form': form, 'message': 'Nome già in uso.'})

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CreateGameView, self).dispatch(*args, **kwargs)

class GameSettingsForm(forms.Form):
    WEEKDAYS = [(0,'Lunedì'), (1,'Martedì'), (2,'Mercoledì'), (3,'Giovedì'), (4,'Venerdì'), (5,'Sabato'), (6,'Domenica')]
    day_end_weekdays = forms.MultipleChoiceField(choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple, label='Sere in cui finisce il giorno', required=True)
    day_end_time = forms.TimeField(label='Ora del tramonto')
    night_end_time = forms.TimeField(label='Ora dell\'alba')
    half_phase_duration = forms.IntegerField(label='Durata di alba e tramonto (in secondi)')
    public = forms.BooleanField(label='Pubblica partita', required=False)
    postgame_info = forms.BooleanField(label='Mostra tutte le informazioni al termine della partita', required=False)

class GameSettingsView(GameView):
    def get(self, request):
        player = request.player
        game = request.game
        form = GameSettingsForm(initial={
            'day_end_weekdays': game.get_day_end_weekdays(),
            'day_end_time':game.day_end_time,
            'night_end_time':game.night_end_time,
            'half_phase_duration': game.half_phase_duration,
            'public':game.public,
            'postgame_info':game.postgame_info
        })
        return render(request, 'settings.html', {'form': form, 'message': None, 'classified': True})
    
    def post(self, request):
        game = request.game
        form = GameSettingsForm(request.POST)

        if form.is_valid():
            game.day_end_time = form.cleaned_data['day_end_time']
            game.night_end_time = form.cleaned_data['night_end_time']
            game.day_end_weekdays = sum([ 2**int(i) for i in form.cleaned_data['day_end_weekdays']])
            game.half_phase_duration = form.cleaned_data['half_phase_duration']
            game.public = form.cleaned_data['public']
            game.postgame_info = form.cleaned_data['postgame_info']
            game.save()

            current_turn = game.current_turn
            if current_turn.end is not None:
                current_turn.set_end(allow_retroactive_end=False)
                current_turn.save()

            form = GameSettingsForm(initial={
                'day_end_weekdays': game.get_day_end_weekdays(),
                'day_end_time': game.day_end_time,
                'night_end_time': game.night_end_time,
                'half_phase_duration': game.half_phase_duration,
                'public': game.public,
                'postgame_info': game.postgame_info
            })
            return render(request, 'settings.html', {'form': form, 'message': 'Impostazioni aggiornate correttamente.'})
        else:
            return render(request, 'settings.html', {'form': form, 'message': 'Scelta non valida.'})
    
    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(GameSettingsView, self).dispatch(*args, **kwargs)

class JoinGameView(GameView):
    title = 'Unisciti al villaggio'
    def can_join(self, request):
        game = request.game
        dynamics = game.get_dynamics()
        dynamics.update()
        subphase = dynamics.creation_subphase
        return request.player is None and not request.is_master and subphase == SIGNING_UP

    def get(self, request):
        if self.can_join(request):
            return render(request, 'confirm.html', {
                'title': self.title,
                'message': 'Vuoi davvero partecipare a ' + request.game.description + '?'
            })
        else:
            return render(request, 'command_not_allowed.html', {
                'message': 'Non puoi unirti al villaggio.', 
                'title': self.title
            })

    def post(self, request):
        game = request.game
        user = request.user
        if self.can_join(request):
            player = Player.objects.create(game=game, user=user)
            player.save()
            # Kill dynamics to refresh players list
            game.kill_dynamics()
        return redirect('game:status', game_name=request.game.name)

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(JoinGameView, self).dispatch(*args, **kwargs)

class LeaveGameView(GameView):
    title = 'Abbandona il villaggio'
    def can_leave(self, request):
        game = request.game
        dynamics = game.get_dynamics()
        dynamics.update()
        subphase = dynamics.creation_subphase
        return request.player is not None and subphase == SIGNING_UP

    def get(self, request):
        if self.can_leave(request):
            return render(request, 'confirm.html', {
                'title': self.title,
                'message': 'Vuoi davvero abbandonare la partita?'
            })
        else:
            return render(request, 'command_not_allowed.html', {
                'message': 'Non puoi abbandonare il villaggio.', 
                'title': self.title
            })

    def post(self, request):
        game = request.game
        user = request.user
        player = request.player
        if self.can_leave(request):
            player.canonicalize().delete()
            # Kill dynamics to refresh players list
            game.kill_dynamics()
        return redirect('game:status', game_name=request.game.name)

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LeaveGameView, self).dispatch(*args, **kwargs)

class RollbackLastTurnView(GameView):
    title = "Annulla ultimo turno"
    def get(self, request):
        return render(request, 'confirm.html', {
            'message': 'Sei sicuro di voler tornare al turno precedente? Questo cancellerà definitivamente tutti gli eventi del turno corrente.',
            'title': self.title })

    def post(self, request):
        game = request.game
        current_turn = game.current_turn
        prev_turn = current_turn.prev_turn()
        prev_turn.end = None
        prev_turn.save()
        current_turn.delete()
        game.kill_dynamics()
        return redirect('game:status', game_name=game.name)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(RollbackLastTurnView, self).dispatch(*args, **kwargs)

class RestartGameView(GameView):
    def get(self, request):
        return render(request, 'confirm.html', {'message': 'Sei sicuro di voler ricominciare la partita? Questa azione non può essere annullata.', 'title': 'Azzera partita'})

    def post(self, request):
        game = request.game
        dynamics = game.get_dynamics()
        Turn.objects.filter(game=game).delete()
        game.kill_dynamics()
        game.initialize(get_now())
        return redirect('game:status', game_name=game.name)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(RestartGameView, self).dispatch(*args, **kwargs)

class SetupGameView(GameView):
    def get(self, request):
        game = request.game
        dynamics = game.get_dynamics()
        dynamics.update()
        subphase = dynamics.creation_subphase
        
        SETUP_PAGES = {
            SIGNING_UP: 'game:seed',
            CHOOSING_ROLES: 'game:composition',
            SOOTHSAYING: 'game:soothsayer',
            PUBLISHING_INFORMATION: 'game:propositions',
        }

        return redirect(SETUP_PAGES[subphase], game_name=game.name)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(SetupGameView, self).dispatch(*args, **kwargs)

class SeedForm(forms.Form):
    excluded_players = forms.ModelMultipleChoiceField(
        queryset = Player.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Giocatori da escludere:',
        required=False
    )
    seed = forms.IntegerField(required=True, label='Seed')
    RULESETS = [
        ('three_teams', 'Regole con tre fazioni')
    ]
    ruleset = forms.ChoiceField(choices=RULESETS)

    def __init__(self, *args, **kwargs):
        game = kwargs.pop('game', None)
        super(SeedForm, self).__init__(*args, **kwargs)
        self.fields['excluded_players'].queryset = Player.objects.filter(game=game)

class SeedView(GameView):
    def get(self, request):
        game = request.game
        form = SeedForm(game=game)
        return render(request, 'seed.html', {'form': form, 'message': None, 'classified': True})

    def post(self, request):
        game = request.game
        form = SeedForm(request.POST)
        if form.is_valid():
            excluded_players = form.cleaned_data['excluded_players']
            excluded_players.delete()
            game.initialize(get_now())
            dynamics = game.get_dynamics()
            first_turn = dynamics.current_turn

            event = SeedEvent(seed=str(form.cleaned_data['seed']))
            event.timestamp = get_now()
            dynamics.inject_event(event)

            event = SetRulesEvent(ruleset=form.cleaned_data['ruleset'])
            event.timestamp = get_now()
            dynamics.inject_event(event)

            return redirect('game:setup', game_name=game.name)
        else:
            return render(request, 'seed.html', {'form': form, 'message': 'Scelta non valida', 'classified': True})

class VillageCompositionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super(VillageCompositionForm, self).__init__(*args, **kwargs)
        dynamics = self.game.get_dynamics()
        assert dynamics.creation_subphase == CHOOSING_ROLES

        for role in dynamics.starting_roles:
            self.fields[role.__name__] = forms.IntegerField(label=role.full_name, min_value=0, initial=0)

    def clean(self):
        dynamics = self.game.get_dynamics()
        cleaned_data = super().clean()
        count = 0
        for role in dynamics.starting_roles:
            count += cleaned_data.get(role.__name__)

        if count != len(dynamics.players):
            raise forms.ValidationError(
                'Sono stati selezionati %(roles)s ruoli, mentre partecipano %(players)s giocatori.',
                params = {'roles': count, 'players': len(dynamics.players)}
            )

class VillageCompositionView(GameView):
    def get(self, request):
        game = request.game
        form = VillageCompositionForm(game=game)
        return render(request, 'composition.html', {'form': form, 'message': None, 'classified': True})

    def post(self, request):
        game = request.game
        form = VillageCompositionForm(request.POST, game=game)
        if form.is_valid():
            dynamics = game.get_dynamics()
            
            roles = dynamics.starting_roles
            for role in roles:
                for i in range(form.cleaned_data[role.__name__]):
                    event = AvailableRoleEvent(role_name = role.__name__)
                    event.timestamp = get_now()
                    dynamics.inject_event(event)

            return redirect('game:setup', game_name=game.name)
        else:
            return render(request, 'composition.html', {'form': form, 'message': 'Scelta non valida', 'classified': True})

class InitialPropositionsForm(forms.Form):
    propositions = forms.CharField(widget=forms.Textarea())

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super(InitialPropositionsForm, self).__init__(*args, **kwargs)
        dynamics = self.game.get_dynamics()
        assert dynamics.creation_subphase == PUBLISHING_INFORMATION

class InitialPropositionsView(GameView):
    def get(self, request):
        game = request.game
        form = InitialPropositionsForm(game=game)
        return render(request, 'propositions.html', {'form': form, 'message': None, 'classified': True})

    def post(self, request):
        game = request.game
        form = InitialPropositionsForm(request.POST, game=game)
        if form.is_valid():
            dynamics = game.get_dynamics()
            
            for line in form.cleaned_data['propositions'].splitlines():
                event = InitialPropositionEvent(turn=dynamics.current_turn, timestamp=get_now(), text=line)
                dynamics.inject_event(event)

            turn = game.current_turn
            turn.end = get_now()
            turn.save()
            game.advance_turn()
            return redirect('game:status', game_name=request.game.name)
        else:
            return render(request, 'propositions.html', {'form': form, 'message': 'Scelta non valida', 'classified': True})

class AdvanceTurnView(GameView):
    title = 'Turno successivo'
    def get(self, request):
        game = request.game
        if game.is_over:
            return render(request, 'command_not_allowed.html', {
                'message': 'Non puoi avanzare al prossimo turno in quanto la partita è finita.',
                'title': self.title
            })
        else:
            return render(request, 'confirm.html', {
                'message': 'Sei sicuro di voler avanzare immediatamente al prossimo turno?', 
                'title': self.title
            })

    def post(self, request):
        game = request.game
        turn = game.current_turn
        if not game.is_over:
            turn.end = get_now()
            turn.save()
        return redirect('game:status', game_name=request.game.name)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(AdvanceTurnView, self).dispatch(*args, **kwargs)



# Form for changing point of view (for GMs only)
class ChangePointOfViewForm(forms.Form):
    player = forms.ModelChoiceField(
                queryset=Player.objects.select_related('user').all(),
                empty_label='(Nessuno)',
                required=False,
                label='Scegli un giocatore:'
            )


# View for changing point of view (for GMs only)
class PointOfView(GameView):
    def get(self, request):
        player = request.player
        form = ChangePointOfViewForm(initial={'player': player})
        return render(request, 'point_of_view.html', {'form': form, 'message': None, 'classified': True})
    
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
            return render(request, 'point_of_view.html', {'form': form, 'message': 'Punto di vista cambiato con successo', 'classified': True})
        else:
            return render(request, 'point_of_view.html', {'form': form, 'message': 'Scelta non valida', 'classified': True})
    
    @method_decorator(user_passes_test(is_GM_check))
    def dispatch(self, *args, **kwargs):
        return super(PointOfView, self).dispatch(*args, **kwargs)


class CommentForm(forms.Form):
    text = forms.CharField(widget=forms.Textarea, label='', max_length=4096)

class CommentView(GameView):
    max_comments_per_turn = 100
    
    def can_comment(self, request):
        # Checks if the user can post a comment
        user = request.user
        game = request.game
        current_turn = game.current_turn
        
        if is_GM_check(user):
            return True
        
        try:
            comments_number = Comment.objects.filter(user=user).filter(turn=current_turn).count()
            if comments_number >= self.max_comments_per_turn:
                return False
            else:
                return True
        
        except IndexError:
            return True

    def get(self, request):
        user = request.user
        game = request.game
        form = CommentForm()
        old_comments = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp')
        can_comment = self.can_comment(request)
        return render(request, 'comment.html', {'form': form, 'old_comments': old_comments, 'can_comment': can_comment, 'classified': True})
    
    def post(self, request):
        form = CommentForm(request.POST)
        user = request.user
        game = request.game
        current_turn = game.current_turn
        
        if form.is_valid() and self.can_comment(request):
                text = form.cleaned_data['text']
                comment = Comment(turn=game.current_turn, user=user, text=text)
                comment.save()
                return redirect('comment')
       
        old_comments = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp')
        can_comment = self.can_comment(request)
        return render(request, 'comment.html', {'form': form, 'old_comments': old_comments, 'can_comment': can_comment, 'classified': True})
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CommentView, self).dispatch(*args, **kwargs)


# Dump view (for GM only)
class DumpView(GameView):
    def get(self, request):
        game = request.game
        response = HttpResponse(content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = 'attachment: filename="dump.json"'
        dump_game(game, response)
        return response
    
    @method_decorator(user_passes_test(is_GM_check))
    def dispatch(self, *args, **kwargs):
        return super(DumpView, self).dispatch(*args, **kwargs)
