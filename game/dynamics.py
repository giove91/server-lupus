# -*- coding: utf-8 -*-

import sys

from django.db.models import Q

from threading import RLock
from datetime import datetime
import time

from .models import Event, Turn
from .events import CommandEvent, VoteAnnouncedEvent, TallyAnnouncedEvent, \
    SetMayorEvent, PlayerDiesEvent, PowerOutcomeEvent, StakeFailedEvent, \
    ExileEvent, VictoryEvent, AvailableRoleEvent, RoleKnowledgeEvent
from .constants import *
from .roles import *
from .utils import get_now
DEBUG_DYNAMICS = False
SIMULATE_NEXT_TURN = True
FORCE_SIMULATION = False # Enable only while running tests
RELAX_TIME_CHECKS = False
ANCIENT_DATETIME = datetime(year=1970, month=1, day=1, tzinfo=REF_TZINFO)

# When SINGLE_MODE is set, at most one dynamics can act concurrently
# on the same game; when SINGLE_MODE is not set automatic events won't
# be written to the database, so many dynamics can act concurrently;
# when switching from single mode to non single mode, all automatic
# events have to be deleted from the database
SINGLE_MODE = False

def set_debug_dynamics(value):
    global DEBUG_DYNAMICS
    DEBUG_DYNAMICS = value

class Dynamics:

    def __init__(self, game):
        if DEBUG_DYNAMICS:
            print("New dynamics spawned: %r" % (self), file=sys.stderr)
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
        self.simulated_events = []
        self.events = []
        self.turns = []
        self.failed = False

        self.initialize_augmented_structure()

        # If in single mode, delete all automatic events
        if SINGLE_MODE:
            for event in Event.objects.all():
                event = event.as_child()
                if event.AUTOMATIC:
                    if DEBUG_DYNAMICS:
                        print("Deleting event %r" % (event), file=sys.stderr)
                    event.delete()

        # Otherwise expect that there are no automatic events in the
        # database
        else:
            for event in Event.objects.all():
                event = event.as_child()
                assert not event.AUTOMATIC, "Please delete automatic events from database using delete_automatic_events.py"

    def initialize_augmented_structure(self):
        self.players = list(self.game.player_set.order_by('user__last_name', 'user__first_name', 'user__username'))
        self.players_dict = {}
        self.random = None
        self.current_turn = None
        self.prev_turn = None
        self.last_timestamp_in_turn = None
        self.last_pk_in_turn = None
        self.creation_subphase = SIGNING_UP
        self.mayor = None
        self.appointed_mayor = None
        self.pre_simulation_mayor = None
        self.pre_simulation_appointed_mayor = None
        self.available_roles = []
        self.death_ghost_created = False
        self.death_ghost_just_created = False
        self.ghosts_created_last_night = False
        self.used_ghost_powers = set()
        self.giove_is_happy = False
        self.server_is_on_fire = False  # so far...
        self.sasha_is_sleeping = False  # usually...
        self.playing_teams = []
        self.dying_teams = []
        self.advocated_players = []
        self.redirected_ballots = []
        self.amnesia_target = None
        self.hypnosis_ghost_target = None
        self.illusion = None
        self.wolves_agree = None
        self.necromancers_agree = None
        self.winners = None
        self.over = False
        self.upcoming_deaths = []
        self.pending_disqualifications = []
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
            player.role_class_before_ghost = None
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
            player.visiting = None
            player.visitors = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.sequestrated = False
            player.just_dead = False
            player.just_ghostified = False
            player.just_transformed = False
            player.just_resurrected = False
            player.hypnotist = None
            player.has_confusion = False

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
        # If role is Spettro, return only Spettro
        if player.apparent_role.ghost:
            return player.apparent_role.__base__
        else:
            return player.apparent_role
    
    def get_apparent_team(self, player):
        return player.apparent_team
    
    def update(self, simulation=False):
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
        if DEBUG_DYNAMICS and self.spawned_at:
            print('First updating finished. Elapsed time: {0!r}'.format(time.time() - self.spawned_at))    
            self.spawned_at = None   
        

    def _pop_event_from_db(self):
        if DEBUG_DYNAMICS:
            print("current_turn: {0!r}; last_timestamp_in_turn: %r; last_pk_in_turn: {1!r}".format(self.current_turn, self.last_timestamp_in_turn, self.last_pk_in_turn), file=sys.stderr)
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
                if DEBUG_DYNAMICS:
                    print("Receiving event from queue", file=sys.stderr)
                if self.debug_event_bin is not None:
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
                    if DEBUG_DYNAMICS:
                        print("Receiving event from database", file=sys.stderr)
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
            pass
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
        if DEBUG_DYNAMICS:
            print("Received turn %r" % (turn), file=sys.stderr)

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
        if DEBUG_DYNAMICS:
            print("Received event %r of subclass %s, timed %s" % (event, event.subclass, event.timestamp), file=sys.stderr)
            if isinstance(event, AvailableRoleEvent):
                print("  Available role: %s" % (event.role_name), file=sys.stderr)

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
        
    def _simulate_event(self, event):
        if event.CAN_BE_SIMULATED:
            event.apply(self)

    def inject_event(self, event):
        """This is for non automatic events."""
        assert not event.AUTOMATIC
        assert self.current_turn.phase in event.RELEVANT_PHASES
        event.turn = self.current_turn
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

    def _compute_entering_creation(self):
        if DEBUG_DYNAMICS:
            print("Computing creation", file=sys.stderr)

    def _checks_after_creation(self):
        # You shall generate no events here!

        # Check that all teams are represented
        self.playing_teams = self._count_alive_teams()
        assert sorted(self.playing_teams) == sorted(self.starting_teams)
        for player in self.players:
            if player.role.__class__ in self.required_roles:
                self.required_roles.remove(player.role.__class__)
        assert len(self.required_roles) == 0

    def check_soothsayers(self):
        # Check that the soothsayer received revelations according to
        # the rules
        result = True
        for soothsayer in [pl for pl in self.players if pl.role.__class__.__name__ == 'Divinatore']:
            events = [ev for ev in self.events if isinstance(ev, RoleKnowledgeEvent) and ev.player.pk == soothsayer.pk]
            if len(events) != 4 or sorted([ev.target.canonicalize().role.full_name == ev.role_name for ev in events]) != sorted([False, False, True, 
True]):
                result = False
        assert self.creation_subphase == SOOTHSAYING or result
        if self.creation_subphase == SOOTHSAYING and result:
            self.creation_subphase = PUBLISHING_INFORMATION

    def _compute_entering_night(self):
        if DEBUG_DYNAMICS:
            print("Computing night", file=sys.stderr)

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
            if DEBUG_DYNAMICS:
                print("  competitor: " + repr(competitor), file=sys.stderr)
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

            if DEBUG_DYNAMICS:
                print("    skip: " + repr(skip), file=sys.stderr)
                print("    score: " + repr(score), file=sys.stderr)

            # Finally, count the score of this competitor
            if not skip:
                if score == min_score:
                    minimizers.append(competitor)
                elif score < min_score:
                    minimizers = [competitor]
                    min_score = score

        # Choose a random minimizing competitor
        if DEBUG_DYNAMICS:
            print("minimizers: " + repr(minimizers), file=sys.stderr)
            print("min_score: " + repr(min_score), file=sys.stderr)
        return self.random.choice(minimizers)

    def check_common_target(self, players, ghosts=False):
        target = None
        target_ghost = None
        for player in players:
            role = player.role
            if role.recorded_target is not None:
                if ghosts:
                    assert role.recorded_target_ghost is not None
                # Ignore sequestrated lupi
                if role.player.sequestrated:
                    continue
                if target is None:
                    target = role.recorded_target
                    if ghosts:
                        target_ghost = role.recorded_target_ghost
                elif target.pk != role.recorded_target.pk:
                    return False
                elif ghosts and target_ghost != role.recorded_target_ghost:
                    return False
            else:
                if ghosts:
                    assert role.recorded_target_ghost is None

        return True

    def _compute_entering_dawn(self):
        if DEBUG_DYNAMICS:
            print("Computing dawn", file=sys.stderr)

        self.ghosts_created_last_night = False

        # Prepare temporary status
        self.wolves_agree = None
        self.necromancers_agree = None
        for player in self.get_active_players():
            player.apparent_aura = player.aura
            player.apparent_mystic = player.is_mystic
            player.apparent_role = player.role.__class__
            player.apparent_team = player.team
            player.visiting = []
            player.visitors = []

        # So, here comes the big little male house ("gran casino");
        # first of all we consider powers that can block powers that
        # can block powers: Spettro dell'Occultamento, Sequestratore,
        # Sciamano, Esorcista, Stregone

        # Build the list of blockers
        critical_blockers = [player for player in self.get_active_players() if player.role.critical_blocker and player.role.recorded_target is not None]

        # Build the block graph and compute blocking success
        block_graph = dict([(x.pk, x.role.get_blocked(self.players)) for x in self.players])
        rev_block_graph = dict([(x.pk, []) for x in self.players])
        for x, ys in iter(block_graph.items()):
            for y in ys:
                rev_block_graph[y].append(x)
        blockers_success = self._solve_blockers(critical_blockers, block_graph, rev_block_graph)
        if DEBUG_DYNAMICS:
            print("block_graph:" + repr(block_graph), file=sys.stderr)
            print("rev_block_graph:" + repr(rev_block_graph), file=sys.stderr)
            print("blockers_success:" + repr(blockers_success), file=sys.stderr)

        # Extend the success status to all players and compute who has
        # been sequestrated
        powers_success = dict([(x.pk, True) for x in self.players])
        powers_success.update(blockers_success)
        sequestrated = {}
        for src, success in iter(blockers_success.items()):
            if success:
                for dst in block_graph[src]:
                    if dst in blockers_success:
                        assert not powers_success[dst]
                    else:
                        powers_success[dst] = False
                    if self.players_dict[src].role.sequester:
                        sequestrated[dst] = True
        if DEBUG_DYNAMICS:
            print("powers_success: " + repr(powers_success), file=sys.stderr)
            print("sequestrated: " + repr(sequestrated), file=sys.stderr)

        # Then compute the visit graph
        for player in self.get_active_players():
            if player.role.recorded_target is not None and \
                    not player.role.ghost and \
                    player.pk not in sequestrated:
                player.visiting.append(player.role.recorded_target)
                player.role.recorded_target.visitors.append(player)
        if DEBUG_DYNAMICS:
            print("visiting: " + repr(dict([(x, x.visiting) for x in self.get_active_players()])), file=sys.stderr)
            print("visitors: " + repr(dict([(x, x.visitors) for x in self.get_active_players()])), file=sys.stderr)

        # Utility methods for later
        def apply_role(player):
            if player.role.recorded_target is None:
                return
            if DEBUG_DYNAMICS:
                print("> Applying role %r for %r:" % (player, player.role), file=sys.stderr)
            success = powers_success[player.pk]
            if DEBUG_DYNAMICS:
                print(success, file=sys.stderr)
            if success:
                success = player.role.pre_apply_dawn(self)
                if DEBUG_DYNAMICS:
                    print(success, file=sys.stderr)
            else:
                if DEBUG_DYNAMICS:
                    print(success, file=sys.stderr)
            event = PowerOutcomeEvent(player=player, success=success, sequestrated=player.pk in sequestrated, command=player.role.recorded_command)
            self.generate_event(event)
            if success:
                player.role.apply_dawn(self)

        players = self.get_active_players()
        self.random.shuffle(players)
        players.sort(key=lambda x:x.role.priority)
        for player in players:
            assert player.role.priority is not None
            apply_role(player)
            while self._update_step(advancing_turn=True):
                pass

        # Unset (nearly) all temporary status
        self.wolves_agree = None
        self.necromancers_agree = None
        self.illusion = None
        for player in self.players:
            if not self.simulating:
                player.role.unrecord_targets()
            player.apparent_aura = None
            player.apparent_mystic = None
            player.apparent_role = None
            player.apparent_team = None
            player.visiting = None
            player.visitors = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.sequestrated = False
            player.just_ghostified = False
            player.just_transformed = False
            player.just_resurrected = False
            player.has_confusion = False
        
        if self.simulating:
            # Remove useless state for following day
            self.advocated_players = []
            self.hypnosis_ghost_target = None
            self.redirected_ballots = []
            self.amnesia_target = None
        else:
            
            self._end_of_main_phase()

    def _compute_entering_day(self):
        if DEBUG_DYNAMICS:
            print("Computing day", file=sys.stderr)

    def _compute_entering_sunset(self):
        if DEBUG_DYNAMICS:
            print("Computing sunset", file=sys.stderr)

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
            self.advocated_players = []
            self.hypnosis_ghost_target = None
            self.redirected_ballots = []
            self.amnesia_target = None

            # Unrecord all elect and vote events
            for player in self.players:
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
        winner = None
        quorum_failed = False

        # Count last ballot for each player
        ballots = {}
        mayor_ballot = None
        for player in self.get_alive_players():
            ballots[player.pk] = player.recorded_vote

        # Apply Spettro dell'Ipnosi
        if self.hypnosis_ghost_target is not None and self.hypnosis_ghost_target[0].alive and self.hypnosis_ghost_target[1].alive:
            ballots[self.hypnosis_ghost_target[0].pk] = self.hypnosis_ghost_target[1]

        # Apply Spettro dell'Amnesia
        if self.amnesia_target is not None and self.amnesia_target.alive:
            ballots[self.amnesia_target.pk] = None

        # Apply Ipnotista
        def hypnotist_redirect(hypnotist):
            if hypnotist.role.__class__.__name__ == 'Ipnotista': # TODO: sistemare per bene, magari mettendola sotto roles
                for player in self.get_alive_players():
                    if player.hypnotist is hypnotist and ballots[player.pk] is not ballots[hypnotist.pk] and \
                    (self.hypnosis_ghost_target is None or player is not self.hypnosis_ghost_target[0]) and \
                    player is not self.amnesia_target:
                        ballots[player.pk] = ballots[hypnotist.pk]
                        hypnotist_redirect(player)

        for player in self.get_alive_players():
            hypnotist_redirect(player)

        # Apply Scrutatore
        for (target, scrutatore) in self.redirected_ballots:
            if not scrutatore.alive:
                continue
            assert target is not None
            assert scrutatore.role.__class__.__name__ == 'Scrutatore'
            for player in self.get_alive_players():
                if ballots[player.pk] is target:
                    ballots[player.pk] = ballots[scrutatore.pk]

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

        # Check that at least half of the alive people voted
        if votes_num * 2 < len(self.get_alive_players()):
            quorum_failed = True

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

        # Abort the vote if the quorum wasn't reached
        if quorum_failed:
            return None, MISSING_QUORUM

        # Compute winners (or maybe loosers...)
        tally_sheet = sorted(tally_sheet.items(),key=lambda x: x[1], reverse=True)
        max_votes = tally_sheet[0][1]
        winners = [x[0] for x in tally_sheet if x[1] == max_votes]
        assert len(winners) > 0
        if mayor_ballot is not None and mayor_ballot.pk in winners:
            winner = mayor_ballot.pk
        else:
            winner = self.random.choice(winners)
        winner_player = self.players_dict[winner]

        # Check for protection by Avvocato del Diavolo
        cause = None
        if winner_player in self.advocated_players:
            winner_player = None
            cause = ADVOCATE

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

        if DEBUG_DYNAMICS:
            print("Computing disqualifications", file=sys.stderr)

        for disqualification in self.pending_disqualifications:
            event = ExileEvent(player=disqualification.player, cause=DISQUALIFICATION, disqualification=disqualification)
            self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

    def _count_alive_teams(self):
        teams = []

        for player in self.get_alive_players():
            if player.team not in teams:
                teams.append(player.team)

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
            self.generate_event(VictoryEvent(popolani_win=POPOLANI in winning_teams,
                                             lupi_win=LUPI in winning_teams,
                                             negromanti_win=NEGROMANTI in winning_teams,
                                             cause=NATURAL))

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
        if DEBUG_DYNAMICS:
            print("Terminating main phase", file=sys.stderr)

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
