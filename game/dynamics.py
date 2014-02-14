# -*- coding: utf-8 -*-

from django.db.models import Q

from threading import RLock

from models import Event, Turn
import roles

class Dynamics:

    def __init__(self, game):
        self.game = game
        self.check_mode = False
        self.update_lock = RLock()
        self.event_num = 0
        self.initialize_augmented_structure()

    def initialize_augmented_structure(self):
        self.players = list(self.game.player_set.all())
        self.players_dict = {}
        self.random = None
        self.current_turn = None
        self.prev_turn = None
        self.last_timestamp_in_turn = None
        self.last_pk_in_turn = None
        self.mayor = None
        self.available_roles = []
        for player in self.players:
            self.players_dict[player.pk] = player
            player.team = None
            player.role = None
            player.aura = None
            player.is_mystic = None
            player.alive = True
            player.active = True

    def get_canonical_player(self, player):
        return self.players_dict[player.pk]

    def update(self):
        with self.update_lock:
            while self._update_step():
                pass

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
        # Promote the new turn
        self.prev_turn = self.current_turn
        self.current_turn = turn

        # Do some checks on it
        assert self.current_turn.begin is not None
        if self.prev_turn is not None:
            assert self.prev_turn.begin is not None
            assert self.prev_turn.end is not None
            assert self.prev_turn.begin <= self.prev_turn.end
            assert self.prev_turn.end == turn.begin
            assert self.last_timestamp_in_turn <= self.prev_turn.end

        # Prepare data for checking events
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
        assert event.timestamp >= self.current_turn.begin
        assert (event.timestamp > self.last_timestamp_in_turn) or (event.timestamp >= self.last_timestamp_in_turn and event.pk >= self.last_pk_in_turn)
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
        pass

    def _compute_entering_day(self):
        pass

    def _compute_entering_sunset(self):
        new_mayor = self._compute_elected_mayor()
        if new_mayor is not None:
            #TODO
            pass

        winner = self._compute_vote_winner()
        if winner is not None:
            # TODO
            pass

    def _compute_elected_mayor(self):
        prev_turn = self.current_turn.prev_turn(must_exist=True)
        votes = CommandEvents.objects.filter(turn=prev_turn).filter(type=ELECT).order_by(Event.timestamp)
        new_mayor = None

        # TODO

        return new_mayor

    def _compute_vote_winner(self):
        prev_turn = self.current_turn.prev_turn(must_exist=True)
        votes = CommandEvents.objects.filter(turn=prev_turn).filter(type=VOTE).order_by(Event.timestamp)
        winner = None

        # Count last ballot for each player
        ballots = {}
        mayor_ballot = None
        for player in self.get_players():
            ballots[player.pk] = None
        for vote in votes:
            ballots[vote.player.pk] = vote
            if vote.player.is_mayor():
                mayor_ballot = vote

        # TODO: count Ipnotista and Spettro dell'Amnesia

        # TODO: check that at least half of the alive people voted; if
        # not, abort the voting

        # TODO: count Spettro della Duplicazione

        # Fill tally sheet
        tally_sheet = {}
        for player in self.get_alive_players():
            tally_sheet[player.pk] = 0
        for ballot in ballots.itervalues():
            tally_sheet[ballot.target.pk] += 1

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

        # TODO: kill the winner
