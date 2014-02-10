from django.db import models
from models import Role, Player, Global


# Fazione dei Popolani

class Contadino(Role):
    name = 'Contadino'
    team = Global.POPOLANI
    aura = Global.WHITE


class Cacciatore(Role):
    name = 'Cacciatore'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Custode(Role):
    name = 'Custode del cimitero'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Divinatore(Role):
    name = 'Divinatore'
    team = Global.POPOLANI
    aura = Global.WHITE
    is_mystic = True


class Esorcista(Role):
    name = 'Esorcista'
    team = Global.POPOLANI
    aura = Global.WHITE
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
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Guardia(Role):
    name = 'Guardia'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    message = 'Proteggi:'
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Investigatore(Role):
    name = 'Investigatore'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Mago(Role):
    name = 'Mago'
    team = Global.POPOLANI
    aura = Global.WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players().exclude(pk=self.pk)


class Massone(Role):
    name = 'Massone'
    team = Global.POPOLANI
    aura = Global.WHITE


class Messia(Role):
    name = 'Messia'
    team = Global.POPOLANI
    aura = Global.WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Necrofilo(Role):
    name = 'Necrofilo'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive and self.last_usage is None
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Stalker(Role):
    name = 'Stalker'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Veggente(Role):
    name = 'Veggente'
    team = Global.POPOLANI
    aura = Global.WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Voyeur(Role):
    name = 'Stalker'
    team = Global.POPOLANI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


# Fazione dei Lupi

class Lupo(Role):
    name = 'Lupo'
    team = Global.LUPI
    aura = Global.BLACK
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Avvocato(Role):
    name = 'Avvocato del diavolo'
    team = Global.LUPI
    aura = Global.BLACK
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Diavolo(Role):
    name = 'Diavolo'
    team = Global.LUPI
    aura = Global.BLACK
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Fattucchiera(Role):
    name = 'Fattucchiera'
    team = Global.LUPI
    aura = Global.BLACK
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_active_players()


class Rinnegato(Role):
    name = 'Rinnegato'
    team = Global.LUPI
    aura = Global.WHITE


class Sequestratore(Role):
    name = 'Sequestratore'
    team = Global.LUPI
    aura = Global.BLACK
    
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
    team = Global.NEGROMANTI
    aura = Global.WHITE
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
    team = Global.NEGROMANTI
    aura = Global.WHITE


class Ipnotista(Role):
    name = 'Ipnotista'
    team = Global.NEGROMANTI
    aura = Global.WHITE
    
    def can_use_power(self):
        return self.player.alive and ( self.last_usage is None or self.days_from_last_usage() >= 2 )
    
    def get_targets(self):
        return self.player.game.get_alive_players().exclude(pk=self.pk)


class Medium(Role):
    name = 'Medium'
    team = Global.NEGROMANTI
    aura = Global.WHITE
    is_mystic = True
    
    def can_use_power(self):
        return self.player.alive
    
    def get_targets(self):
        return self.player.game.get_dead_players().exclude(pk=self.pk)


class Spettro(Role):
    name = 'Spettro'
    team = Global.NEGROMANTI
    aura = None
    
    AMNESIA = 'A'
    DUPLICAZIONE = 'D'
    ILLUSIONE = 'I'
    MISTIFICAZIONE = 'M'
    MORTE = 'R'
    OCCULTAMENTO = 'O'
    OMBRA = 'B'
    VISIONE = 'V'
    
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
    
    POWERS_LIST = (
        (AMNESIA, POWER_NAMES[AMNESIA]),
        (DUPLICAZIONE, POWER_NAMES[DUPLICAZIONE]),
        (ILLUSIONE, POWER_NAMES[ILLUSIONE]),
        (MISTIFICAZIONE, POWER_NAMES[MISTIFICAZIONE]),
        (MORTE, POWER_NAMES[MORTE]),
        (OCCULTAMENTO, POWER_NAMES[OCCULTAMENTO]),
        (OMBRA, POWER_NAMES[OMBRA]),
        (VISIONE, POWER_NAMES[VISIONE]),
    )
    
    power = models.CharField(max_length=1, choices=POWERS_LIST)
    has_power = models.BooleanField(default=True)   # Should be set to False when revived by the Messiah
    
    def can_use_power(self):
        # TODO: aggiungere informazioni sul potere soprannaturale
        return not self.player.alive and self.has_power






