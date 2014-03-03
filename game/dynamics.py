# -*- coding: utf-8 -*-

import sys

from django.db.models import Q

from threading import RLock
from datetime import datetime

from models import Event, Turn
from events import CommandEvent, VoteAnnouncedEvent, TallyAnnouncedEvent, \
    ElectNewMayorEvent, PlayerDiesEvent
from constants import *
from roles import *

DEBUG_DYNAMICS = False
RELAX_TIME_CHECKS = False
ANCIENT_DATETIME = datetime(year=1970, month=1, day=1, tzinfo=REF_TZINFO)

class Dynamics:

    def __init__(self, game):
        self.game = game
        self.check_mode = False  # Not supported at the moment
        self.update_lock = RLock()
        self.event_num = 0
        self._updating = False
        self.debug_event_bin = None
        self.auto_event_queue = []
        self.initialize_augmented_structure()

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
        self.ghosts_created_last_night = False
        self.used_ghost_powers = set()
        self.giove_is_happy = False
        self.server_is_on_fire = False  # so far...
        self.playing_teams = []
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
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
        return [player for player in self.players if player.alive]

    def get_dead_players(self):
        """Players are guaranteed to be sorted in a canonical order,
        which does not change neither by restarting the server (but it
        can change if players' data is changed)."""
        return [player for player in self.players if not player.alive]

    def get_canonical_player(self, player):
        return self.players_dict[player.pk]

    def update(self):
        with self.update_lock:
            if self._updating:
                return
            self._updating = True
            while self._update_step():
                pass
            self._updating = False

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
            # TODO: the following code has race conditions when
            # executed in autocommit mode; fix it! (also, check the
            # fix with the real database we're going to use)
            queued_event = self._pop_event_from_queue()
            # If there is not queued event and we're advancing turn,
            # do not process any other event
            if advancing_turn and queued_event is None:
                return False
            event = self._pop_event_from_db()
            if event is not None and queued_event is not None:
                # TODO: implement the following
                #assert event == queued_event
                pass
            if queued_event is not None:
                if self.debug_event_bin is not None:
                    self.debug_event_bin.append(queued_event)
            if event is not None:
                self._receive_event(event)
                return True
            elif queued_event is not None:
                queued_event.save()
                self._receive_event(queued_event)
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
            assert self.prev_turn.begin <= self.prev_turn.end
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

        # Do some check on the new event
        if not RELAX_TIME_CHECKS:
            assert event.timestamp >= self.current_turn.begin
        assert (event.timestamp > self.last_timestamp_in_turn) or \
            (event.timestamp >= self.last_timestamp_in_turn and event.pk >= self.last_pk_in_turn), \
            repr((event.timestamp, self.last_timestamp_in_turn, event.pk, self.last_pk_in_turn))
        self.last_timestamp_in_turn = event.timestamp
        self.last_pk_in_turn = event.pk
        assert self.current_turn.phase in event.RELEVANT_PHASES

        # Process the event
        self._process_event(event)
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
        # XXX: probably we want to check the originating event
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

    def _solve_blockers(self, critical_blockers, block_graph):
        # First some checks and build the reverse graph
        rev_block_graph = dict([(x.pk, []) for x in critical_blockers])
        critical_pks = [x.pk for x in critical_blockers]
        for src, dsts in block_graph.iteritems():
            for dst in dsts:
                assert self.players_dict[dst] in critical_blocker
                assert dst != src
                rev_block_graph[dst].append(src)

        def iter_competitors():
            current = dict([(x.pk, True) for x in critical_blockers])
            while True:
                yield current
                for i in critical_pks:
                    current[i] = not current[i]
                    if not current[i]:
                        break
                else:
                    return

        # Start generating competitors
        min_score = len(critical_blockers) + 1
        minimizers = []
        for competitor in iter_competitors():
            score = 0
            skip = False
            for src, success in competitor:
                # If this player succeeds, we have to check that its
                # blocks are successful
                if success:
                    for dst in block_graph[src]:
                        if competitor[dst]:
                            skip = True
                            break
                    if skip:
                        break

                # If it fails, we have to count whether this is
                # justified or not
                else:
                    for dst in rev_block_graph[src]:
                        if competitor[dst]:
                            break
                    else:
                        score += 1

            # Finally, count the score of this competitor
            if not skip:
                if score == min_score:
                    minimizers.append(competitor)
                elif score < min_score:
                    minimizers = [competitor]
                    min_score = score

        # Choose a random minimizing competitor
        return rev_block_graph, self.random.choice(minimizers)

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
            pass

        # Prepare temporary status
        for player in self.get_active_players():
            player.apparent_aura = player.aura
            player.apparent_mystic = player.is_mystic
            player.visiting = None
            player.visitors = []

        def apply_roles(roles):
            for role in roles:
                if isinstance(role, str):
                    if role in ghosts_by_power:
                        player = ghosts_by_power[role]
                        player.role.apply_dawn(dynamics)
                else:
                    if role.__name__ in players_by_role:
                        for player in players_by_role[role.__name__]:
                            player.role.apply_dawn(self)

        # So, here comes the big little male house ("gran casino");
        # first of all we consider powers that can block powers that
        # can block powers: Spettro dell'Occultamento, Sequestratore,
        # Profanatore di Tombe, Esorcista
        critical_blockers = players_by_role[Sequestratore.__name__] + \
            players_by_role[Profanatore.__name__] + \
            players_by_role[Esorcista.__name__]
        ghost = None
        if OCCULTAMENTO in ghosts_by_power:
            ghost = ghosts_by_power[OCCULTAMENTO]
            critical_blockers.append(ghost)
        block_graph = dict([(x.pk, [x.role.get_blocked(critical_blockers, ghost)]) for x in critical_blockers])
        rev_block_graph, blockers_success = self._solve_blockers(critical_blockers, block_graph)

        # Then powers that can block other powers: Guardia del Corpo
        # and Custode del Cimitero (TODO)

        # Powers that influence the querying powers: Fattucchiera,
        # Spettro dell'Illusione and Spettro della Mistificazione
        # (TODO)
        QUERY_INFLUENCE_ROLES = [Fattucchiera, ILLUSIONE, MISTIFICAZIONE]
        apply_roles(QUERY_INFLUENCE_ROLES)

        # Powers that query the state: Espansivo, Investigatore, Mago,
        # Stalker, Veggente, Voyeur, Diavolo, Medium and Spettro della
        # Visione (TODO)
        QUERY_ROLES = [Espansivo, Investigatore, Mago, Stalker, Veggente,
                       Voyeur, Diavolo, Medium, VISIONE]
        apply_roles(QUERY_ROLES)

        # Powers that modify the state: Cacciatore, Messia, Necrofilo,
        # Lupi, Avvocato del Diavolo, Negromante, Ipnotista, Spettro
        # dell'Amnesia, Spettro della Duplicazione and Spettro della
        # Morte (TODO)

        # Roles with no power: Contadino, Divinatore, Massone,
        # Rinnegato, Fantasma and Spettro without power

        # Unset all temporary status
        for player in self.players:
            player.role.unrecord_targets()
            player.apparent_aura = None
            player.apparent_mystic = None
            player.visiting = None
            player.visitors = None

    def _compute_entering_day(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing day"

        self._check_team_exile()

    def _compute_entering_sunset(self):
        if DEBUG_DYNAMICS:
            print >> sys.stderr, "Computing sunset"

        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            event = ElectNewMayorEvent(player=new_mayor)
            self.generate_event(event)

        while self._update_step(advancing_turn=True):
            pass

        winner = self._compute_vote_winner()
        if winner is not None:
            event = PlayerDiesEvent(player=winner, cause=STAKE)
            self.generate_event(event)

        # Unrecord all elect and vote events
        for player in self.players:
            player.recorded_vote = None
            player.recorded_elect = None

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
        for player in self.players:
            ballots[player.pk] = player.recorded_vote
            if player.is_mayor():
                mayor_ballot = player.recorded_vote

        # TODO: count Ipnotista and Spettro dell'Amnesia

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

        # Check that at least halg of the alive people voted
        if votes_num * 2 < len(self.get_alive_players()):
            quorum_failed = True

        # TODO: count Spettro della Duplicazione

        # Send announcements
        for player in self.get_alive_players():
            if ballots[player.pk] is not None:
                event = VoteAnnouncedEvent(voter=player, voted=ballots[player.pk], type=VOTE)
                self.generate_event(event)
        for player in self.get_alive_players():
            if tally_sheet[player.pk] != 0:
                event = TallyAnnouncedEvent(voted=player, vote_num=tally_sheet[player.pk], type=VOTE)
                self.generate_event(event)

        # Abort the vote if the quorum wasn't reached
        if quorum_failed:
            return None

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

        return self.players_dict[winner]

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
                    if player.team == team:
                        player.active = False

        # Check victory condition
        winning_teams = None
        if len(teams) == 1:
            winning_teams = teams
        elif len(teams) == 0:
            winning_teams = self.playing_teams

        self.playing_teams = teams

        if winning_teams is not None:
            self._compute_victory(winning_teams)

    def _compute_victory(self, winning_teams):
        # TODO
        pass
