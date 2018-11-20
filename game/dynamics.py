# -*- coding: utf-8 -*-

import sys
import logging

from django.db.models import Q

from threading import RLock
from datetime import datetime, timedelta
import time

from .models import Event, Turn
from .events import CommandEvent, VoteAnnouncedEvent, TallyAnnouncedEvent, \
    SetMayorEvent, PlayerDiesEvent, PowerOutcomeEvent, StakeFailedEvent, \
    ExileEvent, VictoryEvent, AvailableRoleEvent, RoleKnowledgeEvent
from .constants import *
from .utils import get_now

SIMULATE_NEXT_TURN = True
FORCE_SIMULATION = False # Enable only while running tests
RELAX_TIME_CHECKS = False
ANCIENT_DATETIME = datetime(year=1970, month=1, day=1, tzinfo=REF_TZINFO)
UPDATE_INTERVAL = timedelta(seconds=1)

# When SINGLE_MODE is set, at most one dynamics can act concurrently
# on the same game; when SINGLE_MODE is not set automatic events won't
# be written to the database, so many dynamics can act concurrently;
# when switching from single mode to non single mode, all automatic
# events have to be deleted from the database
SINGLE_MODE = False

logger = logging.getLogger(__name__)

class Movement:
    def __repr__(self):
        return "%r (%r) => %r (%r) %s" % (self.src, self.src.power.name, self.dst, self.dst.power.name, "[Illusione]" if self != self.src.movement else "")
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

class Dynamics:
    def __repr__(self):
        return hex(id(self))

    def __init__(self, game):
        self.logger = logging.LoggerAdapter(logger, {'dynamics': hex(id(self))})
        self.logger.info("New dynamics for game %(game)s spawned!" % {'game':game.name, 'self':self})
        self.spawned_at = time.time()
        self.game = game
        self.check_mode = False  # Not supported at the moment
        self.update_lock = RLock()
        self.event_num = 0
        self._updating = False
        self.debug_event_bin = None
        self.auto_event_queue = []
        self.db_event_queue = []
        self.simulating = False
        self.simulated = False
        self.simulated_turn = None
        self.simulated_events = []
        self.events = []
        self.turns = []
        self.failed = False

        self.initialize_augmented_structure()

        """# If in single mode, delete all automatic events
        if SINGLE_MODE:
            for event in Event.objects.all():
                event = event.as_child()
                if event.AUTOMATIC:
                    self.logger.debug("Deleting event %r" % (event))
                    event.delete()

        # Otherwise expect that there are no automatic events in the
        # database
        else:
            for event in Event.objects.all():
                event = event.as_child()
                assert not event.AUTOMATIC, "Please delete automatic events from database using delete_automatic_events.py"
        """

    def initialize_augmented_structure(self):
        self.players = list(self.game.player_set.order_by('pk'))
        self.players_dict = {}
        self.random = None
        self.current_turn = None
        self.prev_turn = None
        self.last_timestamp_in_turn = None
        self.last_pk_in_turn = None
        self.last_update = ANCIENT_DATETIME
        self.mayor = None
        self.appointed_mayor = None
        self.pre_simulation_mayor = None
        self.pre_simulation_appointed_mayor = None
        self.available_roles = []
        self.assignements_per_role = {}
        self.death_ghost_created = False
        self.death_ghost_just_created = False
        self.ghosts_created_last_night = False
        self.used_ghost_powers = set()
        self.spectral_sequence = None
        self.giove_is_happy = False
        self.server_is_on_fire = False  # so far...
        self.sasha_is_sleeping = False  # usually...
        self.playing_teams = []
        self.dying_teams = []
        self.recorded_winners = None
        self.illusion = None
        self.wolves_agree = None
        self.necromancers_agree = None
        self.vote_influences = []
        self.electoral_frauds = []
        self.post_event_triggers = []
        self.sentence_modifications = []
        self.winners = None
        self.over = False
        self.upcoming_deaths = []
        self.pending_disqualifications = []
        self.movements = []
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
            player.dead_power = None
            player.specter = False
            player.aura = None
            player.is_mystic = None
            player.alive = True
            player.active = True
            player.disqualified = False
            player.canonical = True
            player.recorded_vote = None
            player.recorded_elect = None
            player.apparent_mystic = None
            player.apparent_aura = None
            player.apparent_role = None
            player.apparent_team = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.temp_dehypnotized = False
            player.just_dead = False
            player.just_ghostified = False
            player.just_transformed = False
            player.just_resurrected = False
            player.hypnotist = None
            player.has_permanent_amnesia = False
            player.has_confusion = False
            player.cooldown = False

    def get_active_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return [player for player in self.players if player.active]

    def get_inactive_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return [player for player in self.players if not player.active]

    def get_alive_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return [player for player in self.players if player.alive and player.active]

    def get_dead_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return [player for player in self.players if not player.alive and player.active]

    def get_canonical_player(self, player):
        return self.players_dict[player.pk]


    def get_apparent_aura(self, player):
        return player.apparent_aura

    def get_apparent_mystic(self, player):
        return player.apparent_mystic

    def get_apparent_role(self, player):
        return player.apparent_role

    def get_apparent_team(self, player):
        return player.apparent_team

    def update(self, simulation=False, lazy=False):
        # If dynamics was updated recently, don't try again to save time
        if lazy and self.last_update + UPDATE_INTERVAL > get_now():
            return

        self.last_update = get_now()
        with self.update_lock:
            try:
                if self._updating:
                    return
                self._updating = True
                while self._update_step():
                    pass
                if simulation or FORCE_SIMULATION:
                    self._simulate_next_turn()
                self._updating = False
            except Exception:
                self.failed = True
                raise
        if self.spawned_at:
            self.logger.info('First updating finished. Elapsed time: %r' % (time.time() - self.spawned_at))
            self.spawned_at = None


    def _pop_event_from_db(self):
        self.logger.debug("Searching db for events in %r after %s an with pk>%s", self.current_turn, self.last_timestamp_in_turn, self.last_pk_in_turn)
        if len(self.db_event_queue) > 0:
            return self.db_event_queue.pop(0).as_child()

        try:
            result = Event.objects.filter(turn=self.current_turn). \
                filter(Q(timestamp__gt=self.last_timestamp_in_turn) |
                       (Q(timestamp__gte=self.last_timestamp_in_turn) & Q(pk__gt=self.last_pk_in_turn))). \
                       order_by('timestamp', 'pk')
            self.db_event_queue += result
            event = self.db_event_queue.pop(0)
        except IndexError:
            return None
        else:
            return event.as_child()

    def _pop_event_from_queue(self):
        if len(self.auto_event_queue) > 0:
            return self.auto_event_queue.pop(0)
        else:
            return None

    def _update_step(self, advancing_turn=False):
        # First check for new events in current turn
        if self.current_turn is not None:
            queued_event = self._pop_event_from_queue()
            if queued_event is not None:
                self.logger.debug("Receiving event %s from queue", queued_event)
                if self.debug_event_bin is not None and not self.simulating:
                    self.debug_event_bin.append(queued_event)
                if SINGLE_MODE:
                    queued_event.save()
                else:
                    queued_event.fill_subclass()
                self._receive_event(queued_event)
                return True
            else:
                # If there is not queued event and we're advancing
                # turn, do not process any other event
                if advancing_turn:
                    return False
                event = self._pop_event_from_db()
                if event is not None:
                    self.logger.debug("Found event %r from database", event)
                    self._receive_event(event)
                    return True

        # If we are advancing the turn right now, do now attempt to do
        # it twice
        if advancing_turn:
            return False

        # If no events were found, check for new turns
        try:
            if self.current_turn is not None:
                turn = self.current_turn.next_turn(must_exist=True)
            else:
                turn = Turn.first_turn(self.game, must_exist=True)
        except Turn.DoesNotExist:
            # Refresh turn since the end might have changed
            if self.current_turn is not None:
                self.current_turn.refresh_from_db()

            # Check if current_turn has ended: if so, automatically advance turn
            if self.current_turn is not None and self.current_turn.end is not None and self.current_turn.end <= get_now():
                self.game.advance_turn(current_turn=self.current_turn)
                return True
        else:
            self.turns.append(turn)
            self._receive_turn(turn)
            return True

        return False

    def _check_events_before_turn(self, turn):
        assert Event.objects.filter(turn=turn).filter(timestamp__lt=turn.begin).count() == 0

    def _receive_turn(self, turn):
        # Check that turn that is finishing did not have events before
        # the beginning
        if self.current_turn is not None:
            self._check_events_before_turn(self.current_turn)

        # Promote the new turn (we also update the old turn from the
        # database, since we expect that end might have been set since
        # last time we obtained it)
        if self.current_turn is not None:
            self.prev_turn = Turn.objects.get(pk=self.current_turn.pk)
        self.current_turn = turn

        # Create turn to be simulated
        if self.current_turn.phase in [DAY, NIGHT] and self.current_turn.end is not None:
            self.simulated_turn = self.current_turn.next_turn()
            self.simulated_turn.set_begin_end(self.current_turn)
        else:
            self.simulated_turn = None

        self.simulated_events = []

        # Debug print
        self.logger.info("Received turn %r", turn)

        # Do some checks on it
        assert self.current_turn.begin is not None
        if self.prev_turn is not None:
            assert self.prev_turn.begin is not None
            assert self.prev_turn.end is not None
            assert self.prev_turn.begin <= self.prev_turn.end, (self.prev_turn.begin, self.prev_turn.end)
            assert self.prev_turn.end == turn.begin
            if not RELAX_TIME_CHECKS:
                assert self.last_timestamp_in_turn <= self.prev_turn.end

        # Check for events before the beginning of the turn
        self._check_events_before_turn(self.current_turn)

        # Prepare data for checking events
        if RELAX_TIME_CHECKS:
            self.last_timestamp_in_turn = ANCIENT_DATETIME
        else:
            self.last_timestamp_in_turn = turn.begin
        self.last_pk_in_turn = -1

        # Perform phase-dependant entering
        {
            DAY: self._compute_entering_day,
            NIGHT: self._compute_entering_night,
            SUNSET: self._compute_entering_sunset,
            DAWN: self._compute_entering_dawn,
            CREATION: self._compute_entering_creation,
            }[self.current_turn.phase]()

    def _simulate_next_turn(self):
        """
        Simulate following turn.
        This will work only if simulated turn is in the dynamics, which means that:
        * Current turn must be DAY or NIGHT
        * Current turn must have end.
        During simulation, only events with flag CAN_BE_SIMULATED are applied.
        Events are not saved in self.events, but in self.simulated_events instead.
        All changes to dynamics are (or at least they should be) reverted after simulation is complete.
        This includes the pseudorandom number generator, which is set back to its previous state,
        to guarantee that dynamics is deterministic.

        In case of problems, set SIMULATE_NEXT_TURN to False to disable simulation.
        """
        if not FORCE_SIMULATION and (not SIMULATE_NEXT_TURN or self.simulated):
            return
        if self.simulated_turn is None:
            self.simulated = True
            return
        self.simulating = True
        self.logger.info("Simulating turn %s", self.simulated_turn)
        self.simulated_events = []
        # Copy random status
        random_state = self.random.getstate()

        # Save last processed event
        real_last_timestamp_in_turn = self.last_timestamp_in_turn
        real_last_pk_in_turn = self.last_pk_in_turn

        # Save mayor
        pre_simulation_mayor = self.mayor
        pre_simulation_appointed_mayor = self.appointed_mayor

        # Temporarily promote
        real_current_turn = self.current_turn
        real_prev_turn = self.prev_turn
        self.current_turn = self.simulated_turn
        self.prev_turn = real_current_turn

        # Prepare data for checking events
        if RELAX_TIME_CHECKS:
            self.last_timestamp_in_turn = ANCIENT_DATETIME
        else:
            self.last_timestamp_in_turn = self.current_turn.begin
        self.last_pk_in_turn = -1

        assert self.simulated_turn.phase in [DAWN,SUNSET], self.simulated_turn
        {
            SUNSET: self._compute_entering_sunset,
            DAWN: self._compute_entering_dawn,
            }[self.simulated_turn.phase]()

        # Rollback turn
        self.current_turn = real_current_turn
        self.prev_turn = real_prev_turn

        # Get back timestamp and pk
        self.last_timestamp_in_turn = real_last_timestamp_in_turn
        self.last_pk_in_turn = real_last_pk_in_turn


        # Rollback mayor changes
        self.mayor = pre_simulation_mayor
        self.appointed_mayor = pre_simulation_appointed_mayor
        self.pre_simulation_mayor = None
        self.pre_simulation_appointed_mayor = None

        # Rollback random object
        self.random.setstate(random_state)

        self.simulating = False
        self.simulated = True


    def _receive_event(self, event):
        # Preliminary checks on the context
        assert self.current_turn is not None
        assert event.turn == self.current_turn

        # Debug prints
        self.logger.info("Received event %r, timed %s", event, event.timestamp)
        if isinstance(event, AvailableRoleEvent):
            self.logger.debug("  Available role: %s", event.role_class.name)

        # Do some check on the new event
        if not RELAX_TIME_CHECKS:
            assert event.timestamp >= self.current_turn.begin
        if not event.AUTOMATIC or SINGLE_MODE:
            assert (event.timestamp > self.last_timestamp_in_turn) or \
                (event.timestamp >= self.last_timestamp_in_turn and event.pk >= self.last_pk_in_turn), \
                repr((event.timestamp, self.last_timestamp_in_turn, event.pk, self.last_pk_in_turn))
            self.last_timestamp_in_turn = event.timestamp
            self.last_pk_in_turn = event.pk
        else:
            assert event.timestamp >= self.last_timestamp_in_turn, (event.timestamp, self.last_timestamp_in_turn)
            self.last_timestamp_in_turn = event.timestamp
        assert self.current_turn.phase in event.RELEVANT_PHASES

        # Process the event
        if not self.simulating:
            self._process_event(event)
            self.events.append(event)
            self.event_num += 1
        else:
            self._simulate_event(event)

    def _process_event(self, event):
        self.simulated = False
        event.apply(self)
        if event.to_player_string('admin') is not None:
            self.logger.debug("> %s",event.to_player_string('admin'))

    def _simulate_event(self, event):
        if event.CAN_BE_SIMULATED:
            event.apply(self)

    def inject_event(self, event):
        """This is for non automatic events."""
        assert not event.AUTOMATIC
        assert self.current_turn.phase in event.RELEVANT_PHASES
        event.turn = self.current_turn
        if event.timestamp is None:
            event.timestamp = get_now()
        event.save()

        if self.debug_event_bin is not None:
            self.debug_event_bin.append(event)
        self.update()

    def generate_event(self, event):
        """This is for automatic events."""
        assert event.AUTOMATIC
        assert self.current_turn.phase in event.RELEVANT_PHASES
        event.turn = self.current_turn
        if event.timestamp is None:
            event.timestamp = self.last_timestamp_in_turn

        if self.simulating:
            self.simulated_events.append(event)

        self.auto_event_queue.append(event)
        for trigger in self.post_event_triggers:
            trigger(event)

    def _compute_entering_creation(self):
        self.logger.debug("Computing creation")

    def _checks_after_creation(self):
        # You shall generate no events here!

        # Check that all teams are represented
        self.playing_teams = self._count_alive_teams()
        assert sorted(self.playing_teams) == sorted(self.rules.teams)
        for role in self.valid_roles:
            if role.required:
                assert role in {x.role.__class__ for x in self.players}

        for player in self.players:
            assert not player.role.needs_soothsayer_propositions()

        assert not self.check_missing_spectral_sequence()

    def check_missing_spectral_sequence(self):
        """Check if the spectral sequence is requested, and if so check if it's
        been provided.
        """
        return self.rules.needs_spectral_sequence and self.spectral_sequence is None

    def check_missing_soothsayer_propositions(self):
        """Check that the soothsayer received revelations according to
        the rules.
        If everything is ok it returns None,
        else returns a player that is missing propositions.
        Raises an exception if a player received more proposition than
        required or if they don't satisfy the rules."""

        for player in self.players:
            if player.role.needs_soothsayer_propositions():
                return player

        return None

    def _compute_entering_night(self):
        self.logger.debug("Computing night")

        # Before first night check that creation went ok
        first_night_date = FIRST_DATE
        if DATE_CHANGE_PHASE == NIGHT:
            first_night_date = first_night_date + 1
        if self.current_turn.date == first_night_date:
            self._checks_after_creation()

        self._check_team_exile()

    def _solve_blockers(self, critical_blockers, block_graph, rev_block_graph):
        # First some checks and build the reverse graph
        critical_pks = [x.pk for x in critical_blockers]
        for src, dsts in iter(block_graph.items()):
            for dst in dsts:
                assert dst != src
                assert src in rev_block_graph[dst]

        def iter_competitors():
            current = dict([(x.pk, True) for x in critical_blockers])
            while True:
                yield current.copy()
                for i in critical_pks:
                    current[i] = not current[i]
                    if not current[i]:
                        break
                else:
                    return

        # Start generating competitors
        min_score = len(critical_blockers) + 1
        minimizers = None
        for competitor in iter_competitors():
            self.logger.debug("  competitor: %r", competitor)
            score = 0
            skip = False
            for src, success in iter(competitor.items()):
                # If this player succeeds, we have to check that its
                # blocks are successful
                if success:
                    for dst in block_graph[src]:
                        if dst in critical_pks and competitor[dst]:
                            skip = True
                            break
                    if skip:
                        break

                # If it fails, we have to count whether this is
                # justified or not
                else:
                    for dst in rev_block_graph[src]:
                        if dst in critical_pks and competitor[dst]:
                            break
                    else:
                        score += 1

            self.logger.debug("    skip: %r", skip)
            self.logger.debug("    score: %r", score)

            # Finally, count the score of this competitor
            if not skip:
                if score == min_score:
                    minimizers.append(competitor)
                elif score < min_score:
                    minimizers = [competitor]
                    min_score = score

        # Choose a random minimizing competitor
        self.logger.debug("  minimizers: %r", minimizers)
        self.logger.debug("  min_score: %r", min_score)
        return self.random.choice(minimizers)

    def check_common_target(self, players):
        target = None
        role_class = None
        for player in players:
            role = player.power
            if role.recorded_target is not None:
                if target is None:
                    target = role.recorded_target
                    role_class = role.recorded_role_class
                elif target.pk != role.recorded_target.pk:
                    return False
                elif role_class != role.recorded_role_class:
                    return False
            else:
                assert role.recorded_role_class is None

        return True

    def _compute_entering_dawn(self):
        self.logger.debug("Computing dawn")

        self.ghosts_created_last_night = False

        # Prepare temporary status
        self.wolves_agree = None
        self.necromancers_agree = None
        for player in self.get_active_players():
            player.apparent_aura = player.aura
            player.apparent_mystic = player.is_mystic
            player.apparent_role = player.role.__class__
            player.apparent_team = player.team
            player.movement = None
            # Restore cooldown for EVERY_OTHER_NIGHT powers
            if not self.simulating:
                player.cooldown = False

        # So, here comes the big little male house ("gran casino");
        # first of all we consider powers that can block powers that
        # can block powers: Spettro dell'Occultamento, Sequestratore,
        # Sciamano, Esorcista, Stregone

        # Build the list of blockers
        critical_blockers = [player for player in self.get_active_players() if player.power.critical_blocker and player.power.recorded_target is not None]

        # Build the block graph and compute blocking success
        block_graph = dict([(x.pk, x.power.get_blocked(self.players)) for x in self.players])
        rev_block_graph = dict([(x.pk, []) for x in self.players])
        for x, ys in iter(block_graph.items()):
            for y in ys:
                rev_block_graph[y].append(x)
        blockers_success = self._solve_blockers(critical_blockers, block_graph, rev_block_graph)
        self.logger.debug("  block_graph: %r", block_graph)
        self.logger.debug("  rev_block_graph: %r", rev_block_graph)
        self.logger.debug("  blockers_success: %r", blockers_success)

        # Extend the success status to all players
        powers_success = dict([(x.pk, True) for x in self.players])
        powers_success.update(blockers_success)
        for src, success in iter(blockers_success.items()):
            if success:
                for dst in block_graph[src]:
                    if dst in blockers_success:
                        assert not powers_success[dst]
                    else:
                        powers_success[dst] = False
        self.logger.debug("  powers_success: %r", powers_success)

        # Then compute the visit graph
        for player in self.get_active_players():
            if player.power.recorded_target is not None and player.alive:
                mov = Movement(src=player, dst=player.power.recorded_target)
                self.movements.append(mov)
                player.movement = mov
        self.logger.debug("  movements: %r", dict([(x.src, x.dst) for x in self.movements]))

        # Utility methods for later
        def apply_role(player):
            assert (player.alive) != (player.power.dead_power)
            if player.power.recorded_target is None:
                return
            self.logger.debug("  > Applying role %r for %r:", player.power, player)
            success = powers_success[player.pk]
            if success:
                success = player.power.pre_apply_dawn(self)
                self.logger.debug("    Success!" if success else "    Conditions for applying role not met!")
            else:
                self.logger.debug("    Power blocked!")
            event = PowerOutcomeEvent(player=player, success=success, command=player.power.recorded_command, power=player.power.__class__)
            self.generate_event(event)
            if success:
                player.power.apply_dawn(self)

        players = self.get_active_players()
        self.random.shuffle(players)
        players.sort(key=lambda x:x.power.priority)
        for player in players:
            assert player.power.priority is not None
            apply_role(player)
            while self._update_step(advancing_turn=True):
                pass

        # Unset (nearly) all temporary status
        self.wolves_agree = None
        self.necromancers_agree = None
        self.movements = []
        for player in self.players:
            if not self.simulating:
                player.power.unrecord_targets()
            player.apparent_aura = None
            player.apparent_mystic = None
            player.apparent_role = None
            player.apparent_team = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.movement = None
            player.just_ghostified = False
            player.just_transformed = False
            player.just_resurrected = False
            player.has_confusion = False

        if self.simulating:
            # Remove useless state for following day
            self.sentence_modifications = []
            self.vote_influences = []
            self.electoral_frauds = []
            self.post_event_triggers = []
            for player in self.players:
                player.temp_dehypnotized = False
        else:

            self._end_of_main_phase()

    def _compute_entering_day(self):
        self.logger.debug("Computing day")

    def _compute_entering_sunset(self):
        self.logger.debug("Computing sunset")

        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            event = SetMayorEvent(player=new_mayor, cause=ELECT)
            self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

        assert self.upcoming_deaths == []

        winner, cause = self._compute_vote_winner()

        if winner is not None:
            event = PlayerDiesEvent(player=winner, cause=STAKE)
            self.generate_event(event)
        else:
            event = StakeFailedEvent(cause=cause)
            self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

        if not self.simulating:
            # Unrecord all data set during previous dawn
            self.sentence_modifications = []
            self.vote_influences = []
            self.electoral_frauds = []

            # Unrecord all elect and vote events, and remove hypnotist immunity
            for player in self.players:
                player.temp_dehypnotized = False
                player.recorded_vote = None
                player.recorded_elect = None

            self._end_of_main_phase()

    def _compute_elected_mayor(self):
        new_mayor = None

        # Count last ballot for each player
        ballots = {}
        for player in self.get_alive_players():
            ballots[player.pk] = player.recorded_elect

        # Fill the tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        for ballot in iter(ballots.values()):
            if ballot is None:
                continue
            tally_sheet[ballot.pk] += 1

        # Send announcements
        for player in self.get_alive_players():
            if ballots[player.pk] is not None:
                event = VoteAnnouncedEvent(voter=player.canonicalize(), voted=ballots[player.pk], type=ELECT)
                self.generate_event(event)
        for player in self.get_alive_players():
            if tally_sheet[player.pk] != 0:
                event = TallyAnnouncedEvent(voted=player.canonicalize(), vote_num=tally_sheet[player.pk], type=ELECT)
                self.generate_event(event)

        # Compute winners (or maybe loosers...)
        tally_sheet = sorted(tally_sheet.items(),key=lambda x: x[1], reverse=True)
        winner = tally_sheet[0][0]
        max_votes = tally_sheet[0][1]
        if max_votes * 2 > len(self.get_alive_players()):
            return self.players_dict[winner]
        else:
            return None

    def _compute_vote_winner(self):
        # Compute vote results.
        # Will check for additional effects, that must be functions
        # taking and returning a dict of ballots (when editing votes)
        # or a winner and a cause (when computing stake result)

        winner = None
        quorum_failed = False

        # Count last ballot for each player
        ballots = {}
        mayor_ballot = None
        for player in self.get_alive_players():
            ballots[player.pk] = player.recorded_vote

        # Apply effects that modify expressed vote.
        for func in self.vote_influences:
            ballots = func(ballots)

        # Apply effect of permanent_amnesia.

        for player in self.get_alive_players():
            if player.has_permanent_amnesia:
                ballots[player.pk] = None

        # Apply effects of hypnotization. Should hopefully work
        for player in self.get_alive_players():
            hypnotized_players = set()
            ancestor = player
            while ancestor.hypnotist is not None and ancestor.hypnotist.alive and \
                not ancestor.temp_dehypnotized and not ancestor.hypnotist in hypnotized_players:
                hypnotized_players.add(ancestor)
                ancestor = ancestor.hypnotist
            for pl in hypnotized_players:
                ballots[pl.pk] = ballots[ancestor.pk]

        # Apply effects that change vote examination
        for func in self.electoral_frauds:
            ballots = func(ballots)

        # Check mayor vote
        for player in self.get_alive_players():
            if player.is_mayor():
                mayor_ballot = ballots[player.pk]

        # Fill the tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        votes_num = 0
        for ballot in iter(ballots.values()):
            if ballot is None:
                continue
            tally_sheet[ballot.pk] += 1
            votes_num += 1

        # Send vote announcements
        for player in self.get_alive_players():
            for target in [target for target in self.get_alive_players() if target == ballots[player.pk]]:
                event = VoteAnnouncedEvent(voter=player, voted=target, type=VOTE)
                self.generate_event(event)

        # Send tally announcements
        for player in self.get_alive_players():
            if tally_sheet[player.pk] != 0:
                event = TallyAnnouncedEvent(voted=player, vote_num=tally_sheet[player.pk], type=VOTE)
                self.generate_event(event)

        # Compute winners (or maybe loosers...)
        tally_sheet = sorted(tally_sheet.items(),key=lambda x: x[1], reverse=True)
        max_votes = tally_sheet[0][1]

        if self.rules.strict_quorum:
            quorum_failed = max_votes * 2 <= len(self.get_alive_players())
        else:
            quorum_failed = votes_num * 2 < len(self.get_alive_players())

        if quorum_failed:
            winner_player = None
            cause = MISSING_QUORUM
        else:
            winners = [x[0] for x in tally_sheet if x[1] == max_votes]
            assert len(winners) > 0
            if mayor_ballot is not None and mayor_ballot.pk in winners:
                winner = mayor_ballot.pk
            else:
                winner = self.random.choice(winners)
            winner_player = self.players_dict[winner]
            cause = None

        # Check for effects that modify sentence
        for func in self.sentence_modifications:
            winner_player, cause = func(winner_player, cause)

        return winner_player, cause

    def _check_deaths(self):
        # We randomize deaths in order to mix Fantasmi and Ipnotisti
        self.random.shuffle(self.upcoming_deaths)

        for event in self.upcoming_deaths:
            event.apply_death(self)

            # Process events at each iteration, because subsequent
            # death computations may depend on everything before have
            # cleared out
            while self._update_step(advancing_turn=True):
                pass

    def _perform_disqualifications(self):
        # We randomize, just to avoid revealing random information to
        # the other players
        self.random.shuffle(self.pending_disqualifications)

        self.logger.debug("Computing disqualifications")

        for disqualification in self.pending_disqualifications:
            event = ExileEvent(player=disqualification.player, cause=DISQUALIFICATION, disqualification=disqualification)
            self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

    def _count_alive_teams(self):
        teams = set()

        for player in self.get_alive_players():
            if player.team not in teams:
                teams.add(player.team)

        return teams

    def _check_team_exile(self):
        # Detect dying teams
        for team in self.dying_teams:
            for player in self.players:
                if player.team == team and player.active:
                    event = ExileEvent(player=player, cause=TEAM_DEFEAT)
                    self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

        # Check victory condition
        teams = self._count_alive_teams()
        assert set(teams) <= set(self.playing_teams)
        winning_teams = None
        if len(teams) == 1:
            winning_teams = teams
        elif len(teams) == 0:
            winning_teams = self.playing_teams

        self.playing_teams = teams
        self.dying_teams = []

        if winning_teams is not None and self.winners is None:
            self.generate_event(VictoryEvent(winners=winning_teams, cause=NATURAL))
        elif self.recorded_winners:
            self.generate_event(VictoryEvent(winners=self.recorded_winners, cause=FORCED))

    def _perform_mayor_succession(self):
        new_mayor = not(self.mayor.alive and self.mayor.active)
        if self.appointed_mayor is not None:
            new_appointed_mayor = not(self.appointed_mayor.alive and self.appointed_mayor.active)
        else:
            new_appointed_mayor = False

        # Loss of appointed mayor
        if new_appointed_mayor:
            self.appointed_mayor = None

        # Loss of mayor
        if new_mayor:
            if self.appointed_mayor is not None and not self.mayor.disqualified:
                assert self.appointed_mayor.alive and self.appointed_mayor.active
                self.generate_event(SetMayorEvent(player=self.appointed_mayor, cause=SUCCESSION_CHOSEN))
            else:
                candidates = self.get_alive_players()
                if len(candidates)>0:
                    self.generate_event(SetMayorEvent(player=self.random.choice(candidates), cause=SUCCESSION_RANDOM))
                else:
                    self.generate_event(SetMayorEvent(player=None, cause=SUCCESSION_RANDOM))


        while self._update_step(advancing_turn=True):
            pass
        if len(self.get_alive_players())==0:
            assert self.mayor is None
        else:
            assert self.mayor.alive and self.mayor.active

    def _end_of_main_phase(self):
        self.logger.debug("Terminating main phase")

        assert self.mayor.alive and self.mayor.active
        if self.appointed_mayor is not None:
            assert self.appointed_mayor.alive and self.appointed_mayor.active

        self._check_deaths()
        self._perform_disqualifications()
        self._check_team_exile()
        self._perform_mayor_succession()

        if len(self.get_alive_players())==0:
            assert self.mayor is None
        else:
            assert self.mayor.alive and self.mayor.active
        if self.appointed_mayor is not None:
            assert self.appointed_mayor.alive and self.appointed_mayor.active

        # Reset leftover temporary status
        self.death_ghost_just_created = False
        self.upcoming_deaths = []
        self.pending_disqualifications = []
        self.post_event_triggers = []
