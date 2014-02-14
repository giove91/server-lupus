from django.contrib import admin

from game.models import *
from game.events import *
from game.roles import *

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

admin.site.register(Player, PlayerAdmin)
admin.site.register(CommandEvent, CommandEventAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(Turn, TurnAdmin)

