from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import models
from django.utils.html import format_html
from django.urls import reverse

from game.models import *
from game.events import *
from game.roles import *
from game.widgets import CustomSplitDateTime


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

# Define a new User admin
class UserAdmin(UserAdmin):
    inlines = (ProfileInline, )

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'current_turn', 'public', 'postgame_info')
    list_display_link = ('current_turn',)

class TurnAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.DateTimeField: {'widget': CustomSplitDateTime(time_format='%H:%M:%S.%f', attrs={'style': 'width:100px'})},
    }

    list_display = ('as_string', 'game', 'begin', 'end', 'is_current')
    list_filter = ['game']

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'game', 'gender', 'team', 'role_name', 'aura', 'is_mystic', 'alive', 'active', 'can_use_power', 'can_vote', 'is_mayor', 'is_appointed_mayor')
    search_fields = ['user__first_name', 'user__last_name']
    list_filter = ['game']

class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('announcement_name', 'game', 'timestamp', 'text', 'visible')
    list_filter = ['visible']

class CommentAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('comment_name', 'user', 'timestamp', 'game', 'turn', 'text', 'visible')
    list_filter = ['turn__game', 'visible', 'user']
    search_fields = ['user__first_name', 'user__last_name', 'text']

class EventAdmin(admin.ModelAdmin):
    def link_to_subclass(self, obj):
        link = reverse('admin:game_%s_change' % obj.subclass.lower(), args=[obj.pk])
        return format_html('<a href="{}">{}</a>', link, obj.subclass)
    link_to_subclass.short_description = 'Subclass'

    list_filter = ['turn__game', 'turn']
    list_display = ('link_to_subclass', 'turn', 'is_automatic', 'timestamp', 'pk')

class CommandEventAdmin(admin.ModelAdmin):
    list_filter = ['type', 'turn__game', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'player_role', 'type', 'target', 'target_role', 'target2', 'target2_role', 'role_class', 'multiple_role_class')
    search_fields = ['player__user__first_name', 'player__user__last_name']

@admin.register(SeedEvent)
class SeedEventAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'seed' )
    list_filter = ['turn__game']
    readonly_fields = ['timestamp']

@admin.register(SetRulesEvent)
class SetRulesEventAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'ruleset' )
    list_filter = ['turn__game']
    readonly_fields = ['timestamp']

@admin.register(AvailableRoleEvent)
class AvailableRoleEventAdmin(admin.ModelAdmin):
    def role_name(self, obj):
        return obj.role_class.name

    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'game', 'role_name' )
    exclude = ['role_class']
    list_filter = ['turn__game']
    readonly_fields = ['timestamp']

@admin.register(SpectralSequenceEvent)
class SpectralSequenceEventAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'game', 'sequence' )
    list_filter = ['turn__game']
    readonly_fields = ['timestamp']

class FreeTextEventAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'game', 'turn', 'timestamp', 'text')
    readonly_fields = ['timestamp']

class InitialPropositionEventAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'game', 'turn', 'timestamp', 'text')
    readonly_fields = ['timestamp']

class SoothsayerModelEventAdmin(admin.ModelAdmin):
    def game(self, obj):
        return obj.turn.game

    list_display = ('event_name', 'game', 'turn', 'timestamp', 'target', 'advertised_role', 'soothsayer')
    readonly_fields = ['timestamp']

class RoleKnowledgeEventAdmin(admin.ModelAdmin):
    list_filter = ['cause', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'target', 'role_class', 'cause')
    search_fields = ['player__user__first_name', 'player__user__last_name', 'target__user__first_name', 'target__user__last_name']

class PowerOutcomeEventAdmin(admin.ModelAdmin):
    list_filter = ['success', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'success')
    search_fields = ['player__user__first_name', 'player__user__last_name']

class PageRequestAdmin(admin.ModelAdmin):
    list_filter = ['user__is_staff', 'user']
    list_display = ('pagerequest_name', 'user', 'timestamp', 'path', 'ip_address', 'hostname')
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

class ForceVictoryEventAdmin(admin.ModelAdmin):
    list_display = ('winners', )

admin.site.register(Player, PlayerAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(Turn, TurnAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(Comment, CommentAdmin)

admin.site.register(CommandEvent, CommandEventAdmin)
admin.site.register(InitialPropositionEvent, InitialPropositionEventAdmin)
admin.site.register(SoothsayerModelEvent, SoothsayerModelEventAdmin)
admin.site.register(FreeTextEvent, FreeTextEventAdmin)
#admin.site.register(RoleKnowledgeEvent, RoleKnowledgeEventAdmin)
#admin.site.register(PowerOutcomeEvent, PowerOutcomeEventAdmin)
admin.site.register(ForceVictoryEvent, ForceVictoryEventAdmin)

admin.site.register(PageRequest, PageRequestAdmin)
