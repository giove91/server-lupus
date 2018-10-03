from .base import *
from ..constants import *

class Rules(Rules):
    needs_spectral_sequence = True
    display_votes = False
    mayor = False
    forgiving_failures = True
    strict_quorum = True

    @staticmethod
    def post_death(dynamics, player):
        if player.team == POPOLANI and len(dynamics.spectral_sequence) > 0:
            if dynamics.spectral_sequence.pop(0):
                from ..events import GhostificationEvent, RoleKnowledgeEvent
                dynamics.generate_event(GhostificationEvent(player=player, ghost=Delusione, cause=SPECTRAL_SEQUENCE))
                for negromante in dynamics.players:
                    if negromante.role.necromancer:
                        dynamics.generate_event(RoleKnowledgeEvent(player=player,
                                                                   target=negromante,
                                                                   role_class=negromante.role.__class__,
                                                                   cause=GHOST))
                        dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                                   target=player,
                                                                   role_class=Delusione,
                                                                   cause=SPECTRAL_SEQUENCE))


##############
#  POPOLANI  #
##############

class Contadino(Contadino):
    pass

class Divinatore(Divinatore):
    frequency = EVERY_OTHER_NIGHT
    priority = QUERY
    targets = ALIVE
    targets_role_class = ALIVE

    def apply_dawn(self, dynamics):
        if dynamics.get_apparent_role(self.recorded_target) == self.recorded_role_class:
            from ..events import RoleKnowledgeEvent
            dynamics.generate_event(RoleKnowledgeEvent(target=self.recorded_target, player=self.player, role_class=self.recorded_role_class, cause=SOOTHSAYER))
        else:
            from ..events import NegativeRoleKnowledgeEvent
            dynamics.generate_event(NegativeRoleKnowledgeEvent(target=self.recorded_target, player=self.player, role_class=self.recorded_role_class, cause=SOOTHSAYER))

    def needs_soothsayer_propositions(self):
        from ..events import SoothsayerModelEvent
        events = SoothsayerModelEvent.objects.filter(soothsayer=self.player)
        if len([ev for ev in events if ev.target == ev.soothsayer]) > 0:
            return KNOWS_ABOUT_SELF
        if len(events) != 4:
            return NUMBER_MISMATCH
        truths = [isinstance(ev.target.canonicalize().role, ev.advertised_role) for ev in events]
        if not (False in truths) or not (True in truths):
            return TRUTH_MISMATCH

        return False

class Esorcista(Esorcista):
    pass

class Espansivo(Espansivo):
    pass

class Guardia(Guardia):
    pass

class Investigatore(Investigatore):
    frequency = EVERY_OTHER_NIGHT

    def apply_dawn(self, dynamics):
        from ..events import RoleKnowledgeEvent
        dynamics.generate_event(RoleKnowledgeEvent(player=self.player, target=self.recorded_target, role_class=dynamics.get_apparent_role(self.recorded_target), cause=DETECTIVE))

class Mago(Mago):
    pass

class Massone(Massone):
    pass

class Messia(Messia):
    pass

class Sciamano(Sciamano):
    pass

class Stalker(Stalker):
    pass

class Spia(Role):
    name = 'Spia'
    aura = WHITE
    team = POPOLANI
    priority = QUERY
    frequency = EVERY_NIGHT
    can_act_first_night = False
    targets = ALIVE

    def apply_dawn(self, dynamics):
        from ..events import VoteKnowledgeEvent, VoteAnnouncedEvent
        votes = [event for event in dynamics.events if
            isinstance(event, VoteAnnouncedEvent) and
            event.voter == self.recorded_target and
            event.type == VOTE and
            event.turn == dynamics.current_turn.prev_turn().prev_turn()
        ]
        assert len(votes) <= 1
        if votes:
            dynamics.generate_event(VoteKnowledgeEvent(player=self.player, voter=self.recorded_target, voted=votes[0].voted, cause=SPY))
        else:
            dynamics.generate_event(VoteKnowledgeEvent(player=self.player, voter=self.recorded_target, voted=None, cause=SPY))

class Trasformista(Trasformista):
    def pre_apply_dawn(self, dynamics):
        return dynamics.get_apparent_role(self.recorded_target).team == POPOLANI

class Veggente(Veggente):
    pass

class Voyeur(Voyeur):
    pass

##############
#    LUPI    #
##############

class Lupo(Lupo):
    required = True

    # Lupi can kill everybody! Yay!
    def pre_apply_dawn(self, dynamics):
        if dynamics.wolves_agree is None:
            dynamics.wolves_agree = dynamics.check_common_target([x for x in dynamics.get_alive_players() if isinstance(x.role, Lupo)])

        if dynamics.wolves_agree:
            # Check protection by Guardia
            if self.recorded_target.protected_by_guard:
                return False

        else:
            # Check if wolves tried to strike, but they didn't agree
            if self.recorded_target is not None:
                return False

        return True

class Assassino(Assassino):
    pass

class Avvocato(Avvocato):
    pass

class Diavolo(Diavolo):
    targets_multiple_role_class = ALIVE

    def pre_apply_dawn(self, dynamics):
        # Will not fail on Negromenti
        return True

    def apply_dawn(self, dynamics):
        from ..events import MultipleRoleKnowledgeEvent
        dynamics.generate_event(MultipleRoleKnowledgeEvent(
                player=self.player,
                target=self.recorded_target,
                multiple_role_class=self.recorded_multiple_role_class,
                response=dynamics.get_apparent_role(self.recorded_target) in self.recorded_multiple_role_class,
                cause=DEVIL
        ))

class Fattucchiera(Fattucchiera):
    message_role = 'Fallo apparire come:'
    targets = EVERYBODY
    targets_role_class = ALIVE

    def apply_dawn(self, dynamics):
        role = self.recorded_role_class
        target = self.recorded_target.canonicalize()
        target.apparent_aura = role.aura
        target.apparent_mystic = role.is_mystic
        target.apparent_role = role
        target.apparent_team = role.team

class Alcolista(Rinnegato):
    name = 'Alcolista'
    frequency = EVERY_NIGHT
    priority = QUERY_INFLUENCE # Mah
    targets = EVERYBODY

    def pre_apply_dawn(self, dynamics):
        return False # Lol

    def apply_dawn(self, dynamics):
        pass #out

class Necrofilo(Necrofilo):
    pass

class Sequestratore(Sequestratore):
    pass

class Stregone(Stregone):
    pass

##############
# NEGROMANTI #
##############

class Negromante(Negromante):
    priority = POST_MORTEM
    has_power = True
    required = True
    message_role = 'Assegna il seguente potere soprannaturale:'

    def can_use_power(self):
        if not self.player.alive:
            return self.has_power

        return True

    def get_targets_role_class(self):
        powers = {Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia}
        dynamics = self.player.game.get_dynamics()
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def pre_apply_dawn(self, dynamics):
        if self.player.alive:
            return self.recorded_target.role.ghost
        else:
            return True

    def apply_dawn(self, dynamics):
        if self.recorded_target.role.ghost:
            from ..events import GhostSwitchEvent
            dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=self.recorded_role_class, cause=NECROMANCER))
        else:
            assert not self.player.alive
            from ..events import GhostificationEvent
            dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_role_class, cause=NECROMANCER))

        if not self.player.alive:
            self.has_power = False

class Fantasma(Fantasma):
    # We must refer to the correct definitions of the powers
    def get_valid_powers(self):
        return {Amnesia, Confusione, Illusione, Ipnosi, Occultamento, Visione}

class Delusione(Spettro):
    # Spettro yet to be initialized (or who has lost his power).
    frequency = NEVER
    priority = USELESS
    allow_duplicates = True

class Amnesia(Amnesia):
    frequency = EVERY_OTHER_NIGHT
    priority = MODIFY

    def apply_dawn(self, dynamics):
        self.recorded_target.has_permanent_amnesia = True

class Assoluzione(Spettro):
    name = "Spettro dell'Assoluzione"
    priority = MODIFY
    frequency = EVERY_OTHER_NIGHT
    targets = ALIVE

    def apply_dawn(self, dynamics):
        target = self.recorded_target.canonicalize()

        def vote_influence(ballots):
            for voter, voted in ballots.items():
                if voted == target:
                    ballots[voter] = None

            return ballots

        dynamics.vote_influences.append(vote_influence)

class Diffamazione(Spettro):
    name = "Spettro della Diffamazione"
    priority = MODIFY
    frequency = EVERY_NIGHT
    targets = ALIVE

    def apply_dawn(self, dynamics):
        assert self.has_power
        target = self.recorded_target.canonicalize()

        def fraud(ballots):
            if target.alive:
                for voter, voted in ballots.items():
                    if voted is None:
                        ballots[voter] = target
            return ballots

        dynamics.electoral_frauds.append(fraud)

class Confusione(Confusione):
    targets = EVERYBODY
    targets2 = None
    targets_role_class = ALIVE

    def apply_dawn(self, dynamics):
        role = self.recorded_role_class
        target = self.recorded_target
        target.apparent_aura = role.aura
        target.apparent_mystic = role.is_mystic
        target.apparent_role = role
        target.apparent_team = role.team

class Illusione(Illusione):
    def apply_dawn(self, dynamics):
        assert self.has_power

        assert self.recorded_target2.alive

        # Visiting: Stalker illusion, we have to replace the
        # original location
        self.recorded_target2.visiting = [self.recorded_target]

        # Visitors: Voyeur illusion, we have to add to the
        # original list
        if self.recorded_target2 not in self.recorded_target.visitors:
            self.recorded_target.visitors.append(self.recorded_target2)

        if self.recorded_target2.role.recorded_target is not None and self.recorded_target2 in self.recorded_target2.role.recorded_target.visitors:
            self.recorded_target2.role.recorded_target.visitors.remove(self.recorded_target2)

        dynamics.illusion = (self.recorded_target2, self.recorded_target)

class Occultamento(Occultamento):
    pass

class Telepatia(Spettro):
    priority = EVENT_INFLUENCE
    frequency = EVERY_OTHER_NIGHT
    targets = ALIVE

    def apply_dawn(self, dynamics):
        def trigger(event):
            if hasattr(event, 'player') and event.player == self.recorded_target:
                from ..events import TelepathyEvent
                dynamics.generate_event(TelepathyEvent(player=self.player, perceived_event=event))

        dynamics.post_event_triggers.append(trigger)

