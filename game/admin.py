from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from game.models import *
from game.events import *
from game.roles import *


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
    list_display = ('game_name', 'running', 'current_turn', 'mayor')

class TurnAdmin(admin.ModelAdmin):
    list_display = ('as_string', 'date', 'phase', 'begin', 'end')

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'gender', 'team', 'role_name', 'aura', 'is_mystic', 'alive', 'active', 'can_use_power', 'can_vote', 'is_mayor', 'is_appointed_mayor')
    search_fields = ['user__first_name', 'user__last_name']

class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('announcement_name', 'timestamp', 'text', 'visible')
    list_filter = ['visible']

class CommentAdmin(admin.ModelAdmin):
    list_display = ('comment_name', 'user', 'timestamp', 'turn', 'text', 'visible')
    list_filter = ['visible', 'user']
    search_fields = ['user__first_name', 'user__last_name', 'text']

class EventAdmin(admin.ModelAdmin):
    list_filter = ['turn']
    list_display = ('subclass', 'turn', 'is_automatic', 'timestamp', 'pk')

class CommandEventAdmin(admin.ModelAdmin):
    list_filter = ['type', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'player_role', 'type', 'target', 'target_role', 'target2', 'target2_role', 'target_ghost')
    search_fields = ['player__user__first_name', 'player__user__last_name']

class FreeTextEventAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'turn', 'timestamp', 'text')

class InitialPropositionEventAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'turn', 'timestamp', 'text')

class RoleKnowledgeEventAdmin(admin.ModelAdmin):
    list_filter = ['cause', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'target', 'role_name', 'cause')
    search_fields = ['player__user__first_name', 'player__user__last_name', 'target__user__first_name', 'target__user__last_name']

class PowerOutcomeEventAdmin(admin.ModelAdmin):
    list_filter = ['success', 'turn']
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'success', 'sequestrated')
    search_fields = ['player__user__first_name', 'player__user__last_name']

class PageRequestAdmin(admin.ModelAdmin):
    list_filter = ['user__is_staff', 'user']
    list_display = ('pagerequest_name', 'user', 'timestamp', 'path', 'ip_address', 'hostname')
    search_fields = ['user__username', 'user__first_name', 'user__last_name']

class ForceVictoryEventAdmin(admin.ModelAdmin):
    list_display = ('popolani_win', 'lupi_win', 'negromanti_win')

admin.site.register(Player, PlayerAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(Turn, TurnAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(Comment, CommentAdmin)

admin.site.register(CommandEvent, CommandEventAdmin)
admin.site.register(InitialPropositionEvent, InitialPropositionEventAdmin)
admin.site.register(FreeTextEvent, FreeTextEventAdmin)
admin.site.register(RoleKnowledgeEvent, RoleKnowledgeEventAdmin)
admin.site.register(PowerOutcomeEvent, PowerOutcomeEventAdmin)
admin.site.register(ForceVictoryEvent, ForceVictoryEventAdmin)

admin.site.register(PageRequest, PageRequestAdmin)
