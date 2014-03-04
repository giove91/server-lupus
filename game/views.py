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

from datetime import datetime, timedelta

import urllib, urllib2
import xml.etree.ElementTree as ET


def is_GM_check(user):
    # Checks that the user is a GM
    if not user.is_authenticated():
        return False
    return user.is_staff


def get_events(request, player):
    # player can be a Player, 'admin' or 'public' (depending on the view)
    game = request.game
    
    # TODO: prendere le cose dalla dynamics
    if player == 'admin':
        turns = Turn.objects.filter(game=game).order_by('date', 'phase')
    else:
        turns = Turn.objects.filter(game=game).filter( Q(phase=CREATION) | Q(phase=DAWN) | Q(phase=SUNSET) ).order_by('date', 'phase')
    
    events = Event.objects.filter(turn__game=game).order_by('timestamp', 'pk')
    
    result = { turn: { 'standard': [], VOTE: {}, ELECT: {}, 'initial_propositions': [], 'soothsayer_propositions': [] } for turn in turns }
    
    for e in events:
        event = e.as_child()
        message = event.to_player_string(player)
        if message is not None:
            assert event.turn in result.keys()
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
    
    ordered_result = [ (turn, result[turn]) for turn in turns ]
    return ordered_result



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
    return redirect('status')


def ruleset(request):
    return render(request, 'ruleset.html')

def credits(request):
    return render(request, 'credits.html')


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
        elif 802 <= self.description <= 804:
            return 'cloudy'
        elif 800 <= self.description <= 801:
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

# View of village status and public events
class VillageStatusView(View):
    def get(self, request):
        
        game = request.game
        events = get_events(request, 'public')
        weather = get_weather(request)
        
        context = {
            'events': events,
            'weather': weather,
        }   
        return render(request, 'public_info.html', context)


# View of personal info and events
class PersonalInfoView(View):
    def get(self, request):
        
        if request.player is None:
            return redirect('pointofview')
        
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
class AdminStatusView(View):
    def get(self, request):
        events = get_events(request, 'admin')
        weather = get_weather(request)
        
        context = {
            'events': events,
            'weather': weather,
            'classified': True,
        }
        
        return render(request, 'public_info.html', context)
    
    @method_decorator(user_passes_test(is_GM_check))
    def dispatch(self, *args, **kwargs):
        return super(AdminStatusView, self).dispatch(*args, **kwargs)



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
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(request.POST, fields=self.get_fields(request))
        if form.is_valid():
            if self.save_command(request, form.cleaned_data):
                return self.submitted(request)
            else:
                return render(request, 'command_not_allowed.html', {'message': 'La scelta effettuata non &egrave; valida.', 'classified': True})
        else:
            return render(request, self.template_name, {'form': form, 'classified': True})
    
    def get(self, request):
        if request.player is None:
            return redirect('pointofview')
        
        if not self.check(request):
            return self.not_allowed(request)
        
        form = CommandForm(fields=self.get_fields(request))
        context = {
            'form': form,
            'title': self.title,
            'url_name': self.url_name,
            'classified': True,
        }
        return render(request, self.template_name, {'form': form, 'title': self.title, 'url_name': self.url_name, 'classified': True})
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CommandView, self).dispatch(*args, **kwargs)


class UsePowerView(CommandView):
    
    title = 'Potere notturno'
    url_name = 'usepower'
    
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
    
    title = 'Votazione per il rogo'
    url_name = 'vote'
    
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
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=VOTE, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


class ElectView(CommandView):
    
    title = 'Elezione del Sindaco'
    url_name = 'elect'
    
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
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        command = CommandEvent(player=player, type=ELECT, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


# View for appointing a successor (for mayor only)
class AppointView(CommandView):
    
    title = 'Nomina del successore'
    url_name = 'appoint'
    
    def check(self, request):
        return request.player is not None and request.player.is_mayor and request.game is not None and (request.game.current_turn.phase == DAY or request.game.current_turn.phase == NIGHT)
    
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
        
        if target is not None and target not in game.get_alive_players():
            return False
        
        if target is not None and target == player:
            return False
        
        command = CommandEvent(player=player, type=APPOINT, target=target, turn=game.current_turn, timestamp=get_now())
        dynamics = request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True






class ContactsView(ListView):
    model = Player
    template_name = 'contacts.html'
    
    # TODO: forse un giorno bisognerebbe filtrare con il Game giusto
    
    def get_queryset(self):
        return Player.objects.all().order_by('user__last_name', 'user__first_name')
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ContactsView, self).dispatch(*args, **kwargs)


class AnnouncementsView(ListView):
    model = Announcement
    template_name = 'announcements.html'
    
    # TODO: filtrare per il Game giusto
    def get_queryset(self):
        return Announcement.objects.filter(visible=True).order_by('-timestamp')


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

class CommentView(View):
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
        
        if form.is_valid() and self.can_comment(request):
                text = form.cleaned_data['text']
                comment = Comment(turn=game.current_turn, user=user, text=text)
                comment.save()
                form = CommentForm()
       
        old_comments = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp')
        can_comment = self.can_comment(request)
        return render(request, 'comment.html', {'form': form, 'old_comments': old_comments, 'can_comment': can_comment})
    
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(CommentView, self).dispatch(*args, **kwargs)

