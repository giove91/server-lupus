from django.db import models
from models import Role, Player
from constants import *


# Fazione dei Popolani

class Contadino(Role):
    name = 'Contadino'
    team = POPOLANI
    aura = WHITE


class Cacciatore(Role):
    name = 'Cacciatore'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Custode(Role):
    name = 'Custode del cimitero'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Divinatore(Role):
    name = 'Divinatore'
    team = POPOLANI
    aura = WHITE
    is_mystic = True


class Esorcista(Role):
    name = 'Esorcista'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    message = 'Benedici la casa di:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()


class Espansivo(Role):
    name = 'Espansivo'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Guardia(Role):
    name = 'Guardia'
    team = POPOLANI
    aura = WHITE
    
    message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Investigatore(Role):
    name = 'Investigatore'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Mago(Role):
    name = 'Mago'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players().exclude(pk=self.pk)


class Massone(Role):
    name = 'Massone'
    team = POPOLANI
    aura = WHITE


class Messia(Role):
    name = 'Messia'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Necrofilo(Role):
    name = 'Necrofilo'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Stalker(Role):
    name = 'Stalker'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Veggente(Role):
    name = 'Veggente'
    team = POPOLANI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Voyeur(Role):
    name = 'Voyeur'
    team = POPOLANI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


# Fazione dei Lupi

class Lupo(Role):
    name = 'Lupo'
    team = LUPI
    aura = BLACK
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = LUPI
    aura = BLACK
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Diavolo(Role):
    name = 'Diavolo'
    team = LUPI
    aura = BLACK
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Fattucchiera(Role):
    name = 'Fattucchiera'
    team = LUPI
    aura = BLACK
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()


class Rinnegato(Role):
    name = 'Rinnegato'
    team = LUPI
    aura = WHITE


class Sequestratore(Role):
    name = 'Sequestratore'
    team = LUPI
    aura = BLACK
    
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
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        # TODO: aggiungere la condizione sul fatto che non siano stati creati spettri durante la notte precedente
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)
    
    def get_targets_ghost(self):
        used_powers = Player.objects.filter(role__role_name=Spettro.name)
        # TODO: gestire la scelta del potere dello spettro


class Fantasma(Role):
    name = 'Fantasma'
    team = NEGROMANTI
    aura = WHITE


class Ipnotista(Role):
    name = 'Ipnotista'
    team = NEGROMANTI
    aura = WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Medium(Role):
    name = 'Medium'
    team = NEGROMANTI
    aura = WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Spettro(Role):
    name = 'Spettro'
    team = NEGROMANTI
    aura = None
    
    POWER_NAMES = {
        AMNESIA: 'Amnesia',
        DUPLICAZIONE: 'Duplicazione',
        ILLUSIONE: 'Illusione',
        MISTIFICAZIONE: 'Mistificazione',
        MORTE: 'Morte',
        OCCULTAMENTO: 'Occultamento',
        OMBRA: 'Ombra',
        VISIONE: 'Visione',
    }
    
    POWERS_LIST = POWER_NAMES.items()
    
    power = models.CharField(max_length=1, choices=POWERS_LIST)
    has_power = models.BooleanField(default=True)   # Should be set to False when revived by the Messiah
    
    def can_use_power(self):
        # TODO: aggiungere informazioni sul potere soprannaturale
        return not self.player.alive and self.has_power
        return {
            AMNESIA: lambda: not self.player.alive and self.has_power,
            }[self.power]()






