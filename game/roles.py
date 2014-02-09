from django.db import models
from models import Role, Player


# Fazione dei Popolani

class Contadino(Role):
    name = 'Contadino'
    team = 'P'


class Cacciatore(Role):
    name = 'Cacciatore'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Custode(Role):
    name = 'Custode del cimitero'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Divinatore(Role):
    name = 'Divinatore'
    team = 'P'
    is_mystic = True


class Esorcista(Role):
    name = 'Esorcista'
    team = 'P'
    is_mystic = True
    
    message = 'Benedici la casa di:'
    
    def can_use_power(self):
        return self.player.alive
    
    def can_use_power_on(self, target):
        return True
    
    def get_targets(self):
        return self.player.game.get_active_players()


class Espansivo(Role):
    name = 'Espansivo'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Guardia(Role):
    name = 'Guardia'
    team = 'P'
    
    message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Investigatore(Role):
    name = 'Investigatore'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Mago(Role):
    name = 'Mago'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players().exclude(pk=self.pk)


class Massone(Role):
    name = 'Massone'
    team = 'P'


class Messia(Role):
    name = 'Messia'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Necrofilo(Role):
    name = 'Necrofilo'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Stalker(Role):
    name = 'Stalker'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Veggente(Role):
    name = 'Veggente'
    team = 'P'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Voyeur(Role):
    name = 'Stalker'
    team = 'P'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_active_players().exclude(pk=self.pk)


# Fazione dei Lupi

class Lupo(Role):
    name = 'Lupo'
    team = 'L'
    aura = 'B'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = 'L'
    aura = 'B'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Diavolo(Role):
    name = 'Diavolo'
    team = 'L'
    aura = 'B'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Fattucchiera(Role):
    name = 'Fattucchiera'
    team = 'L'
    aura = 'B'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()


class Rinnegato(Role):
    name = 'Rinnegato'
    team = 'L'
    aura = 'W'


class Sequestratore(Role):
    name = 'Sequestratore'
    team = 'L'
    aura = 'B'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        targets = self.player.game.get_alive_players().exclude(pk=self.pk)
        if self.last_usage is not None and self.days_from_last_usage <= 1:
            targets = targets.exclude(pk=self.last_target.pk)
        return targets


# Fazione dei Negromanti

class Negromante(Role):
    name = 'Negromante'
    team = 'N'
    is_mystic = True
    
    def can_use_power(self):
        # TODO: aggiungere la condizione sul fatto che non siano stati creati spettri durante la notte precedente
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)
    
    # TODO: gestire la scelta del potere dello spettro


class Fantasma(Role):
    name = 'Fantasma'
    team = 'N'


class Ipnotista(Role):
    name = 'Ipnotista'
    team = 'N'
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Medium(Role):
    name = 'Medium'
    team = 'N'
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Spettro(Role):
    name = 'Spettro'
    team = 'N'
    
    def can_use_power(self):
        # TODO: aggiungere informazioni sul potere soprannaturale
        return not self.player.alive






