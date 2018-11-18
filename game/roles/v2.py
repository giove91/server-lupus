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
    knowledge_class = 1
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
    knowledge_class = 1

    def apply_dawn(self, dynamics):
        from ..events import PlayerDiesEvent
        assert self.recorded_target is not None

        # Will target illusions
        movements = [mov for mov in dynamics.movements if mov.dst == self.recorded_target and mov is not self.player.movement]
        if len(movements) > 0:
            mov = dynamics.random.choice(movements)
            if mov is mov.src.movement and not mov.src.just_dead:
                assert mov.src.alive
                dynamics.generate_event(PlayerDiesEvent(player=mov.src, cause=ASSASSIN))

class Diavolo(Diavolo):
    knowledge_class = 1
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
    knowledge_class = 1
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
    knowledge_class = 1
    name = 'Alcolista'
    frequency = EVERY_NIGHT
    priority = QUERY_INFLUENCE # Mah
    targets = EVERYBODY

    def pre_apply_dawn(self, dynamics):
        return False # Lol

    def apply_dawn(self, dynamics):
        pass #out

class Sequestratore(Sequestratore):
    knowledge_class = 1
    def apply_dawn(self, dynamics):
        super().apply_dawn(dynamics)
        if self.recorded_target.movement in dynamics.movements:
            dynamics.movements.remove(self.recorded_target.movement)

        from ..events import MovementKnowledgeEvent, NoMovementKnowledgeEvent
        if self.recorded_target.movement is None or self.recorded_target.movement.dst is None:
            dynamics.generate_event(NoMovementKnowledgeEvent(player=self.player, target=self.recorded_target, cause=KIDNAPPER))
        else:
            dynamics.generate_event(MovementKnowledgeEvent(player=self.player, target=self.recorded_target, target2=None, cause=KIDNAPPER))

class Stregone(Stregone):
    knowledge_class = 1
    pass

##############
# NEGROMANTI #
##############

class Negromante(Negromante):
    knowledge_class = 4
    priority = POST_MORTEM
    frequency = EVERY_NIGHT
    required = True
    message_role = 'Lancia il seguente incantesimo:'

    def get_targets(self):
        return [player for player in self.player.game.get_active_players() if player.specter and player.pk != self.player.pk]

    def get_targets_role_class(self):
        powers = {Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia, Vita}
        dynamics = self.player.game.get_dynamics()
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def pre_apply_dawn(self, dynamics):
        if self.recorded_role_class in dynamics.used_ghost_powers:
            return False
        if not self.recorded_target.specter:
            return False

        return True

    def apply_dawn(self, dynamics):
        assert self.recorded_target.specter
        from ..events import GhostSwitchEvent
        dynamics.generate_event(GhostSwitchEvent(player=self.recorded_target, ghost=self.recorded_role_class, cause=NECROMANCER))

    def post_death(self, dynamics):
        if isinstance(self.player.dead_power, NoPower):
            self.player.dead_power = Spettrificazione(self.player)

class Spettrificazione(Role):
    name = "Spettrificazione"
    team = NEGROMANTI
    dead_power = True
    frequency = ONCE_A_GAME
    priority = POST_MORTEM
    targets = DEAD
    message_role = 'Lancia il seguente incantesimo:'

    def get_targets_role_class(self):
        powers = {Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia}
        dynamics = self.player.game.get_dynamics()
        available_powers = powers - dynamics.used_ghost_powers
        return available_powers

    def pre_apply_dawn(self, dynamics):
        if self.recorded_role_class in dynamics.used_ghost_powers:
            return False

        if self.recorded_target.specter:
            return False

        return True

    def apply_dawn(self, dynamics):
        assert not self.recorded_target.specter
        from ..events import GhostificationEvent
        dynamics.generate_event(GhostificationEvent(player=self.recorded_target, ghost=self.recorded_role_class, cause=NECROMANCER))

class Fantasma(Fantasma):
    knowledge_class = 4
    # We must refer to the correct definitions of the powers
    def get_valid_powers(self):
        return [Amnesia, Assoluzione, Confusione, Diffamazione, Illusione, Morte, Occultamento, Telepatia]

    def post_death(self, dynamics):
        powers = self.get_valid_powers()
        available_powers = [x for x in powers if x not in dynamics.used_ghost_powers]
        if len(available_powers) >= 1:
            power = dynamics.random.choice(available_powers)
        else:
            power = Delusione

        from ..events import RoleKnowledgeEvent, GhostificationEvent
        dynamics.generate_event(GhostificationEvent(player=self.player, cause=PHANTOM, ghost=power))
        for negromante in dynamics.players:
            if negromante.role.necromancer:
                dynamics.generate_event(RoleKnowledgeEvent(player=self.player,
                                                           target=negromante,
                                                           role_class=negromante.role.__class__,
                                                           cause=GHOST))
                dynamics.generate_event(RoleKnowledgeEvent(player=negromante,
                                                           target=self.player,
                                                           role_class=power,
                                                           cause=PHANTOM))

class Delusione(Spettro):
    # Spettro yet to be initialized.
    name = "Nessuno"
    verbose_name = "Spettro senza alcun Incantesimo attivo"
    frequency = NEVER
    priority = USELESS
    allow_duplicates = True

class Amnesia(Amnesia):
    frequency = EVERY_OTHER_NIGHT
    priority = MODIFY

    def apply_dawn(self, dynamics):
        self.recorded_target.has_permanent_amnesia = True

class Assoluzione(Spettro):
    name = "Assoluzione"
    verbose_name = 'Spettro con l\'Incantesimo dell\'Assoluzione'
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
    name = "Diffamazione"
    verbose_name = 'Spettro con l\'Incantesimo della Diffamazione'
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
    targets = ALIVE
    targets2 = EVERYBODY
    allow_target2_same_as_target = False

    def get_targets2(self):
        ret = self.player.game.get_dynamics().get_active_players()
        ret.append(None)
        return ret

    def apply_dawn(self, dynamics):
        assert self.has_power
        assert self.recorded_target != self.recorded_target2
        assert self.recorded_target.alive

        from ..dynamics import Movement
        if self.recorded_target.movement in dynamics.movements:
            dynamics.movements.remove(self.recorded_target.movement)

        if self.recorded_target2 is not None:
            illusion = Movement(src=self.recorded_target, dst=self.recorded_target2)
            assert self.recorded_target2.movement != illusion
            dynamics.movements.append(illusion)

class Morte(Morte):
    frequency = ONCE_A_GAME

    def pre_apply_dawn(self, dynamics):
        return True

    def apply_dawn(self, dynamics):
        if not self.recorded_target.just_dead:
            assert self.recorded_target.alive
            from ..events import PlayerDiesEvent, UnGhostificationEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.recorded_target, cause=DEATH_GHOST))
            dynamics.generate_event(UnGhostificationEvent(player=self.player))

class Occultamento(Occultamento):
    pass

class Telepatia(Spettro):
    name = 'Telepatia'
    verbose_name = 'Spettro con l\'Incantesimo della Telepatia'
    priority = EVENT_INFLUENCE
    frequency = EVERY_OTHER_NIGHT
    targets = ALIVE

    def apply_dawn(self, dynamics):
        def trigger(event):
            if hasattr(event, 'player') and event.player == self.recorded_target:
                from ..events import TelepathyEvent
                dynamics.generate_event(TelepathyEvent(player=self.player, perceived_event=event))

        dynamics.post_event_triggers.append(trigger)

class Vita(Spettro):
    name = 'Vita'
    verbose_name = 'Spettro con l\'Incantesimo della Vita'
    priority = USELESS

    def post_appearance(self, dynamics):
        assert not self.player.alive
        from ..events import PlayerResurrectsEvent
        dynamics.generate_event(PlayerResurrectsEvent(player=self.player))

    def pre_disappearance(self, dynamics):
        if self.player.alive:
            from ..events import PlayerDiesEvent
            dynamics.generate_event(PlayerDiesEvent(player=self.player, cause=LIFE_GHOST))

    def post_death(self, dynamics):
        from ..events import GhostSwitchEvent
        dynamics.generate_event(GhostSwitchEvent(player=self.player, ghost=Delusione, cause=LIFE_GHOST))

## ORDER COSTRAINTS
#
# Necromancers must act after every other ghost.
# If not, they will change power before they can use it.
