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
    list_display = ('full_name', 'team', 'role_name', 'aura', 'alive', 'active', 'can_use_power', 'can_vote', 'is_mayor')
    #list_filter = ['team', 'alive', 'active']
    search_fields = ['user__first_name', 'user__last_name']

class EventAdmin(admin.ModelAdmin):
    list_display = ('subclass', 'turn', 'timestamp', 'pk')

class CommandEventAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'turn', 'timestamp', 'player', 'type', 'target', 'target2', 'target_ghost')

class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('announcement_name', 'timestamp', 'text', 'visible')
    list_filter = ['visible']

class CommentAdmin(admin.ModelAdmin):
    list_display = ('comment_name', 'user', 'timestamp', 'turn', 'text', 'visible')
    list_filter = ['visible']
    search_fields = ['user__first_name', 'user__last_name', 'text']

admin.site.register(Player, PlayerAdmin)
admin.site.register(CommandEvent, CommandEventAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(Turn, TurnAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(Comment, CommentAdmin)

