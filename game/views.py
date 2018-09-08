#!/usr/bin/python
# coding=utf8

from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django.db.models import Q

from django.views import generic
from django.views.generic.base import View
from django.views.generic.base import TemplateView
from django.views.generic import ListView
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView

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


def is_staff_check(user):
    # Checks that the user is an admin
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
    user = request.user
    if user.is_authenticated:
        games = Game.objects.filter(
            Q(pk__in=user.player_set.values('game')) |
            Q(pk__in=user.gamemaster_set.values('game')) |
            Q(public=True))
    else:
        games = Game.objects.filter(public=True)
    
    # Remove failed games
    games = [g for g in games if g.get_dynamics() is not None]

    beginning_games = [g for g in games if not g.started]
    ongoing_games = [g for g in games if g.started and not g.is_over]
    ended_games = [g for g in games if g.is_over]

    context = {
        'beginning_games': beginning_games,
        'ongoing_games': ongoing_games,
        'ended_games': ended_games,
    }
    return render(request, 'index.html', context)

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

@user_passes_test(is_staff_check)
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = Profile(user=user)
            profile.save()
            user.refresh_from_db()  # load the profile instance created by the signal
            user.profile.gender = form.cleaned_data.get('gender')
            user.profile.save()
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

class GameFormView(FormView):
    # Pass game_name to success_url
    def get_success_url(self):
        return reverse(self.success_url, kwargs={'game_name': self.request.game.name})

    # Pass game to form as kwarg
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'game': self.request.game})
        return kwargs

# Generic view for deleting an event (will respawn dynamics)
class EventDeleteView(DeleteView):
    def get_success_url(self):
        return reverse(self.success_url, kwargs={'game_name': self.request.game.name})

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        request.game.kill_dynamics()
        return response

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
            return redirect('game:pointofview', game_name=request.game.name)
        
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
            return redirect('game:pointofview', game_name=request.game.name)
        
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


# Views to acquire or release GM powers
@login_required
def as_gm(request, game_name):
    request.session['as_gm'] = True
    return redirect('game:status', game_name=game_name)

@login_required
def as_normal_user(request, game_name):
    request.session['as_gm'] = False
    return redirect('game:status', game_name=game_name)

# Generic view to confirm execution of command
class ConfirmForm(forms.Form):
    current_turn_pk = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        self.current_turn = kwargs.pop('current_turn', None)
        super().__init__(*args, **kwargs)
        self.initial['current_turn_pk'] = self.current_turn.pk

    def clean(self):
        current_turn = self.game.get_current_turn(for_update=True)
        cleaned_data = super().clean()
        if current_turn.pk != cleaned_data.get('current_turn_pk'):
            raise forms.ValidationError(
                'L\'azione è stata annullata in quanto il turno corrente è cambiato.'
            )

class ConfirmView(GameFormView):
    form_class = ConfirmForm
    template_name = 'confirm.html'
    message = None
    title = None

    def get_message(self):
        return self.message

    def get_title(self):
        return self.title

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'current_turn': self.request.current_turn
        })
        return kwargs

    def can_execute_action(self):
        return True

    def not_allowed(self):
        return render(self.request, 'command_not_allowed.html', {'message': 'Non puoi eseguire questa azione.', 'title': self.title})

    def get(self, *args, **kwargs):
        if self.can_execute_action():
            return super().get(*args, **kwargs)
        else:
            return self.not_allowed()

    @transaction.atomic
    def post(self, *args, **kwargs):
        if self.can_execute_action():
            return super().post(self, *args, **kwargs)
        else:
            return self.not_allowed()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context.update({
            'message': self.get_message,
            'title': self.get_title,
        })
        return context


# View for creating a new Game
class CreateGameView(CreateView):
    model = Game
    fields = ['name', 'title', 'description']
    template_name = 'create_game.html'

    def get_form(self):
        form = super(CreateGameView, self).get_form()
        form.fields['description'].widget = forms.Textarea()
        return form

    def form_valid(self, form):
        player = self.request.player
        user = self.request.user

        game_name = slugify(form.cleaned_data['name'])
        title = form.cleaned_data['title']
        description = form.cleaned_data['description']
        (game, created) = Game.objects.get_or_create(name=game_name, title=title, description=description)
        if created:
            game.initialize(get_now())
            master = GameMaster(user=user,game=game)
            master.save()
            return redirect('game:settings', game_name=game_name)
        else:
            return render(self.request, 'create_game.html', {'form': form, 'message': 'Nome già in uso.'})

    @method_decorator(user_passes_test(is_staff_check))
    def dispatch(self, *args, **kwargs):
        return super(CreateGameView, self).dispatch(*args, **kwargs)


# View for changing Game Settings
class GameSettingsForm(forms.Form):
    WEEKDAYS = [(0,'Lunedì'), (1,'Martedì'), (2,'Mercoledì'), (3,'Giovedì'), (4,'Venerdì'), (5,'Sabato'), (6,'Domenica')]
    day_end_weekdays = forms.MultipleChoiceField(choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple, label='Sere in cui finisce il giorno', required=True)
    day_end_time = forms.TimeField(label='Ora del tramonto')
    night_end_time = forms.TimeField(label='Ora dell\'alba')
    half_phase_duration = forms.IntegerField(label='Durata di alba e tramonto (in secondi)')
    public = forms.BooleanField(label='Pubblica partita', required=False)
    postgame_info = forms.BooleanField(label='Mostra tutte le informazioni al termine della partita', required=False)
    auto_advancing = forms.BooleanField(label='Abilita l\'avanzamento automatico per il turno corrente', required=False)

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super().__init__(*args, **kwargs)
        self.initial.update({
            'day_end_weekdays': self.game.get_day_end_weekdays(),
            'day_end_time': self.game.day_end_time,
            'night_end_time': self.game.night_end_time,
            'half_phase_duration': self.game.half_phase_duration,
            'public': self.game.public,
            'postgame_info': self.game.postgame_info,
            'auto_advancing': self.game.current_turn.end is not None,
        })

@method_decorator(master_required, name='dispatch')
class GameSettingsView(GameFormView):
    form_class = GameSettingsForm
    template_name = 'settings.html'

    def form_valid(self, form):
        game = self.request.game
        game.day_end_time = form.cleaned_data['day_end_time']
        game.night_end_time = form.cleaned_data['night_end_time']
        game.day_end_weekdays = sum([ 2**int(i) for i in form.cleaned_data['day_end_weekdays']])
        game.half_phase_duration = form.cleaned_data['half_phase_duration']
        game.public = form.cleaned_data['public']
        game.postgame_info = form.cleaned_data['postgame_info']
        game.save()

        with transaction.atomic():
            current_turn = game.get_current_turn(for_update=True)
            if form.cleaned_data['auto_advancing'] and not game.is_over:
                current_turn.set_end(allow_retroactive_end=False)
            else:
                current_turn.end = None
            current_turn.save()

        game.kill_dynamics()
        form = self.form_class(game=game)
        return render(self.request, self.template_name, {'form': form, 'message': 'Impostazioni aggiornate correttamente.'})

# View to join a game
@method_decorator(login_required, name='dispatch')
class JoinGameView(ConfirmView):
    title = 'Unisciti al villaggio'
    success_url = 'game:status'

    def get_message(self):
        return 'Vuoi davvero partecipare a ' + self.request.game.title + '?'

    def can_execute_action(self):
        game = self.request.game
        dynamics = game.get_dynamics()
        dynamics.update()
        return self.request.player is None and not self.request.is_master and not game.started

    def form_valid(self, form):
        game = self.request.game
        user = self.request.user
        player = Player.objects.create(game=self.request.game, user=self.request.user)
        player.save()
        # Kill dynamics to refresh players list
        game.kill_dynamics()
        return super().form_valid(form)


# ... and to leave it
@method_decorator(login_required, name='dispatch')
class LeaveGameView(ConfirmView):
    title = 'Abbandona il villaggio'
    message = 'Vuoi davvero abbandonare la partita?'
    success_url = 'game:status'

    def can_execute_action(self):
        self.request.game.get_dynamics().update()
        return self.request.player is not None and not self.request.game.started

    def form_valid(self, form):
        game = self.request.game
        user = self.request.user
        player = self.request.player
        player.canonicalize().delete()
        # Kill dynamics to refresh players list
        game.kill_dynamics()
        return super().form_valid(form)

# View for creating a new User and signing him to the Game
class NewPlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        labels = {
            'username': 'Username',
            'first_name': 'Nome',
            'last_name': 'Cognome',
            'email': 'E-mail'
        }
        help_texts = {
            'username': ''
        }

    GENDERS = (
        ('M','Maschio'), ('F','Femmina')
    )
    gender = forms.ChoiceField(label='Genere', choices=GENDERS)

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username

        raise forms.ValidationError("L'utente selezionato esiste già.")

    def __init__(self, **kwargs):
        self.game = kwargs.pop('game')
        return super().__init__(**kwargs)

@method_decorator([user_passes_test(is_staff_check), registrations_open], name='dispatch')
class NewPlayerView(GameFormView):
    form_class = NewPlayerForm
    template_name = 'new_player.html'
    success_url = 'game:status'

    def form_valid(self, form):
        user = form.save(commit=False)
        user.password = User.objects.make_random_password()
        user.save()
        profile = Profile(user=user)
        profile.gender = form.cleaned_data.get('gender')
        profile.save()
        player = Player(game=self.request.game, user=user)
        player.save()
        self.request.game.kill_dynamics()
        return super().form_valid(form)

# View to add or remove masters
class ManageGameMastersForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=User.objects.all(), to_field_name='username', widget=forms.TextInput())
    class Meta:
        model = GameMaster
        fields = ['user']

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super(ManageGameMastersForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if GameMaster.objects.filter(game=self.game, user=cleaned_data.get('user', None)).exists():
            raise forms.ValidationError('L\'utente è già master della partita.')
        return cleaned_data

class ManageGameMastersView(CreateView):
    form_class = ManageGameMastersForm
    template_name = 'manage_masters.html'

    def get_success_url(self):
        return reverse( 'game:managemasters', kwargs={'game_name': self.request.game.name})

    def get_masters(self):
        return GameMaster.objects.filter(game=self.request.game)

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs.update({ 'game': self.request.game })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'masters': self.get_masters()
        })
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.game = self.request.game
        return super().form_valid(form)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(ManageGameMastersView, self).dispatch(*args, **kwargs)


class DeleteGameMasterView(GameView):
    def get(self, request, pk):
        game = request.game
        obj = GameMaster.objects.get(pk=pk)
        if request.is_master and request.game==obj.game and len(game.masters) > 1:
            obj.delete()
        return redirect('game:managemasters', game_name=request.game.name)

# View for advancing turn
@method_decorator(master_required, name='dispatch')
class AdvanceTurnView(ConfirmView):
    title = 'Turno successivo'
    success_url = 'game:status'

    def get_message(self):
        next_turn = self.request.current_turn.next_turn()
        return 'Vuoi davvero avanzare %s%s?' % (next_turn.preposition_to_as_italian_string(), next_turn.turn_as_italian_string())

    def can_execute_action(self):
        return not self.request.game.is_over

    def form_valid(self, form):
        game = self.request.game
        turn = game.get_current_turn(for_update=True)
        # Check if turns were advancing manually
        manual_advance = turn.end is None
        turn.end = get_now()
        turn.save()
        game.get_dynamics().update()
        new_turn = game.get_current_turn(for_update=True)
        assert new_turn.phase == turn.next_turn().phase
        if manual_advance:
            new_turn.end = None
            new_turn.save()

        return super().form_valid(form)


# View to return to previous turn
@method_decorator(master_required, name='dispatch')
class RollbackLastTurnView(ConfirmView):
    title = "Annulla ultimo turno"
    message = 'Sei sicuro di voler tornare al turno precedente? Questo cancellerà definitivamente tutti gli eventi del turno corrente.'
    success_url = 'game:status'

    def form_valid(self, form):
        game = self.request.game
        current_turn = game.get_current_turn(for_update=True)
        prev_turn = Turn.objects.filter(game=game).exclude(pk=current_turn.pk).order_by('-date', '-phase').first()
        if prev_turn is not None:
            current_turn.delete()
            prev_turn.end = None
            prev_turn.save()
        game.kill_dynamics()
        return super().form_valid(form)


# View to restart game
@method_decorator(master_required, name='dispatch')
class RestartGameView(ConfirmView):
    message = 'Sei sicuro di voler ricominciare la partita? Questa azione non può essere annullata.'
    title = 'Azzera partita'
    success_url = 'game:status'

    def form_valid(self, form):
        game = self.request.game
        dynamics = game.get_dynamics()
        Turn.objects.filter(game=game).delete()
        game.kill_dynamics()
        game.initialize(get_now())
        return super().form_valid(form)


class SetupGameView(GameView):
    def get(self, request):
        game = request.game
        dynamics = game.get_dynamics()
        dynamics.update()

        if game.current_turn.phase != CREATION:
            return redirect('game:status', game_name=game.name)

        if not game.started:
            return redirect('game:seed', game_name=game.name)

        if game.mayor is None:
            return redirect('game:composition', game_name=game.name)

        soothsayer = dynamics.check_missing_soothsayer_propositions()
        if soothsayer is not None:
            return redirect('game:soothsayer', game_name=game.name, pk=soothsayer.pk)

        return redirect('game:propositions', game_name=game.name)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(SetupGameView, self).dispatch(*args, **kwargs)


# View for changing game Seed
class SeedForm(forms.Form):
    excluded_players = forms.ModelMultipleChoiceField(
        queryset = Player.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Giocatori da escludere:',
        required=False
    )
    seed = forms.IntegerField(required=True, label='Seed')
    RULESETS = [
        ('classic', 'Variante classica con due fazioni'),
        ('negromanti', 'Variante con la fazione dei negromanti')
    ]
    ruleset = forms.ChoiceField(choices=RULESETS, label='Regolamento')

    def __init__(self, *args, **kwargs):
        game = kwargs.pop('game', None)
        super(SeedForm, self).__init__(*args, **kwargs)
        self.fields['excluded_players'].queryset = Player.objects.filter(game=game)
        assert(not game.started)

@method_decorator(master_required, name='dispatch')
class SeedView(GameFormView):
    form_class = SeedForm
    success_url = 'game:setup'
    template_name = 'seed.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'classified' : True,
        })
        return context

    def form_valid(self, form):
        game = self.request.game
        excluded_players = form.cleaned_data['excluded_players']
        excluded_players.delete()
        game.initialize(get_now())
        dynamics = game.get_dynamics()

        event = SeedEvent(seed=str(form.cleaned_data['seed']))
        event.timestamp = get_now()
        dynamics.inject_event(event)

        event = SetRulesEvent(ruleset=form.cleaned_data['ruleset'])
        event.timestamp = get_now()
        dynamics.inject_event(event)

        return super().form_valid(form)


# View for deciding Village Composition
class VillageCompositionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super(VillageCompositionForm, self).__init__(*args, **kwargs)
        dynamics = self.game.get_dynamics()
        assert self.game.started and self.game.mayor is None

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

@method_decorator(master_required, name='dispatch')
class VillageCompositionView(GameFormView):
    form_class = VillageCompositionForm
    success_url = 'game:setup'
    template_name = 'composition.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'classified' : True,
        })
        return context

    def form_valid(self, form):
        dynamics = self.request.game.get_dynamics()
        roles = dynamics.starting_roles
        for role in roles:
            for i in range(form.cleaned_data[role.__name__]):
                event = AvailableRoleEvent(role_name = role.__name__)
                event.timestamp = get_now()
                dynamics.inject_event(event)

        return super().form_valid(form)


# View for inserting soothsayer propositions
class DisambiguatedPlayerChoiceField(forms.ModelChoiceField):
    model = Player
    def label_from_instance(self, obj):
        return obj.canonicalize().role.disambiguated_name

class SoothsayerForm(forms.ModelForm):
    class Meta:
        model = SoothsayerModelEvent
        fields = [ 'target', 'advertised_role' ]
        labels = {
            'target' : '',
            'advertised_role' : 'ha il ruolo di'
        }
        field_classes = {
            'target': DisambiguatedPlayerChoiceField
        }
        widgets = {
            'advertised_role': forms.Select(choices=())
        }

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super(SoothsayerForm, self).__init__(*args, **kwargs)
        dynamics = self.game.get_dynamics()

        self.fields["target"].queryset = Player.objects.filter(game=self.game)
        choices = [(x.full_name,x.full_name) for x in dynamics.starting_roles]
        self.fields["advertised_role"].choices = choices
        self.fields["advertised_role"].widget.choices = choices

class SoothsayerView(GameFormView):
    form_class = SoothsayerForm
    template_name = 'soothsayer.html'
    success_url = 'game:setup'

    def get_soothsayer(self):
        return Player.objects.get(game=self.request.game, pk=self.kwargs['pk']).canonicalize()

    def get_propositions(self):
        return SoothsayerModelEvent.objects.filter(turn__game=self.request.game, soothsayer=self.get_soothsayer())

    def get_soothsayer_error(self):
        return self.get_soothsayer().role.needs_soothsayer_propositions()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'soothsayer' : self.get_soothsayer(),
            'propositions' : self.get_propositions(),
            'classified' : True,
            'error': self.get_soothsayer_error(),
            'KNOWS_ABOUT_SELF': KNOWS_ABOUT_SELF,
            'NUMBER_MISMATCH': NUMBER_MISMATCH,
            'TRUTH_MISMATCH': TRUTH_MISMATCH,
        })
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.timestamp = get_now()
        self.object.soothsayer = self.get_soothsayer()
        self.request.game.get_dynamics().inject_event(self.object)
        return super().form_valid(form)

    @method_decorator(master_required)
    def dispatch(self, *args, **kwargs):
        return super(SoothsayerView, self).dispatch(*args, **kwargs)

@method_decorator(master_required, name='dispatch')
class DeleteSoothsayerView(EventDeleteView):
    success_url = 'game:setup'
    def get_queryset(self):
        return SoothsayerModelEvent.objects.filter(turn__game=self.request.game)


# View for inserting Initial Propositions
class InitialPropositionForm(forms.ModelForm):
    class Meta:
        model = InitialPropositionEvent
        fields = ['text']
        widgets = { 'text': forms.TextInput() }

class InitialPropositionsView(CreateView):
    form_class = InitialPropositionForm
    template_name = 'propositions.html'

    def get_propositions(self):
        return InitialPropositionEvent.objects.filter(turn__game=self.request.game)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'propositions' : self.get_propositions(),
            'classified' : True,
        })
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.timestamp = get_now()
        self.request.game.get_dynamics().inject_event(self.object)
        return redirect('game:setup', game_name=self.request.game.name)

@method_decorator(master_required, name='dispatch')
class DeletePropositionView(EventDeleteView):
    success_url = 'game:setup'
    def get_queryset(self):
        return InitialPropositionEvent.objects.filter(turn__game=self.request.game)



# Form for changing point of view (for GMs only)
class ChangePointOfViewForm(forms.Form):
    player = forms.ModelChoiceField(
                queryset=Player.objects.select_related('user').all(),
                empty_label='(Nessuno)',
                required=False,
                label='Scegli un giocatore:'
            )
    def __init__(self, *args, **kwargs):
        game = kwargs.pop('game', None)
        super(ChangePointOfViewForm, self).__init__(*args, **kwargs)
        self.fields['player'].queryset = Player.objects.filter(game=game)

# View for changing point of view (for GMs only)
class PointOfView(GameView):
    def get(self, request):
        game = request.game
        player = request.player
        form = ChangePointOfViewForm(game=game, initial={'player': player})
        return render(request, 'point_of_view.html', {'form': form, 'message': None, 'classified': True})
    
    def post(self, request):
        game = request.game
        player = request.player
        form = ChangePointOfViewForm(request.POST, game=game)
        
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
    
    @method_decorator(master_required)
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

        if request.is_master:
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
            last_comment = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp').first()
            # Check against double post
            if last_comment.text != text:
                comment = Comment(turn=game.current_turn, user=user, text=text)
                comment.save()
            return redirect('game:comment', game_name=game.name)

        old_comments = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp')
        can_comment = self.can_comment(request)
        return render(request, 'comment.html', {'form': form, 'old_comments': old_comments, 'can_comment': can_comment, 'classified': True})

    @method_decorator(player_required)
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
    
    @method_decorator(user_passes_test(is_staff_check))
    def dispatch(self, *args, **kwargs):
        return super(DumpView, self).dispatch(*args, **kwargs)
