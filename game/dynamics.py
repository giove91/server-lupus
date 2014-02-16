# -*- coding: utf-8 -*-

from django.db.models import Q

from threading import RLock
from datetime import datetime

from models import Event, Turn
from events import CommandEvent, VoteAnnouncedEvent, TallyAnnouncedEvent, \
    ElectNewMayorEvent, PlayerDiesEvent
from constants import *
import roles

RELAX_TIME_CHECKS = False
ANCIENT_DATETIME = datetime(year=1970, month=1, day=1, tzinfo=REF_TZINFO)

class Dynamics:

    def __init__(self, game):
        self.game = game
        self.check_mode = False
        self.update_lock = RLock()
        self.event_num = 0
        self._updating = False
        self.initialize_augmented_structure()

    def initialize_augmented_structure(self):
        self.players = list(self.game.player_set.order_by('user__last_name', 'user__first_name'))
        self.players_dict = {}
        self.random = None
        self.current_turn = None
        self.prev_turn = None
        self.last_timestamp_in_turn = None
        self.last_pk_in_turn = None
        self.mayor = None
        self.available_roles = []
        self.death_ghost_created = False
        self.ghosts_created_last_night = False
        self.used_ghost_powers = set()
        self.giove_is_happy = False
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
            player.aura = None
            player.is_mystic = None
            player.alive = True
            player.active = True

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
            self.event_num += 1
            return event.as_child()

    def _update_step(self):
        # First check for new events in current turn
        if self.current_turn is not None:
            event = self._pop_event_from_db()
            if event is not None:
                self._receive_event(event)
                return True

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

        # Do some check on the new event
        if not RELAX_TIME_CHECKS:
            assert event.timestamp >= self.current_turn.begin
        assert (event.timestamp > self.last_timestamp_in_turn) or \
            (event.timestamp >= self.last_timestamp_in_turn and event.pk >= self.last_pk_in_turn)
        self.last_timestamp_in_turn = event.timestamp
        self.last_pk_in_turn = event.pk
        assert self.current_turn.phase in event.RELEVANT_PHASES

        # Process the event
        self._process_event(event)

    def _process_event(self, event):
        self.check_mode = event.executed
        event.apply(self)
        self.check_mode = False
        event.executed = True
        event.save()

    def inject_event(self, event):
        """This is for non automatic events."""
        assert not event.AUTOMATIC
        assert self.current_turn.phase in event.RELEVANT_PHASES
        event.turn = self.current_turn
        event.save()
        self.update()

    def generate_event(self, event):
        """This is for automatic events."""
        assert event.AUTOMATIC
        assert self.current_turn.phase in event.RELEVANT_PHASES
        event.turn = self.current_turn
        event.timestamp = self.current_turn.begin

        if self.check_mode:
            # I expect the new event to just already sit in the
            # database. TODO: verify this assertion
            pass
        else:
            event.save()

        # We may be interested in doing an update here, but I'm not
        # sure it has no counterindications
        #self.update()

    def _compute_entering_creation(self):
        pass

    def _compute_entering_night(self):
        pass

    def _compute_entering_dawn(self):
        self.ghosts_created_last_night = False

    def _compute_entering_day(self):
        pass

    def _compute_entering_sunset(self):
        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            # TODO
            pass

        winner = self._compute_vote_winner()
        if winner is not None:
            event = PlayerDiesEvent(player=winner, cause=STAKE)
            self.generate_event(event)

    def _compute_elected_mayor(self):
        votes = CommandEvent.objects.filter(turn=self.prev_turn).filter(type=ELECT).order_by('timestamp')
        new_mayor = None

        # TODO

        return new_mayor

    def _compute_vote_winner(self):
        votes = CommandEvent.objects.filter(turn=self.prev_turn).filter(type=VOTE).order_by('timestamp')
        winner = None
        quorum_failed = False

        # Count last ballot for each player
        ballots = {}
        mayor_ballot = None
        for player in self.players:
            ballots[player.pk] = None
        for vote in votes:
            ballots[vote.player.pk] = vote
            if vote.player.is_mayor():
                mayor_ballot = vote

        # TODO: count Ipnotista and Spettro dell'Amnesia

        # Fill the tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        votes_num = 0
        for ballot in ballots.itervalues():
            if ballot is None:
                continue
            tally_sheet[ballot.target.pk] += 1
            votes_num += 1

        # Check that at least halg of the alive people voted
        if votes_num * 2 < len(self.get_alive_players()):
            quorum_failed = True

        # TODO: count Spettro della Duplicazione

        # Send announcements
        for player in self.get_alive_players():
            if ballots[player.pk] is not None:
                event = VoteAnnouncedEvent(voter=player.canonicalize(), voted=ballots[player.pk].target.canonicalize(), type=VOTE)
                self.generate_event(event)
        for player in self.get_alive_players():
            if tally_sheet[player.pk] != 0:
                event = TallyAnnouncedEvent(voted=player.canonicalize(), note_num=vote_num)
                self.generate_event(event)

        # Abort the vote if the quorum wasn't reached
        if quorum_failed:
            return None

        # Compute winners (or maybe loosers...)
        tally_sheet = tally_sheet.items()
        tally_sheet.sort(key=lambda x: x[1])
        max_votes = tally_sheet[0][1]
        winners = [x[0] for x in tally_sheet if x[1] == max_votes]
        assert len(winners) > 0
        if mayor_ballot.target.pk in winners:
            winner = mayor_ballot.target.pk
        else:
            winner = random.choice(winners)

        return winner
