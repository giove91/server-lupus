# -*- coding: utf-8 -*-

import sys

from django.db.models import Q

from threading import RLock
from datetime import datetime

from models import Event, Turn
from events import CommandEvent, VoteAnnouncedEvent, TallyAnnouncedEvent, \
    ElectNewMayorEvent, PlayerDiesEvent, PowerOutcomeEvent, StakeFailedEvent, \
    ExileEvent, VictoryEvent, AvailableRoleEvent
from constants import *
from roles import *

DEBUG_DYNAMICS = False
RELAX_TIME_CHECKS = False
ANCIENT_DATETIME = datetime(year=1970, month=1, day=1, tzinfo=REF_TZINFO)

# When SINGLE_MODE is set, at most one dynamics can act concurrently
# on the same game; when SINGLE_MODE is not set automatic events won't
# be written to the database, so many dynamics can act concurrently;
# when switching from single mode to non single mode, all automatic
# events have to be deleted from the database
SINGLE_MODE = False

class Dynamics:

    def __init__(self, game):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "New dynamics spawned: %r" % (self)
        self.game = game
        self.check_mode = False  # Not supported at the moment
        self.update_lock = RLock()
        self.event_num = 0
        self._updating = False
        self.debug_event_bin = None
        self.auto_event_queue = []
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
                        print >> sys.stderr, "Deleting event %r" % (event)
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
        self.mayor = None
        self.appointed_mayor = None
        self.available_roles = []
        self.death_ghost_created = False
        self.hypnotist_ghost_created = False
        self.ghosts_created_last_night = False
        self.used_ghost_powers = set()
        self.giove_is_happy = False
        self.server_is_on_fire = False  # so far...
        self.playing_teams = []
        self.advocated_players = []
        self.amnesia_target = None
        self.duplication_target = None
        self.wolves_target = None
        self.necromancers_target = None
        self.winners = None
        self.upcoming_deaths = []
        self.mayor_dying = False
        self.appointed_mayor_dying = False
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
            player.role_class_before_ghost = None
            player.aura = None
            player.is_mystic = None
            player.alive = True
            player.active = True
            player.canonical = True
            player.recorded_vote = None
            player.recorded_elect = None
            player.apparent_mystic = None
            player.apparent_aura = None
            player.visiting = None
            player.visitors = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.just_dead = False
            player.just_ghostified = False
            player.hypnotist = None

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

    def update(self):
        with self.update_lock:
            try:
                if self._updating:
                    return
                self._updating = True
                while self._update_step():
                    pass
                self._updating = False
            except Exception:
                self.failed = True
                raise

    def _pop_event_from_db(self):
        try:
            event = Event.objects.filter(turn=self.current_turn). \
                filter(Q(timestamp__gt=self.last_timestamp_in_turn) |
                       (Q(timestamp__gte=self.last_timestamp_in_turn) & Q(pk__gt=self.last_pk_in_turn))). \
                       order_by('timestamp', 'pk')[0]
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

    def _receive_turn(self, turn):
        # Promote the new turn (we also update the old turn from the
        # database, since we expect that end might have been set since
        # last time we obtained it)
        if self.current_turn is not None:
            self.prev_turn = Turn.objects.get(pk=self.current_turn.pk)
        self.current_turn = turn

        # Debug print
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Received turn %r" % (turn)

        # Do some checks on it
        assert self.current_turn.begin is not None
        if self.prev_turn is not None:
            assert self.prev_turn.begin is not None
            assert self.prev_turn.end is not None
            assert self.prev_turn.begin <= self.prev_turn.end, (self.prev_turn.begin, self.prev_turn.end)
            assert self.prev_turn.end == turn.begin
            if not RELAX_TIME_CHECKS:
                assert self.last_timestamp_in_turn <= self.prev_turn.end

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

    def _receive_event(self, event):
        # Preliminary checks on the context
        assert self.current_turn is not None
        assert event.turn == self.current_turn

        # Debug prints
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Received event %r of subclass %s" % (event, event.subclass)
            if isinstance(event, AvailableRoleEvent):
                print >> sys.stderr, "  Available role: %s" % (event.role_name)

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
            assert event.timestamp >= self.last_timestamp_in_turn
            self.last_timestamp_in_turn = event.timestamp
        assert self.current_turn.phase in event.RELEVANT_PHASES

        # Process the event
        self._process_event(event)
        self.events.append(event)
        self.event_num += 1

    def _process_event(self, event):
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
            event.timestamp = self.current_turn.begin
        self.auto_event_queue.append(event)

    def _compute_entering_creation(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing creation"

    def _checks_after_creation(self):
        # You must generate no events here!

        # Check that all teams are represented
        self.playing_teams = self._count_alive_teams()
        assert sorted(self.playing_teams) == sorted([POPOLANI, LUPI, NEGROMANTI])

        # TODO: check that the soothsayer received revelations
        # according to the rules

    def _compute_entering_night(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing night"

        # Before first night check that creation went ok
        if self.current_turn.date == 1:
            self._checks_after_creation()

        self._check_team_exile()

    def _solve_blockers(self, critical_blockers, block_graph, rev_block_graph):
        # First some checks and build the reverse graph
        critical_pks = [x.pk for x in critical_blockers]
        for src, dsts in block_graph.iteritems():
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
                print >> sys.stderr, "  competitor: " + repr(competitor)
            score = 0
            skip = False
            for src, success in competitor.iteritems():
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
                print >> sys.stderr, "    skip: " + repr(skip)
                print >> sys.stderr, "    score: " + repr(score)

            # Finally, count the score of this competitor
            if not skip:
                if score == min_score:
                    minimizers.append(competitor)
                elif score < min_score:
                    minimizers = [competitor]
                    min_score = score

        # Choose a random minimizing competitor
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "minimizers: " + repr(minimizers)
            print >> sys.stderr, "min_score: " + repr(min_score)
        return self.random.choice(minimizers)

    def _solve_common_target(self, players, ghosts=False):
        target = None
        target_ghost = None
        for player in players:
            role = player.role
            if role.recorded_target is not None:
                if ghosts:
                    assert role.recorded_target_ghost is not None
                if target is None:
                    target = role.recorded_target
                    if ghosts:
                        target_ghost = role.recorded_target_ghost
                elif target.pk != role.recorded_target.pk:
                    return None
                elif ghosts and target_ghost != role.recorded_target_ghost:
                    return None
            else:
                if ghosts:
                    assert role.recorded_target_ghost is None

        if not ghosts:
            return target
        else:
            return target, target_ghost

    def _compute_entering_dawn(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing dawn"

        self.ghosts_created_last_night = False

        # Create an index of all roles and ghost powers
        players_by_role = {}
        ghosts_by_power = {}
        for role_class in Role.__subclasses__():
            players_by_role[role_class.__name__] = []
        for player in self.get_active_players():
            role_name = player.role.__class__.__name__
            players_by_role[role_name].append(player)

            if isinstance(player.role, Spettro):
                ghost_power = player.role.power
                assert ghost_power not in ghosts_by_power
                ghosts_by_power[ghost_power] = player

        # Shuffle players in each role
        for role_players in players_by_role.itervalues():
            self.random.shuffle(role_players)

        # Prepare temporary status
        self.wolves_target = None
        self.necromancers_target = None
        for player in self.get_active_players():
            player.apparent_aura = player.aura
            player.apparent_mystic = player.is_mystic
            player.visiting = []
            player.visitors = []

        # So, here comes the big little male house ("gran casino");
        # first of all we consider powers that can block powers that
        # can block powers: Spettro dell'Occultamento, Sequestratore,
        # Sciamano, Esorcista

        # Build the list of blockers
        critical_blockers = players_by_role[Sequestratore.__name__] + \
            players_by_role[Sciamano.__name__] + \
            players_by_role[Esorcista.__name__]
        if OCCULTAMENTO in ghosts_by_power:
            critical_blockers.append(ghosts_by_power[OCCULTAMENTO])
        critical_blockers = [x for x in critical_blockers if x.role.recorded_target is not None]

        # Build the block graph and compute blocking success
        block_graph = dict([(x.pk, x.role.get_blocked(self.players)) for x in self.players])
        rev_block_graph = dict([(x.pk, []) for x in self.players])
        for x, ys in block_graph.iteritems():
            for y in ys:
                rev_block_graph[y].append(x)
        blockers_success = self._solve_blockers(critical_blockers, block_graph, rev_block_graph)
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "block_graph:" + repr(block_graph)
            print >> sys.stderr, "rev_block_graph:" + repr(rev_block_graph)
            print >> sys.stderr, "blockers_success:" + repr(blockers_success)

        # Extend the success status to all players and compute who has
        # been sequestrated
        powers_success = dict([(x.pk, True) for x in self.players])
        powers_success.update(blockers_success)
        sequestrated = {}
        for src, success in blockers_success.iteritems():
            if success:
                for dst in block_graph[src]:
                    if dst in blockers_success:
                        assert not powers_success[dst]
                    else:
                        powers_success[dst] = False
                    if self.players_dict[src].role.__class__ == Sequestratore:
                        sequestrated[dst] = True
        if DEBUG_DYNAMICS:
            print >> sys.stderr, powers_success
            print >> sys.stderr, sequestrated

        # Then compute the visit graph
        for player in self.get_active_players():
            if player.role.recorded_target is not None and \
                    player.role.__class__ != Spettro and \
                    player.pk not in sequestrated:
                player.visiting.append(player.role.recorded_target)
                player.role.recorded_target.visitors.append(player)
        if DEBUG_DYNAMICS:
            print >> sys.stderr, dict([(x, x.visiting) for x in self.get_active_players()])
            print >> sys.stderr, dict([(x, x.visitors) for x in self.get_active_players()])

        # Utility methods for later
        def apply_role(player):
            if player.role.recorded_target is None:
                return
            success = powers_success[player.pk]
            if success:
                success = player.role.pre_apply_dawn(self)
                if DEBUG_DYNAMICS:
                    if not success:
                        print >> sys.stderr, "pre_apply_dawn() failed for %r" % (player)
            event = PowerOutcomeEvent(player=player, success=success, sequestrated=player.pk in sequestrated, command=player.role.recorded_command)
            self.generate_event(event)
            if success:
                player.role.apply_dawn(self)

        def apply_roles(roles):
            for role in roles:
                if isinstance(role, str):
                    if role in ghosts_by_power:
                        player = ghosts_by_power[role]
                        apply_role(player)
                        while self._update_step(advancing_turn=True):
                            pass
                else:
                    if role.__name__ in players_by_role:
                        for player in players_by_role[role.__name__]:
                            apply_role(player)
                            while self._update_step(advancing_turn=True):
                                pass

        # Apply roles of blockers computed above, so that
        # PowerOutcomeEvent's are properly generated
        BLOCK_ROLES = [Sequestratore, Sciamano, Esorcista,
                       OCCULTAMENTO]
        apply_roles(BLOCK_ROLES)

        # Then powers that influence modifying powers: Guardia del
        # Corpo and Custode del Cimitero
        MODIFY_INFLUENCE_ROLES = [Guardia, Custode]
        apply_roles(MODIFY_INFLUENCE_ROLES)

        # Powers that influence querying powers: Fattucchiera, Spettro
        # dell'Illusione and Spettro della Mistificazione
        QUERY_INFLUENCE_ROLES = [Fattucchiera, ILLUSIONE, MISTIFICAZIONE]
        apply_roles(QUERY_INFLUENCE_ROLES)

        # Powers that query the state: Espansivo, Investigatore, Mago,
        # Stalker, Veggente, Voyeur, Diavolo, Medium and Spettro della
        # Visione
        QUERY_ROLES = [Espansivo, Investigatore, Mago, Stalker, Veggente,
                       Voyeur, Diavolo, Medium, VISIONE]
        apply_roles(QUERY_ROLES)

        # Identify targets for Lupi and Negromanti
        self.wolves_target = self._solve_common_target(players_by_role[Lupo.__name__], ghosts=False)
        self.necromancers_target = self._solve_common_target(players_by_role[Negromante.__name__], ghosts=True)

        assert self.upcoming_deaths == []

        # Powers that modify the state: Cacciatore, Messia,
        # Trasformista, Lupi, Avvocato del Diavolo, Negromante,
        # Ipnotista, Spettro dell'Amnesia and Spettro della Morte (the
        # order is important here!)
        MODIFY_ROLES = [Avvocato, AMNESIA, Ipnotista, Trasformista,
                        Messia, Negromante, Cacciatore, Lupo, MORTE]
        apply_roles(MODIFY_ROLES)

        # Roles with no power: Contadino, Divinatore, Massone,
        # Rinnegato, Fantasma; we apply them anyway, so that we are
        # sure that all players pass through apply_role()
        STUPID_ROLES = [Contadino, Divinatore, Massone, Rinnegato,
                        Fantasma]
        apply_roles(STUPID_ROLES)

        # Unset all temporary status
        self.wolves_target = None
        self.necromancers_target = None
        for player in self.players:
            player.role.unrecord_targets()
            player.apparent_aura = None
            player.apparent_mystic = None
            player.visiting = None
            player.visitors = None
            player.protected_by_guard = False
            player.protected_by_keeper = False
            player.just_ghostified = False

        self._check_deaths()
        self._check_team_exile()

    def _compute_entering_day(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing day"

    def _compute_entering_sunset(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing sunset"

        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            event = ElectNewMayorEvent(player=new_mayor)
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

        # Unrecord all data setting during previous dawn
        self.advocated_players = []
        self.amnesia_target = None
        self.duplication_target = None

        # Unrecord all elect and vote events
        for player in self.players:
            player.recorded_vote = None
            player.recorded_elect = None

        self._check_deaths()
        self._check_team_exile()

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
        for ballot in ballots.itervalues():
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
        tally_sheet = tally_sheet.items()
        tally_sheet.sort(key=lambda x: x[1], reverse=True)
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
        duplication_ballot = None
        for player in self.get_alive_players():

            # Count Ipnotista
            real_vote = player.recorded_vote
            if player.hypnotist is not None and player.hypnotist.alive:
                assert isinstance(player.hypnotist.role, Ipnotista)
                real_vote = player.hypnotist.recorded_vote

            # Count Spettro dell'Amnesia
            if self.amnesia_target is not None and self.amnesia_target.pk == player.pk:
                real_vote = None

            ballots[player.pk] = real_vote
            if player.is_mayor():
                mayor_ballot = real_vote
            if self.duplication_target is not None and self.duplication_target.pk == player.pk:
                duplication_ballot = real_vote

        # Fill the tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        votes_num = 0
        for ballot in ballots.itervalues():
            if ballot is None:
                continue
            tally_sheet[ballot.pk] += 1
            votes_num += 1

        # Check that at least half of the alive people voted
        if votes_num * 2 < len(self.get_alive_players()):
            quorum_failed = True

        # Send vote announcements
        for player in self.get_alive_players():
            if ballots[player.pk] is not None:
                event = VoteAnnouncedEvent(voter=player, voted=ballots[player.pk], type=VOTE)
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
        tally_sheet = tally_sheet.items()
        tally_sheet.sort(key=lambda x: x[1], reverse=True)
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
        # We randomize deaths in order to mix Fantasma powers
        self.random.shuffle(self.upcoming_deaths)

        for event in self.upcoming_deaths:
            event.apply_death(self)

    def _count_alive_teams(self):
        teams = []

        # Popolani
        for player in self.get_alive_players():
            if player.team == POPOLANI:
                teams.append(POPOLANI)
                break

        # Lupi
        for player in self.get_alive_players():
            if isinstance(player.role, Lupo):
                teams.append(LUPI)
                break

        # Negromanti
        for player in self.get_alive_players():
            if isinstance(player.role, Negromante):
                teams.append(NEGROMANTI)
                break

        return teams

    def _check_team_exile(self):
        # Detect dying teams
        teams = self._count_alive_teams()
        assert set(teams) <= set(self.playing_teams)
        dying_teams = set(self.playing_teams) - set(teams)
        for team in dying_teams:
            if team in [LUPI, NEGROMANTI]:
                for player in self.players:
                    if player.team == team and player.active:
                        if player.is_mayor():
                            self.mayor_dying = True
                        elif player.is_appointed_mayor():
                            self.appointed_mayor_dying = True
                        event = ExileEvent(player=player, cause=TEAM_DEFEAT)
                        self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

        # Loss of appointed mayor
        if self.appointed_mayor_dying:
            self.appointed_mayor = None

        # Loss of mayor
        if self.mayor_dying:
            if self.appointed_mayor is not None:
                assert self.appointed_mayor.alive and self.appointed_mayor.active
                self.mayor = self.appointed_mayor
                self.appointed_mayor = None

            else:
                candidates = self.get_alive_players()
                self.mayor = self.random.choice(candidates)

                # TODO: pass through an appropriate event?

        else:
            assert self.mayor.alive and self.mayor.active

        while self._update_step(advancing_turn=True):
            pass

        self.mayor_dying = False
        self.appointed_mayor_dying = False
        self.upcoming_deaths = []

        # Check victory condition
        winning_teams = None
        if len(teams) == 1:
            winning_teams = teams
        elif len(teams) == 0:
            winning_teams = self.playing_teams

        self.playing_teams = teams

        if winning_teams is not None and self.winners is None:
            self.generate_event(VictoryEvent(popolani_win=POPOLANI in winning_teams,
                                             lupi_win=LUPI in winning_teams,
                                             negromanti_win=NEGROMANTI in winning_teams,
                                             cause=NATURAL))
