import logging
import queue
import time
from datetime import datetime, timedelta
from queue import Empty as EmptyException, Queue
from threading import Thread
from typing import Optional

from charachorder import CharaChorder
from pynput import keyboard as kbd, mouse
from serial import SerialException

from .backends import Backend, SQLiteBackend
from .Definitions import ActionType, BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    Defaults, WordMetadata, WordMetadataAttr


class Freqlog:

    def _on_press(self, key: kbd.Key | kbd.KeyCode) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, key, datetime.now()))

    def _on_release(self, key: kbd.Key | kbd.KeyCode) -> None:
        """"Store RELEASE, key and current time in queue"""
        if key in self.modifier_keys:
            self.q.put((ActionType.RELEASE, key, datetime.now()))

    def _on_click(self, _x, _y, button: mouse.Button, _pressed) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, button, datetime.now()))

    def _log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """
        Log a word entry to store if not banned, creating it if it doesn't exist
        :param word: Word to log
        :param start_time: Timestamp of start of word started
        :param end_time: Timestamp of end of word
        :returns: True if word was logged, False if it was banned
        """
        if self.backend.log_word(word, start_time, end_time):
            logging.info(f"Word: {word} - {round((end_time - start_time).total_seconds(), 3)}s")
        else:
            logging.info(f"Banned word, {round((end_time - start_time).total_seconds(), 3)}s")
            logging.debug(f"(Banned word was '{word}')")

    def _log_chord(self, chord: str, start_time: datetime, end_time: datetime) -> None:
        """
        Log a chord entry to store if not banned, creating it if it doesn't exist
        :param chord: Chord to log
        :param start_time: Timestamp of start of chord started
        :param end_time: Timestamp of end of chord
        :returns: True if chord was logged, False if it was banned
        """
        if not self.chords:
            logging.warning("Chords not loaded, not logging chord")
        elif chord not in self.chords:  # TODO: handle chord modifications (i.e. tense, plural, case)
            logging.warning(f"Chord '{chord}' not found in device chords, timing: {start_time} - {end_time}")
        elif self.backend.log_chord(chord, end_time):
            logging.info(f"Chord: {chord} - {end_time}")
        else:
            logging.info(f"Banned chord, {end_time}")
            logging.debug(f"(Banned chord was '{chord}')")

    def _process_queue(self):
        word: str = ""  # word to be logged, reset on criteria below
        word_start_time: datetime | None = None
        word_end_time: datetime | None = None
        chars_since_last_bs: int = 0
        avg_char_time_after_last_bs: timedelta | None = None
        last_key_was_disallowed: bool = False
        active_modifier_keys: set = set()

        def _get_timed_interruptable(q, timeout):
            # Based on https://stackoverflow.com/a/37016663/9206488
            stoploop = time.monotonic() + timeout - 0.5
            while self.is_logging and time.monotonic() < stoploop:
                try:
                    return q.get(block=True, timeout=0.5)  # Allow check for Ctrl-C every second
                except queue.Empty:
                    pass
                except TypeError:  # Weird bug in Threading (File "/usr/lib/python3.11/threading.py", line 324, in wait
                    # gotit = waiter.acquire(True, timeout)
                    #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                    # TypeError: main.<locals>.<lambda>() takes 0 positional arguments but 2 were given)
                    # This except fixes it but I'm not sure what side effects it might have
                    self.is_logging = False
                    raise EmptyException
            if not self.is_logging:
                raise EmptyException

            # Final wait for last fraction of a second
            return q.get(block=True, timeout=max(0, stoploop + 0.5 - time.monotonic()))

        def _log_and_reset_word(min_length: int = 2) -> None:
            """Log word to file and reset word metadata"""
            nonlocal word, word_start_time, word_end_time, chars_since_last_bs, avg_char_time_after_last_bs, \
                last_key_was_disallowed
            if not word:  # Don't log if word is empty
                return

            # Strip whitespace from start and end of word
            word = word.strip()

            # TODO: Do we need to trim word to only substring that is in allowed_chars?

            # Only log words/chords that have >= min_length characters
            if len(word) >= min_length:
                if avg_char_time_after_last_bs and avg_char_time_after_last_bs > timedelta(
                        milliseconds=self.chord_char_threshold):  # Word, based on backspace timing
                    self._log_word(word, word_start_time, word_end_time)
                else:  # Chord
                    self._log_chord(word, word_start_time, word_end_time)

            word = ""
            word_start_time = None
            word_end_time = None
            chars_since_last_bs = 0
            avg_char_time_after_last_bs = None
            last_key_was_disallowed = False

        while self.is_logging:
            try:
                action: ActionType
                key: kbd.Key | kbd.KeyCode | mouse.Button
                time_pressed: datetime

                # Blocking here makes the while-True non-blocking
                action, key, time_pressed = _get_timed_interruptable(self.q, self.new_word_threshold)

                # Debug keystrokes
                if isinstance(key, kbd.Key) or isinstance(key, kbd.KeyCode):
                    logging.debug(f"{action}: {key} - {time_pressed}")
                    logging.debug(f"word: '{word}', active_modifier_keys: {active_modifier_keys}")

                # Update modifier keys
                if action == ActionType.PRESS and key in self.modifier_keys:
                    active_modifier_keys.add(key)
                elif action == ActionType.RELEASE:
                    active_modifier_keys.discard(key)

                # On backspace, remove last char from word if word is not empty
                if key == kbd.Key.backspace and word:
                    if active_modifier_keys.intersection({kbd.Key.ctrl, kbd.Key.ctrl_l, kbd.Key.ctrl_r,
                                                          kbd.Key.cmd, kbd.Key.cmd_l, kbd.Key.cmd_r}):
                        # Remove last word from word
                        # FIXME: make this work - rn _log_and_reset_word() is called immediately upon ctrl/cmd keydown
                        # TODO: make this configurable (i.e. for vim, etc)
                        if " " in word:
                            word = word[:word.rfind(" ")]
                        elif "\t" in word:
                            word = word[:word.rfind("\t")]
                        elif "\n" in word:
                            word = word[:word.rfind("\n")]
                        else:  # Word is only one word
                            word = ""
                    else:
                        logging.debug(f"Backspace: {word} -> {word[:-1]}")
                        word = word[:-1]
                    chars_since_last_bs = 0
                    avg_char_time_after_last_bs = None
                    self.q.task_done()
                    continue

                # Handle whitespace/disallowed keys
                if ((isinstance(key, kbd.Key) and key in {kbd.Key.space, kbd.Key.tab, kbd.Key.enter}) or
                        (isinstance(key, kbd.KeyCode) and (not key.char or key.char not in self.allowed_chars))):
                    # If key is whitespace/disallowed and timing is more than chord_char_threshold, log and reset word
                    if (word and avg_char_time_after_last_bs and
                            avg_char_time_after_last_bs > timedelta(milliseconds=self.chord_char_threshold)):
                        logging.debug(f"Whitespace/disallowed, log+reset: {word}")
                        _log_and_reset_word()
                    else:  # Add key to chord
                        match key:
                            case kbd.Key.space:
                                word += " "
                            case kbd.Key.tab:
                                word += "\t"
                            case kbd.Key.enter:
                                word += "\n"
                            case _:
                                if isinstance(key, kbd.KeyCode) and key.char:
                                    word += key.char
                        last_key_was_disallowed = True
                    self.q.task_done()
                    continue

                # On non-chord key, log and reset word if it exists
                #   Non-chord key = key in modifier keys or non-key
                # FIXME: support modifier keys in chords
                if key in self.modifier_keys or not (isinstance(key, kbd.Key) or isinstance(key, kbd.KeyCode)):
                    logging.debug(f"Non-chord key: {key}")
                    if word:
                        _log_and_reset_word()
                    self.q.task_done()
                    continue

                # Add new char to word and update word timing if no modifier keys are pressed
                if isinstance(key, kbd.KeyCode) and not active_modifier_keys and key.char:
                    # I think this is for chords that end in space
                    # If last key was disallowed and timing of this key is more than chord_char_threshold, log+reset
                    if (last_key_was_disallowed and word and word_end_time and
                            (time_pressed - word_end_time) > timedelta(milliseconds=self.chord_char_threshold)):
                        logging.debug(f"Disallowed and timing, log+reset: {word}")
                        _log_and_reset_word()
                    word += key.char
                    chars_since_last_bs += 1

                    # TODO: code below potentially needs to be copied to edge cases above
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

            except EmptyException:  # Queue is empty
                # If word is older than NEW_WORD_THRESHOLD seconds, log and reset word
                if word:
                    _log_and_reset_word()
                if not self.is_logging:
                    # Cleanup and exit if queue is empty and logging is stopped
                    self.backend.close()
                    logging.warning("Stopped freqlogging")
                    break

    def _get_chords(self):
        """
        Get chords from device
        """
        if self.device is None:
            return

        with self.device:
            logging.info(f"Getting {self.device.get_chordmap_count()} chords from device")
            self.chords = []
            started_logging = False  # prevent early short-circuit
            for chord, phrase in self.device.get_chordmaps():
                self.chords.append(str(phrase).strip())
                if not self.is_logging:  # Short circuit if logging is stopped
                    if started_logging:
                        logging.info("Stopped getting chords from device")
                        break
                else:
                    started_logging = True
            else:
                logging.info(f"Got {len(self.chords)} chords from device")

    @staticmethod
    def is_backend_initialized(backend_path: str) -> bool:
        """
        Check if backend is initialized
        :param backend_path: Path to backend (currently == SQLiteBackend)
        :raises the same exceptions as SQLiteBackend.does_db_exist():
        :return: True if backend is initialized, False otherwise
        """
        return SQLiteBackend.is_db_populated(backend_path)

    def __init__(self, backend_path: str, password_callback: callable, loggable: bool = True,
                 upgrade_callback: Optional[callable] = None) -> None:
        """
        Initialize Freqlog
        :param backend_path: Path to backend (currently == SQLiteBackend)
        :param password_callback: Callback to call to get password to encrypt/decrypt banlist entries
                Should take one argument: whether the password is being set for the first time
        :param loggable: Whether to create listeners
        :param upgrade_callback: Callback to run if database is upgraded
        :raises ValueError: If the database version is newer than the current version
        :raises PermissionError: If the database path is not readable or writable
        :raises IsADirectoryError: If the database path is not a file
        :raises FileNotFoundError: If the database path does not exist
        :raises cryptography.fernet.InvalidToken: If the password is incorrect
        """
        logging.info("Initializing freqlog")
        self.device: CharaChorder | None = None
        self.chords: list[str] | None = None
        self.num_chords: int | None = None

        # Get serial device
        devices = CharaChorder.list_devices()
        if len(devices) == 0:
            logging.warning("No CharaChorder devices found")
        else:
            if len(devices) > 1:  # TODO: provide a selection method for users (including in GUI)
                logging.warning(f"Multiple CharaChorder devices found, using: {devices[0]}")
                logging.debug(f"Other devices: {devices[1:]}")
            logging.info(f"Connecting to CharaChorder device at {devices[0]}")
            try:
                self.device = devices[0]
                with self.device:
                    self.num_chords = self.device.get_chordmap_count()
            except SerialException as e:
                logging.error(f"Failed to connect to CharaChorder device: {devices[0]}")
                logging.error(e)
            except IOError as e:
                logging.error(f"I/O error while getting number of chords from CharaChorder device: {devices[0]}")
                logging.error(e)

        self.is_logging: bool = False  # Used in self._get_chords, needs to be initialized here
        if loggable:
            logging.info(f"Logging set to freqlog db at {backend_path}")

            # Asynchronously get chords from device
            Thread(target=self._get_chords).start()

        self.backend: Backend = SQLiteBackend(backend_path, password_callback, upgrade_callback)
        self.q: Queue = Queue()
        self.listener: kbd.Listener | None = None
        self.mouse_listener: mouse.Listener | None = None
        if loggable:
            self.listener = kbd.Listener(on_press=self._on_press, on_release=self._on_release, name="Keyboard Listener")
            self.mouse_listener = mouse.Listener(on_click=self._on_click, name="Mouse Listener")
        self.new_word_threshold: float = Defaults.DEFAULT_NEW_WORD_THRESHOLD
        self.chord_char_threshold: int = Defaults.DEFAULT_CHORD_CHAR_THRESHOLD
        self.allowed_chars: set = Defaults.DEFAULT_ALLOWED_CHARS
        self.allowed_first_chars: set = Defaults.DEFAULT_ALLOWED_FIRST_CHARS
        self.modifier_keys: set = Defaults.DEFAULT_MODIFIER_KEYS
        self.killed: bool = False

    def start_logging(self, new_word_threshold: float | None = None, chord_char_threshold: int | None = None,
                      allowed_chars: set | str | None = None, allowed_first_chars: set | str | None = None,
                      modifier_keys: set = None) -> None:
        if isinstance(allowed_chars, set):
            self.allowed_chars = allowed_chars
        elif isinstance(allowed_chars, str):
            self.allowed_chars = set(allowed_chars)
        if isinstance(allowed_first_chars, set):
            self.allowed_first_chars = allowed_first_chars
        elif isinstance(allowed_first_chars, str):
            self.allowed_first_chars = set(allowed_first_chars)
        if modifier_keys is not None:
            self.modifier_keys = modifier_keys
        if new_word_threshold is not None:
            self.new_word_threshold = new_word_threshold
        if chord_char_threshold is not None:
            self.chord_char_threshold = chord_char_threshold

        logging.info("Starting freqlogging")
        logging.debug(f"new_word_threshold={self.new_word_threshold}, "
                      f"chord_char_threshold={self.chord_char_threshold}, "
                      f"allowed_chars={self.allowed_chars}, "
                      f"allowed_first_chars={self.allowed_first_chars}, "
                      f"modifier_keys={self.modifier_keys}")
        self.listener.start()
        self.mouse_listener.start()
        self.is_logging = True
        logging.warning("Started freqlogging")
        self._process_queue()

    def stop_logging(self) -> None:  # FIXME: find out why this runs twice on one Ctrl-C (does it still?)
        if self.killed:  # TODO: Forcibly kill if already killed once
            exit(1)  # This doesn't work rn
        self.killed = True
        logging.warning("Stopping freqlog")
        if self.listener:
            self.listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.is_logging = False
        logging.info("Stopped listeners")

    def get_backend_version(self) -> str:
        """Get backend version"""
        logging.info("Getting backend version")
        return self.backend.get_version()

    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata:
        """Get metadata for a word"""
        logging.info(f"Getting metadata for '{word}', case {case.name}")
        return self.backend.get_word_metadata(word, case)

    def get_chord_metadata(self, chord: str) -> ChordMetadata | None:
        """
        Get metadata for a chord
        :returns: ChordMetadata if chord is found, None otherwise
        """
        logging.info(f"Getting metadata for '{chord}'")
        return self.backend.get_chord_metadata(chord)

    def get_banlist_entry(self, word: str) -> BanlistEntry | None:
        """
        Get a banlist entry
        :param word: Word to get entry for
        :return: BanlistEntry if word is banned for the specified case, None otherwise
        """
        logging.info(f"Getting banlist entry for '{word}'")
        return self.backend.get_banlist_entry(word)

    def check_banned(self, word: str) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        logging.info(f"Checking if '{word}' is banned")
        return self.backend.check_banned(word)

    def ban_word(self, word: str, time_added: datetime = datetime.now()) -> bool:
        """
        Delete a word/chord entry and add it to the ban list
        :returns: True if word was banned, False if it was already banned
        """
        logging.info(f"Banning '{word}' - {time}")
        res = self.backend.ban_word(word, time_added)
        if res:
            logging.warning(f"Banned '{word}'")
        else:
            logging.warning(f"'{word}' is already banned")
        return res

    def ban_words(self, entries: list[str], time_added: datetime = datetime.now()) -> list[bool]:
        """
        Delete multiple word entries and add them to the ban list
        :param entries: dict of {word to ban: case sensitivity}
        :param time_added: Time to add to banlist
        :return: list of bools, True if word was banned, False if it was already banned
        """
        logging.info(f"Banning {len(entries)} words - {time_added}")
        return [self.ban_word(word, time_added) for word in entries]

    def delete_word(self, word: str, case: CaseSensitivity) -> bool:
        """
        Delete a word/chord entry
        :returns: True if word was deleted, False if it's not in the database
        """
        logging.info(f"Deleting '{word}', case {case.name}")
        res = self.backend.delete_word(word, case)
        if res:
            logging.warning(f"Deleted '{word}', case {case.name}")
        else:
            logging.warning(f"'{word}', case {case.name} doesn't exist in freqlog")
        return res

    def delete_words(self, entries: dict[str: CaseSensitivity]) -> list[bool]:
        """
        Delete multiple word entries
        :param entries: dict of {word to delete: case sensitivity}
        :return: list of bools, True if word was deleted, False if it was already deleted
        """
        logging.info(f"Deleting {len(entries)} words")
        return [self.delete_word(word, case) for word, case in entries.items()]

    def unban_word(self, word: str) -> bool:
        """
        Remove a banlist entry
        :param word: Word to unban
        :returns: True if word was unbanned, False if it was already not banned
        """
        logging.info(f"Unbanning '{word}'")
        res = self.backend.unban_word(word)
        if res:
            logging.warning(f"Unbanned '{word}'")
        else:
            logging.warning(f"'{word}' isn't banned")
        return res

    def unban_words(self, entries: list[str]) -> list[bool]:
        """
        Remove multiple banlist entries
        :param entries: dict of {word to ban: case sensitivity}
        :return: list of bools, True if word was unbanned, False if it was already unbanned
        """
        logging.info(f"Unbanning {len(entries)} words")
        return [self.unban_word(word) for word in entries]

    def num_words(self, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> int:
        """
        Get number of words in store
        :param case: Case sensitivity
        :return: Number of words in store
        """
        logging.info("Getting number of words")
        return self.backend.num_words(case)

    def list_words(self, limit: int = -1, sort_by: WordMetadataAttr = WordMetadataAttr.score, reverse: bool = True,
                   case: CaseSensitivity = CaseSensitivity.INSENSITIVE, search: str = "") -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed, score
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        :param search: Part of word to search for
        """
        logging.info(
            f"Listing words, limit {limit}, sort_by {sort_by}, reverse {reverse}, case {case.name}, search {search}")
        return self.backend.list_words(limit, sort_by, reverse, case, search)

    def export_words_to_csv(self, export_path: str, limit: int = -1, sort_by: WordMetadataAttr = WordMetadataAttr.score,
                            reverse: bool = True, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> int:
        """
        Export words in the store
        :param export_path: Path to csv file to export to
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed, score
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        :return: Number of words exported
        """
        logging.info(f"Exporting words, limit {limit}, sort_by {sort_by}, reverse {reverse}, case {case.name}")
        words = self.backend.list_words(limit, sort_by, reverse, case)
        with open(export_path, "w") as f:
            f.write(",".join(filter(lambda k: not k.startswith("_"), WordMetadataAttr.__dict__.keys())) + "\n")
            f.write("\n".join(map(lambda w: ",".join(map(str, w.__dict__.values())), words)))
        logging.info(f"Exported {len(words)} words to {export_path}")
        return len(words)

    def num_logged_chords(self) -> int:
        """
        Get number of chords in store
        :return: Number of chords in store
        """
        logging.info("Getting number of logged chords")
        return self.backend.num_chords()

    def list_logged_chords(self, limit: int = -1, sort_by: ChordMetadataAttr = ChordMetadataAttr.score,
                           reverse: bool = True, search: str = "") -> list[ChordMetadata]:
        """
        List chords in the store
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param search: Part of chord to search for
        """
        logging.info(f"Listing chords, limit {limit}, sort_by {sort_by}, reverse {reverse}, search {search}")
        return self.backend.list_chords(limit, sort_by, reverse, search)

    def export_chords_to_csv(self, export_path: str, limit: int = -1,
                             sort_by: ChordMetadataAttr = ChordMetadataAttr.score,
                             reverse: bool = True) -> int:
        """
        Export chords in the store
        :param export_path: Path to csv file to export to
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :return: Number of chords exported
        """
        logging.info(f"Exporting chords, limit {limit}, sort_by {sort_by}, reverse {reverse}")
        chords = self.backend.list_chords(limit, sort_by, reverse)
        with open(export_path, "w") as f:
            f.write(",".join(filter(lambda k: not k.startswith("_"), ChordMetadataAttr.__dict__.keys())) + "\n")
            f.write("\n".join(map(lambda c: ",".join(map(str, c.__dict__.values())), chords)))
        logging.info(f"Exported {len(chords)} chords to {export_path}")
        return len(chords)

    def delete_logged_chord(self, chord: str) -> bool:
        """
        Delete a chord entry
        :returns: True if chord was deleted, False if it's not in the database
        """
        logging.info(f"Deleting '{chord}'")
        res = self.backend.delete_chord(chord)
        if res:
            logging.warning(f"Deleted '{chord}'")
        else:
            logging.warning(f"'{chord}' doesn't exist in freqlog")
        return res

    def delete_logged_chords(self, chords: list[str]) -> list[bool]:
        """
        Delete multiple chord entries
        :param chords: list of chords to delete
        :return: list of bools, True if chord was deleted, False if it was already deleted
        """
        logging.info(f"Deleting {len(chords)} chords")
        return [self.delete_logged_chord(chord) for chord in chords]

    def list_banned_words(self, limit: int = -1, sort_by: BanlistAttr = BanlistAttr.word,
                          reverse: bool = False) -> list[BanlistEntry]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        :returns: List of banned words
        """
        logging.info(f"Listing banned words, limit {limit}, sort_by {sort_by}, reverse {reverse}")
        return self.backend.list_banned_words(limit, sort_by, reverse)

    def merge_backends(self, *args, **kwargs):
        """
        Merge backends
        :raises ValueError: If backend-specific requirements are not met
        """
        logging.info(f"Merging backends: {args} {kwargs}")
        self.backend.merge_backend(*args, **kwargs)
