#!/usr/bin/python
# coding=utf8

import json

from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from django.db.models import Q

from django.views import generic
from django.views.generic.base import View, TemplateView, RedirectView
from django.views.generic import ListView
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView

from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import redirect_to_login
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.contrib.auth.decorators import user_passes_test
from django.core import exceptions

from django import forms

from django.contrib.auth.models import User
from game.models import *
from game.events import *
from game.utils import get_now
from game.decorators import *
from game.weather import Weather
from game.widgets import MultiSelect
from datetime import datetime, timedelta


def not_implemented(request):
    raise NotImplementedError("View not implemented")

# Home Page
class HomeView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        user = self.request.user
        if user.is_authenticated:
            games = Game.objects.filter(
                Q(pk__in=user.player_set.values('game')) |
                Q(pk__in=user.gamemaster_set.values('game')) |
                Q(public=True))
        else:
            games = Game.objects.filter(public=True)

        # Remove failed games
        games = [g for g in games if g.get_dynamics() is not None]

        context = super().get_context_data(**kwargs)
        context.update({
            'beginning_games': [g for g in games if not g.started],
            'ongoing_games': [g for g in games if g.started and not g.is_over],
            'ended_games': [g for g in games if g.is_over]
        })
        return context

# Create a new account
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

@method_decorator(user_passes_test(is_staff_check), name='dispatch')
class SignUpView(FormView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = "/"

    def form_valid(self, form):
        user = form.save()
        profile = Profile(user=user, gender=form.cleaned_data.get('gender'))
        profile.save()
        raw_password = form.cleaned_data.get('password1')
        user = authenticate(username=user.username, password=raw_password)
        login(self.request, user)
        return super().form_valid(form)

## Static pages
class RulesetView(TemplateView):
    template_name = 'ruleset.html'

class CreditsView(TemplateView):
    template_name = 'credits.html'

class TrailerView(TemplateView):
    template_name = 'trailer.html'

class PrototypesView(TemplateView):
    template_name = 'prototypes.html'

class ErrorView(TemplateView):
    template_name = 'error.html'

class AnnouncementsListView(ListView):
    model = Announcement
    template_name = 'announcements.html'
    context_object_name = 'announcements'

    def get_queryset(self):
        game = self.request.game
        return Announcement.objects.filter(game=game).filter(visible=True).order_by('-timestamp')


## View for displaying a form passing game to form as argument

class GameFormView(FormView):
    # Pass game_name to success_url
    def get_success_url(self):
        return reverse(self.success_url, kwargs={'game_name': self.request.game.name})

    # Pass game to form as kwarg
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'game': self.request.game})
        return kwargs

    def can_execute_action(self):
        return True

    def dispatch(self, *args, **kwargs):
        if self.can_execute_action():
            return super().dispatch(*args, **kwargs)
        else:
            return render(self.request, 'command_not_allowed.html', {'message': 'Non puoi eseguire questa azione.', 'title': self.title, 'classified': True})

# Generic view for deleting an event (will respawn dynamics)
class EventDeleteView(DeleteView):
    def get_success_url(self):
        return reverse(self.success_url, kwargs={'game_name': self.request.game.name})

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        request.game.kill_dynamics()
        return response

## STATUS VIEWS

# Generic view for showing events
class EventListView(TemplateView):
    classified = False
    display_time = False
    point_of_view = None

    def get_point_of_view(self):
        if self.point_of_view is None:
            raise exceptions.ImproperlyConfigured("EventListView requires requires either a definition of 'point_of_view' or an implementation of 'get_point_of_view()'")
        else:
            return self.point_of_view

    # Retrieve weather
    def get_weather(self):
        stored_weather = self.request.session.get('weather', None)
        weather = Weather(stored_weather)
        uptodate = weather.get_data()
        if not uptodate:
            self.request.session['weather'] = weather.stored()
        return weather

    # Retrieve events depending on the pov
    def get_events(self):
        game = self.request.game
        player = self.get_point_of_view()
        dynamics = game.get_dynamics()
        assert dynamics is not None
        assert not dynamics.failed

        if player == 'admin':
            dynamics = dynamics.get_preview_dynamics()
            # Get all events, since it's requesting from admin.

        assert player == 'admin' or not dynamics.preview

        if player == 'admin':
            turns = dynamics.turns
        else:
            turns = [turn for turn in dynamics.turns if turn.phase in [CREATION, DAWN, SUNSET]]

        events = dynamics.events

        if player == 'admin':
            comments = Comment.objects.filter(turn__game=game).filter(visible=True).order_by('timestamp')
        else:
            comments = []

        # If requesting a preview, show messages as admin

        result = dict([(turn, { 'standard': [], VOTE: {}, ELECT: {}, 'initial_propositions': [], 'soothsayer_propositions': [], 'telepathy': {}, 'comments': [] }) for turn in turns ])
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

            if event.subclass == 'SoothsayerModelEvent' and event.soothsayer == player:
                result[event.turn]['soothsayer_propositions'].append(event.to_soothsayer_proposition())

            if event.subclass == 'TelepathyEvent' and event.player == player:
                if event.perceived_event.player in result[event.turn]['telepathy']:
                    result[event.turn]['telepathy'][event.perceived_event.player].append(event.get_perceived_message())
                else:
                    result[event.turn]['telepathy'][event.perceived_event.player] = [event.get_perceived_message()]

        for comment in comments:
            result[comment.turn]['comments'].append(comment)

        ordered_result = [ (turn, result[turn]) for turn in turns ]

        return ordered_result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.request.dynamics, 'rules'):
            display_votes = self.request.dynamics.rules.display_votes or self.get_point_of_view() in ['admin', 'preview']
            display_mayor = self.request.dynamics.rules.mayor
        else:
            display_votes = False
            display_mayor = False

        context.update({
            'events': self.get_events(),
            'weather': self.get_weather(),
            'classified': self.classified,
            'display_time': self.display_time,
            'display_votes': display_votes,
            'display_mayor': display_mayor
        })
        return context

# View of village status and public events
class VillageStatusView(EventListView):
    template_name = 'public_info.html'
    point_of_view = 'public'

# View of personal info and events
@method_decorator(player_required, name='dispatch')
class PersonalInfoView(EventListView):
    template_name = 'personal_info.html'
    classified = True

    def get_point_of_view(self):
        return self.request.player


# View of all info (for GM only)
@method_decorator(can_access_admin_view, name='dispatch')
class AdminStatusView(EventListView):
    template_name = 'public_info.html'
    point_of_view = 'admin'
    classified = True
    display_time = True

## COMMAND VIEWS

# "Generic" form for submitting actions
class CommandForm(forms.Form):

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        game = kwargs.pop('game', None)
        super(CommandForm, self).__init__(*args, **kwargs)

        # Create form fields in the following order.
        for key in ['target', 'target2', 'role_class', 'multiple_role_class']:
            if key in fields.keys():
                field = fields[key]

                if key == 'target' or key == 'target2':
                    choices = [ (None, '(Nessuno)') ]
                    extra_choices = sorted([player for player in field['choices'] if player is not None], key=lambda x: x.user.last_name)
                    choices.extend( [ (player.pk, player.full_name) for player in extra_choices ] )
                elif key == 'role_class' or key == 'multiple_role_class':
                    if key == 'role_class':
                        choices = [ (None, '(Nessuno)') ]
                    else:
                        choices = []
                    # Create optgroups per team
                    teams_found = [t for t in TEAM_IT.keys() if t in [x.team for x in field['choices']]]
                    for team in teams_found:
                        if len(teams_found) > 1:
                            choices.extend([(TEAM_IT[team], [(role_class.as_string(), role_class.name) for role_class in field['choices'] if role_class.team == team])])
                        else:
                            choices.extend([(role_class.as_string(), role_class.name) for role_class in field['choices']])

                else:
                    raise Exception ('Unknown form field.')

                if key == 'multiple_role_class':
                    self.fields[key] = forms.MultipleChoiceField(choices=choices, required=False, label=field['label'], widget=MultiSelect)
                else:
                    self.fields[key] = forms.ChoiceField(choices=choices, required=False, label=field['label'])

                if key == 'target' or key == 'target2':
                    if field['initial'] is not None:
                        self.fields[key].initial = field['initial'].pk
                    else:
                        self.fields[key].initial = None
                elif key == 'role_class':
                    if field['initial'] is not None:
                        self.fields[key].initial = field['initial'].as_string()
                    else:
                        self.fields[key].initial = None
                elif key == 'multiple_role_class':
                    if field['initial'] is not None:
                        self.fields[key].initial = [x.as_string() for x in field['initial']]
                    else:
                        self.fields[key].initial = None

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

@method_decorator(player_required, name='dispatch')
class CommandView(GameFormView):

    template_name = 'command.html'
    form_class = CommandForm

    def can_execute_action(self):
        # Checks if the action can be done
        raise Exception ('Command not specified.')

    def get_fields(self):
        # Returns a description of the fields required
        raise Exception ('Command not specified.')

    def submitted(self):
        return render(self.request, 'command_submitted.html', {'title': self.title, 'classified': True})

    def save_command(self, cleaned_data):
        # Validates the form data and possibly saves the command, returning True in case of success and False otherwise
        raise Exception ('Command not specified.')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title,
            'url_name': self.url_name,
            'classified': True,
        })
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'fields': self.get_fields()
        })
        return kwargs

    def form_valid(self, form):
        if self.save_command(form.cleaned_data):
            return self.submitted()
        else:
            return render(self.request, 'command_not_allowed.html', {'message': 'La scelta effettuata non è valida.', 'classified': True})

## Night power

class UsePowerView(CommandView):

    title = 'Azione speciale'
    url_name = 'game:usepower'

    def can_execute_action(self):
        return self.request.player is not None and self.request.player.can_use_power()

    def get_fields(self):
        player = self.request.player
        game = player.game
        power = player.power
        dynamics = game.get_dynamics()

        targets = power.get_targets(dynamics)
        targets2 = power.get_targets2(dynamics)
        role_classes = power.get_targets_role_class(dynamics)
        if role_classes is not None:
            role_classes -= {power.get_target_role_class_default(dynamics)}
        multiple_role_classes = power.get_targets_multiple_role_class(dynamics)

        initial = power.recorded_target
        initial2 = power.recorded_target2
        initial_role_class = power.recorded_role_class
        initial_multiple_role_class = power.recorded_multiple_role_class

        fields = {}


        if targets is not None:
            fields['target'] = {'choices': targets, 'initial': initial, 'label': power.message}
        if targets2 is not None:
            fields['target2'] = {'choices': targets2, 'initial': initial2, 'label': power.message2}
        if role_classes is not None:
            role_classes = sorted(role_classes, key=lambda x: x.name)
            fields['role_class'] = {'choices': role_classes, 'initial': initial_role_class, 'label': power.message_role}
        if multiple_role_classes is not None:
            multiple_role_classes = sorted(multiple_role_classes, key=lambda x: x.name)
            fields['multiple_role_class'] = {'choices': multiple_role_classes, 'initial': initial_multiple_role_class, 'label': ''}

        return fields

    def save_command(self, cleaned_data):
        player = self.request.player
        power = player.power
        dynamics = self.request.game.get_dynamics()

        targets = power.get_targets(dynamics)
        targets2 = power.get_targets2(dynamics)
        role_classes = power.get_targets_role_class(dynamics)
        role_class_default = power.get_target_role_class_default(dynamics)
        multiple_role_classes = power.get_targets_multiple_role_class(dynamics)

        target = cleaned_data['target']
        target2 = None
        role_class = None
        multiple_role_class = None

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
            if not power.allow_target2_same_as_target and target2 == target:
                return False

        if role_classes is not None:
            role_class = cleaned_data['role_class']
            if role_class == '':
                role_class = role_class_default
            else:
                role_class = Role.get_from_string(role_class)
            if not role_class in role_classes and target is not None:
                # If role_class is not valid (or None), make the command not valid
                # unless target is None (which means that the power will not be used)
                return False

        if multiple_role_classes is not None:
            multiple_role_class = cleaned_data['multiple_role_class']
            if role_class == '':
                multiple_role_class = None
            else:
                multiple_role_class = {Role.get_from_string(x) for x in multiple_role_class}

            if not multiple_role_class.issubset(multiple_role_classes) and target is not None:
                # If role_class is not valid (or None), make the command not valid
                # unless target is None (which means that the power will not be used)
                return False

        # If target is None, then the other fields are set to None
        if target is None:
            target2 = None
            role_class = None
            multiple_role_class = None

        command = CommandEvent(player=player, type=USEPOWER, target=target, target2=target2, role_class=role_class, multiple_role_class=multiple_role_class, turn=player.game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=self.request.current_turn):
            return False
        dynamics = self.request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True

## Stake vote

class VoteView(CommandView):

    title = 'Votazione per il rogo'
    url_name = 'game:vote'

    def can_execute_action(self):
        return self.request.player is not None and self.request.player.can_vote()

    def get_fields(self):
        player = self.request.player
        game = player.game
        choices = game.get_alive_players()
        initial = player.recorded_vote

        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per condannare a morte:'} }
        return fields

    def save_command(self, cleaned_data):
        player = self.request.player
        game = player.game
        target = cleaned_data['target']

        if target == '':
            target = None

        if target is not None and target not in game.get_alive_players():
            return False

        command = CommandEvent(player=player, type=VOTE, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=self.request.current_turn):
            return False
        dynamics = self.request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True

## Mayor vote

class ElectView(CommandView):

    title = 'Elezione del Sindaco'
    url_name = 'game:elect'

    def can_execute_action(self):
        return self.request.player is not None and self.request.player.can_vote() and self.request.dynamics.rules.mayor

    def get_fields(self):
        player = self.request.player
        game = player.game
        choices = game.get_alive_players()
        initial = player.recorded_elect

        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Vota per eleggere:'} }
        return fields

    def save_command(self, cleaned_data):
        player = self.request.player
        game = player.game
        target = cleaned_data['target']

        if target == '':
            target = None

        if target is not None and target not in game.get_alive_players():
            return False

        command = CommandEvent(player=player, type=ELECT, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=self.request.current_turn):
            return False
        dynamics = self.request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True


# View for appointing a successor (for mayor only)
class AppointView(CommandView):

    title = 'Nomina del successore'
    url_name = 'game:appoint'

    def can_execute_action(self):
        return self.request.player is not None and self.request.player.is_mayor() and self.request.dynamics.rules.mayor and (self.request.game.current_turn.phase in [DAY, NIGHT])

    def get_fields(self):
        player = self.request.player
        game = player.game
        choices = [p for p in game.get_alive_players() if p.pk != player.pk]
        initial = game.get_dynamics().appointed_mayor

        fields = {'target': {'choices': choices, 'initial': initial, 'label': 'Designa come successore:'} }
        return fields

    def save_command(self, cleaned_data):
        player = self.request.player
        game = player.game
        target = cleaned_data['target']

        if target == '':
            target = None

        if target is not None and target not in game.get_alive_players():
            return False

        if target is not None and target == player:
            return False

        command = CommandEvent(player=player, type=APPOINT, target=target, turn=game.current_turn, timestamp=get_now())
        if not command.check_phase(turn=self.request.current_turn):
            return False
        dynamics = self.request.player.game.get_dynamics()
        dynamics.inject_event(command)
        return True




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
@method_decorator(user_passes_test(is_staff_check), name='dispatch')
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
            'day_end_weekdays': [i for i,x in enumerate(self.game.day_end_weekdays) if x],
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
        game.day_end_weekdays = [str(i) in form.cleaned_data['day_end_weekdays'] for i in range(7)]
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


@method_decorator(master_required, name='dispatch')
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


@method_decorator(master_required, name='dispatch')
class DeleteGameMasterView(DeleteView):
    success_url = 'game:managemasters'
    def get_queryset(self):
        return GameMaster.objects.filter(game=self.request.game)

# View for publishing a new announcement
class PublishAnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['text']
        widgets = { 'text': forms.TextInput() }

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super().__init__(*args, **kwargs)


@method_decorator(master_required, name='dispatch')
class PublishAnnouncementView(CreateView):
    form_class = PublishAnnouncementForm
    template_name = 'announcements.html'

    def get_success_url(self):
        return reverse( 'game:publishannouncement', kwargs={'game_name': self.request.game.name})

    def get_announcements(self):
        return Announcement.objects.filter(game=self.request.game)

    def get_form_kwargs(self, **kwargs):
        kwargs = super().get_form_kwargs(**kwargs)
        kwargs.update({ 'game': self.request.game })
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'announcements': self.get_announcements()
        })
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.game = self.request.game
        return super().form_valid(form)

@method_decorator(master_required, name='dispatch')
class DeleteAnnouncementView(DeleteView):
    def get_success_url(self):
        return reverse('game:publishannouncement', kwargs={'game_name': self.request.game.name})
    def get_queryset(self):
        return Announcement.objects.filter(game=self.request.game)


# View for advancing turn
@method_decorator(master_required, name='dispatch')
class AdvanceTurnView(ConfirmView):
    title = 'Turno successivo'
    success_url = 'game:status'

    def get_message(self):
        next_turn = self.request.current_turn.next_turn()
        return 'Vuoi davvero avanzare %s%s?' % (next_turn.preposition_to_as_italian_string(), next_turn.turn_as_italian_string())

    def can_execute_action(self):
        game = self.request.game
        if game.current_turn.phase == CREATION:
            return game.started and game.get_dynamics().players[0].role is not None and game.get_dynamics().check_missing_soothsayer_propositions() is None
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


## Initial Setup

# View for redirecting to appropriate initial setup
@method_decorator(master_required, name='dispatch')
class SetupGameView(RedirectView):
    def get_redirect_url(self, *args,  **kwargs):
        game = self.request.game
        dynamics = game.get_dynamics()
        dynamics.update()

        if game.current_turn.phase != CREATION:
            self.pattern_name = 'game:status'
        elif not game.started:
            self.pattern_name = 'game:seed'
        elif dynamics.players[0].role is None:
            self.pattern_name = 'game:composition'
        elif dynamics.check_missing_spectral_sequence():
            self.pattern_name = 'game:spectralsequence'
        elif dynamics.check_missing_soothsayer_propositions() is not None:
            kwargs.update({'pk': dynamics.check_missing_soothsayer_propositions().pk})
            self.pattern_name = 'game:soothsayer'
        else:
            self.pattern_name = 'game:propositions'

        return super().get_redirect_url(*args, **kwargs)

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
        ('v1', 'Tre fazioni, regole di Lupus 7'),
        ('v2', 'Tre fazioni, regole di Lupus 8'),
        ('v2_2', 'Due fazioni, regole di Lupus 9')
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
        teams = dynamics.rules.teams
        assert self.game.started and self.game.get_dynamics().players[0].role is None

        for role in sorted(dynamics.valid_roles, key=lambda x: (teams.index(x.team), x.name)):
            if not role.dead_power:
                self.fields[role.__name__] = forms.IntegerField(label=role.name, min_value=0, initial=0)

    def clean(self):
        dynamics = self.game.get_dynamics()
        cleaned_data = super().clean()
        count = 0
        for role in dynamics.valid_roles:
            if not role.dead_power:
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
        roles = [x for x in dynamics.valid_roles if not x.dead_power]
        for role in roles:
            for i in range(form.cleaned_data[role.__name__]):
                event = AvailableRoleEvent(role_class=role)
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
        choices = [(x.as_string(), x.name) for x in dynamics.valid_roles if not x.dead_power]
        self.fields["advertised_role"].choices = choices
        self.fields["advertised_role"].widget.choices = choices

@method_decorator(master_required, name='dispatch')
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

@method_decorator(master_required, name='dispatch')
class DeleteSoothsayerView(EventDeleteView):
    success_url = 'game:setup'
    def get_queryset(self):
        return SoothsayerModelEvent.objects.filter(turn__game=self.request.game)

# View for inserting Spectral Sequence
class SpectralSequenceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super().__init__(*args, **kwargs)

    sequence = forms.MultipleChoiceField(
            widget=forms.CheckboxSelectMultiple(),
            choices = tuple((i, 'Morto %s' % (i+1)) for i in range(20)),
            label='Popolani da rendere spettri:'
    )

@method_decorator(master_required, name='dispatch')
class SpectralSequenceView(FormView):
    form_class = SpectralSequenceForm
    template_name = 'spectral_sequence.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'classified' : True,
        })
        return context

    def form_valid(self, form):
        deaths = [int(i) for i in form.cleaned_data.get('sequence')]
        event = SpectralSequenceEvent(sequence=[i in deaths for i in range(20)], timestamp=get_now())
        self.request.game.get_dynamics().inject_event(event)
        return redirect('game:setup', game_name=self.request.game.name)


# View for inserting Initial Propositions
class InitialPropositionForm(forms.ModelForm):
    class Meta:
        model = InitialPropositionEvent
        fields = ['text']
        widgets = { 'text': forms.TextInput() }

@method_decorator(master_required, name='dispatch')
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
@method_decorator(master_required, name='dispatch')
class PointOfView(GameFormView):
    form_class = ChangePointOfViewForm
    template_name = 'point_of_view.html'
    success_url = 'game:status'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({ 'classified': True })
        return context

    def get_initial(self):
        initial = super().get_initial()
        initial.update({ 'player': self.request.player })
        return initial

    def form_valid(self, form):
        player = form.cleaned_data.get('player')
        if player is not None:
            self.request.session['player_id'] = player.pk
        else:
            self.request.session['player_id'] = None

        return super().form_valid(form)

# View for forcing win
class ForceVictoryForm(forms.ModelForm):
    winners = forms.MultipleChoiceField(choices=(), widget=forms.CheckboxSelectMultiple(choices=()), label='Vincitori', required=False)
    class Meta:
        model = ForceVictoryEvent
        fields = [ 'winners' ]

    def __init__(self, *args, **kwargs):
        self.game = kwargs.pop('game', None)
        super().__init__(*args, **kwargs)
        dynamics = self.game.get_dynamics()

        choices = [(x,TEAM_IT[x]) for x in dynamics.playing_teams]
        self.fields["winners"].initial = list(dynamics.recorded_winners) if dynamics.recorded_winners is not None else []
        self.fields["winners"].choices = sorted(choices, key=lambda x:x[1])
        self.fields["winners"].widget.choices = choices

@method_decorator(master_required, name='dispatch')
class ForceVictoryView(GameFormView):
    form_class = ForceVictoryForm
    template_name = 'force_victory.html'
    title = 'Decreta vincitori'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'classified' : True,
        })
        return context

    def can_execute_action(self):
        return not self.request.game.is_over and self.request.game.started

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.timestamp = get_now()
        self.request.game.get_dynamics().inject_event(self.object)

        return render(self.request, 'command_submitted.html', {'classified': True})


# View for writing comments
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        labels = {'text': ''}

@method_decorator(player_or_master_required, name='dispatch')
class CommentView(FormView):
    form_class = CommentForm
    template_name = 'comment.html'
    max_comments_per_turn = 100

    def get_success_url(self):
        return reverse('game:comment', kwargs={'game_name': self.request.game.name})

    def can_comment(self):
        # Checks if the user can post a comment
        user = self.request.user
        game = self.request.game
        current_turn = game.current_turn

        if self.request.is_master:
            return True

        try:
            comments_number = Comment.objects.filter(user=user).filter(turn=current_turn).count()
            if comments_number >= self.max_comments_per_turn:
                return False
            else:
                return True

        except IndexError:
            return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'old_comments': Comment.objects.filter(user=self.request.user)
                    .filter(turn__game=self.request.game).filter(visible=True).order_by('-timestamp'),
            'can_comment': self.can_comment(),
            'classified': True
        })
        return context

    def form_valid(self, form):
        user = self.request.user
        game = self.request.game
        current_turn = game.current_turn

        if self.can_comment():
            text = form.cleaned_data['text']
            last_comment = Comment.objects.filter(user=user).filter(turn__game=game).filter(visible=True).order_by('-timestamp').first()
            # Check against double post
            if last_comment is None or last_comment.text != text:
                comment = Comment(turn=game.current_turn, user=user, text=text)
                comment.save()

        return super().form_valid(form)


# Dump view (for GM only)
@method_decorator(user_passes_test(is_staff_check), name='dispatch')
class DumpView(View):
    def get(self, request, **kwargs):
        game = request.game
        response = HttpResponse(content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="%s.json"' % game.name
        dump_game(game, response)
        return response

# Load view
class LoadGameForm(forms.Form):
    json = forms.FileField()
    def clean_file(self):
        file = self.cleaned_data['json']
        if file.content_type == 'application/json':
            if file.size > 1048576:
                raise forms.ValidationError('Massimo upload consentito 1MB.' % filesizeformat(file.size))
        else:
            raise forms.ValidationError('Tipo di file non supportato')

@method_decorator(user_passes_test(is_staff_check), name='dispatch')
class LoadGameView(FormView):
    form_class = LoadGameForm
    template_name = 'load_game.html'
    def get_success_url(self):
        return reverse('game:status', kwargs={'game_name': self.request.game.name})

    def form_valid(self, form):
        file = self.request.FILES['json']
        game = self.request.game
        game.load_from_json(json.loads(file.read().decode("UTF-8")))
        return super().form_valid(form)
