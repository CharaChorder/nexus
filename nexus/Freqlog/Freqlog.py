import logging
from datetime import datetime, timedelta
from queue import Empty as EmptyException, Queue

from pynput import keyboard as kbd, mouse

from .backends import Backend, SQLiteBackend
from .Definitions import ActionType, Banlist, BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    Defaults, WordMetadata, WordMetadataAttr


# TODO: Add more (info) logging
class Freqlog:

    def _on_press(self, key: kbd.Key | kbd.KeyCode) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, key, datetime.now()))

    def _on_release(self, key: kbd.Key | kbd.KeyCode) -> None:
        """"Store RELEASE, key and current time in queue"""
        self.q.put((ActionType.RELEASE, key, datetime.now()))

    def _on_click(self, _x, _y, button: mouse.Button, _pressed) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, button, datetime.now()))

    def _log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log word to store"""
        logging.debug(f"Word: {word} - {start_time} - {end_time}")
        self.backend.log_word(word, start_time, end_time)

    def _log_chord(self, chord: str, start_time: datetime, end_time: datetime) -> None:
        """Log chord to store"""
        logging.debug(f"Chord: {chord} - {start_time} - {end_time}")
        self.backend.log_chord(chord, start_time, end_time)

    def __init__(self, db_path: str = Defaults.DEFAULT_DB_PATH):
        self.backend: Backend = SQLiteBackend(db_path)
        self.q: Queue = Queue()
        self.listener: kbd.Listener | None = None
        self.mouse_listener: mouse.Listener | None = None
        self.is_logging: bool = False

    def start_logging(self, new_word_threshold: int = Defaults.DEFAULT_NEW_WORD_THRESHOLD,
                      chord_char_threshold: int = Defaults.DEFAULT_CHORD_CHAR_THRESHOLD,
                      allowed_keys_in_chord: set | str | None = None, modifier_keys: set | None = None) -> None:
        if allowed_keys_in_chord is None:
            allowed_keys_in_chord = Defaults.DEFAULT_ALLOWED_KEYS_IN_CHORD
        elif isinstance(allowed_keys_in_chord, str):
            allowed_keys_in_chord = set(allowed_keys_in_chord)
        if modifier_keys is None:
            modifier_keys = Defaults.DEFAULT_MODIFIER_KEYS
        self.listener = kbd.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        self.is_logging = True
        logging.info("Started freqlogging")

        word: str = ""  # word to be logged, reset on non-chord keys
        word_start_time: datetime | None = None
        word_end_time: datetime | None = None
        chars_since_last_bs: int = 0
        avg_char_time_after_last_bs: timedelta | None = None

        active_modifier_keys: set = set()

        def _log_and_reset_word(min_length: int = 1) -> None:
            """Log word to file and reset word metadata"""
            nonlocal word, word_start_time, word_end_time, chars_since_last_bs, avg_char_time_after_last_bs
            if not word:  # Don't log if word is empty
                return

            # Note: Now done on retrieval
            # # Normalize case if necessary
            # match case_sensitivity:
            #     case CaseSensitivity.INSENSITIVE:
            #         word = word.lower()
            #     case CaseSensitivity.SENSITIVE_FIRST_CHAR:
            #         word = word[0].lower() + word[1:]
            #     case CaseSensitivity.SENSITIVE:
            #         pass

            # Only log words that have more than min_length characters and are not chords
            if len(word) > min_length:
                if avg_char_time_after_last_bs and avg_char_time_after_last_bs > timedelta(
                        milliseconds=chord_char_threshold):
                    self._log_word(word, word_start_time, word_end_time)
                else:
                    # TODO: Switch over when chord logging implemented
                    # self._log_chord(word, word_start_time, word_end_time)
                    pass
            word = ""
            word_start_time = None
            word_end_time = None
            chars_since_last_bs = 0
            avg_char_time_after_last_bs = None

        while True:
            try:
                action: ActionType
                key: kbd.Key | kbd.KeyCode | mouse.Button
                time_pressed: datetime
                action, key, time_pressed = self.q.get(block=False)

                # Update modifier keys
                if action == ActionType.PRESS and key in modifier_keys:
                    active_modifier_keys.add(key)
                elif action == ActionType.RELEASE and key in modifier_keys:
                    active_modifier_keys.remove(key)

                # Ignore non-modifier release events
                if action == ActionType.RELEASE:
                    self.q.task_done()
                    continue

                # On backspace, remove last char from word if word is not empty
                if key == kbd.Key.backspace and word:
                    word = word[:-1]
                    chars_since_last_bs = 0
                    avg_char_time_after_last_bs = None
                    self.q.task_done()
                    continue

                # On non-chord key, log and reset word if it exists
                if not (isinstance(key, kbd.KeyCode) and key.char in allowed_keys_in_chord):
                    if word:
                        _log_and_reset_word()
                    self.q.task_done()
                    continue

                # Add new char to word and update word timing if no modifier keys are pressed
                if not active_modifier_keys:
                    word += key.char
                    chars_since_last_bs += 1
                    if not word_start_time:
                        word_start_time = time_pressed
                    elif chars_since_last_bs > 1 and avg_char_time_after_last_bs:
                        # Should only get here if chars_since_last_bs > 2
                        avg_char_time_after_last_bs = (avg_char_time_after_last_bs * (chars_since_last_bs - 1) +
                                                       (time_pressed - word_end_time)) / chars_since_last_bs
                    elif chars_since_last_bs > 1:
                        avg_char_time_after_last_bs = time_pressed - word_end_time
                    word_end_time = time_pressed
                    self.q.task_done()
            except EmptyException:  # queue is empty
                # If word is older than NEW_WORD_THRESHOLD seconds, log and reset word
                if word and (datetime.now() - word_end_time).total_seconds() > new_word_threshold:
                    _log_and_reset_word()
                elif not word and not self.is_logging:
                    # Cleanup and exit if queue is empty and logging is stopped
                    self.backend.close()
                    logging.info("Stopped freqlogging")
                    break

    def stop_logging(self) -> None:
        self.listener.stop()
        self.mouse_listener.stop()
        self.is_logging = False
        logging.info("Stopping freqlog")

    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata:
        """Get metadata for a word"""
        return self.backend.get_word_metadata(word, case)

    def get_chord_metadata(self, chord: str) -> ChordMetadata | None:
        """
        Get metadata for a chord
        :returns: ChordMetadata if chord is found, None otherwise
        """
        return self.backend.get_chord_metadata(chord)

    def check_banned(self, word: str, case: CaseSensitivity) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        return self.backend.check_banned(word, case)

    def ban_word(self, word: str, case: CaseSensitivity) -> None:
        """Ban a word from being logged"""
        self.backend.ban_word(word, case)

    def unban_word(self, word: str, case: CaseSensitivity) -> None:
        """Unban a word"""
        self.backend.unban_word(word, case)

    def list_words(self, limit: int, sort_by: WordMetadataAttr,
                   reverse: bool, case: CaseSensitivity) -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """
        return self.backend.list_words(limit, sort_by, reverse, case)

    def list_chords(self, limit: int, sort_by: ChordMetadataAttr,
                    reverse: bool, case: CaseSensitivity) -> list[ChordMetadata]:
        """
        List chords in the store
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """
        return self.backend.list_chords(limit, sort_by, reverse, case)

    def list_banned_words(self, limit: int, sort_by: BanlistAttr, reverse: bool) -> list[Banlist]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        """
        return self.backend.list_banned_words(limit, sort_by, reverse)
