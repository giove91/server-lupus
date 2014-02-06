from django.contrib import admin

from game.models import *


class GameAdmin(admin.ModelAdmin):
    list_display = ('game_name', 'running', 'current_turn')

class TurnAdmin(admin.ModelAdmin):
    list_display = ('as_string', 'day', 'phase', 'begin', 'end')

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'team', 'role', 'aura', 'alive', 'active', 'can_use_power', 'can_vote', 'last_usage', 'last_target')
    list_filter = ['team', 'alive', 'active']
    search_fields = ['user__first_name', 'user__last_name', 'role__role_name']

class RoleAdmin(admin.ModelAdmin):
    list_display = ('role_name', 'team', 'aura', 'is_mystic', 'has_power', 'frequency', 'reflexive', 'on_living', 'on_dead', 'reusable_on_same_target', 'is_ghost')
    list_filter = ['team', 'aura', 'is_mystic', 'has_power']
    search_fields = ['role_name']

class ActionAdmin(admin.ModelAdmin):
    list_display = ('action_name', 'day', 'type', 'player', 'target', 'param', 'time')

# admin.site.register(Time, TimeAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Team)
admin.site.register(Role, RoleAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(Turn, TurnAdmin)

