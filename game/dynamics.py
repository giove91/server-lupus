# -*- coding: utf-8 -*-

from django.db.models import Q

from threading import RLock

from models import Event, Turn
import roles

# TODO: implement proper locking

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

        self.last_timestamp_in_turn = turn.begin
        self.last_pk_in_turn = -1

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
