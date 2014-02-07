from django.db import models
from models import Role


# Fazione dei Popolani

class Contadino(Role):
    role_name = 'Contadino'
    team = 'P'


class Cacciatore(Role):
    role_name = 'Cacciatore'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if not target.alive:
            return False
        return True


class Custode(Role):
    role_name = 'Custode del cimitero'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if target.alive:
            return False
        return True


class Divinatore(Role):
    role_name = 'Divinatore'
    team = 'P'
    is_mystic = True


class Esorcista(Role):
    role_name = 'Esorcista'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        return True


class Espansivo(Role):
    role_name = 'Espansivo'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or (self.player.game.current_turn.day - self.last_usage.day >= 2) )
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if not target.alive:
            return False
        return True


class Guardia(Role):
    role_name = 'Guardia'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if not target.alive:
            return False
        return True


class Investigatore(Role):
    role_name = 'Investigatore'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if target.alive:
            return False
        return True


class Mago(Role):
    role_name = 'Mago'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        return True


class Massone(Role):
    role_name = 'Massone'
    team = 'P'


class Messia(Role):
    role_name = 'Messia'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def can_use_power_on(self, target):
        if target.alive:
            return False
        return True


class Necrofilo(Role):
    role_name = 'Necrofilo'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def can_use_power_on(self, target):
        if target.alive:
            return False
        return True


class Stalker(Role):
    role_name = 'Stalker'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or (self.player.game.current_turn.day - self.last_usage.day >= 2) )
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if not target.alive:
            return False
        return True


class Veggente(Role):
    role_name = 'Veggente'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        if not target.alive:
            return False
        return True


class Voyeur(Role):
    role_name = 'Stalker'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or (self.player.game.current_turn.day - self.last_usage.day >= 2) )
    
    def can_use_power_on(self, target):
        if self.player.pk == target.pk:
            return False
        return True



