import logging
from datetime import datetime, timedelta
from enum import Enum
from queue import Queue, Empty as EmptyException

from pynput import keyboard, mouse

from Freqlog.backends.Backend import Backend
from Freqlog.backends.SQLite.SQLiteBackend import SQLiteBackend

# Allowed keys in chord output: a-z, A-Z, 0-9, apostrophe, dash, underscore, slash, backslash, tilde
ALLOWED_KEYS_IN_CHORD: list = [chr(i) for i in range(97, 123)] + [chr(i) for i in range(65, 91)] + \
                              [chr(i) for i in range(48, 58)] + ["'", "-", "_", "/", "\\", "~"]
MODIFIER_KEYS: list = [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt,
                       keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr, keyboard.Key.cmd,
                       keyboard.Key.cmd_l, keyboard.Key.cmd_r]
NEW_WORD_THRESHOLD: float = 5  # seconds after which character input is considered a new word
CHORD_CHAR_THRESHOLD: int = 30  # milliseconds between characters in a chord to be considered a chord
DB_PATH: str = "nexus_freqlog_db.sqlite3"

logging.basicConfig(filename="log.txt", level=logging.DEBUG, format="%(asctime)s - %(message)s")


class ActionType(Enum):
    """Enum for key action type"""
    PRESS = 1
    RELEASE = 2


class CaseSensitivity(Enum):
    """Enum for case sensitivity"""
    CASE_INSENSITIVE = 1
    CASE_SENSITIVE = 2
    CASE_SENSITIVE_FIRST_CHAR = 3


class Freqlog:

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, key, datetime.now()))

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """"Store RELEASE, key and current time in queue"""
        self.q.put((ActionType.RELEASE, key, datetime.now()))

    def _on_click(self, x, y, button: mouse.Button, pressed) -> None:
        """Store PRESS, key and current time in queue"""
        self.q.put((ActionType.PRESS, button, datetime.now()))

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log word to file"""
        logging.debug(f"{word} - {start_time} - {end_time}")
        self.backend.log_word(word, start_time, end_time)

    def __init__(self):
        self.backend: Backend = SQLiteBackend(DB_PATH)
        self.q: Queue = Queue()
        self.listener: keyboard.Listener | None = None
        self.mouse_listener: mouse.Listener | None = None
        self.logging: bool = False

    def start_logging(self) -> None:
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        self.logging = True

        word: str = ""  # word to be logged, reset on non-chord keys
        word_start_time: datetime | None = None
        word_end_time: datetime | None = None
        chars_since_last_bs: int = 0
        avg_char_time_after_last_bs: timedelta | None = None

        modifier_keys: set = set()

        def _log_and_reset_word(min_length: int = 1,
                                case_sensitivity: CaseSensitivity = CaseSensitivity.CASE_SENSITIVE_FIRST_CHAR) -> None:
            """Log word to file and reset word metadata"""
            nonlocal word, word_start_time, word_end_time, chars_since_last_bs, avg_char_time_after_last_bs
            if not word:  # Don't log if word is empty
                return

            # Normalize case if necessary
            match case_sensitivity:
                case CaseSensitivity.CASE_INSENSITIVE:
                    word = word.lower()
                case CaseSensitivity.CASE_SENSITIVE_FIRST_CHAR:
                    word = word[0].lower() + word[1:]
                case CaseSensitivity.CASE_SENSITIVE:
                    pass

            # Only log words that have more than min_length characters and are not chords
            if len(word) > min_length and avg_char_time_after_last_bs and avg_char_time_after_last_bs > timedelta(
                    milliseconds=CHORD_CHAR_THRESHOLD):
                self.log_word(word, word_start_time, word_end_time)
            word = ""
            word_start_time = None
            word_end_time = None
            chars_since_last_bs = 0
            avg_char_time_after_last_bs = None

        while True:
            try:
                action: ActionType
                key: keyboard.Key | keyboard.KeyCode | mouse.Button
                time_pressed: datetime
                action, key, time_pressed = self.q.get(block=False)

                # Update modifier keys
                if action == ActionType.PRESS and key in MODIFIER_KEYS:
                    modifier_keys.add(key)
                elif action == ActionType.RELEASE and key in MODIFIER_KEYS:
                    modifier_keys.remove(key)

                # Ignore non-modifier release events
                if action == ActionType.RELEASE:
                    self.q.task_done()
                    continue

                # On backspace, remove last char from word if word is not empty
                if key == keyboard.Key.backspace and word:
                    word = word[:-1]
                    chars_since_last_bs = 0
                    avg_char_time_after_last_bs = None
                    self.q.task_done()
                    continue

                # On non-chord key, log and reset word if it exists
                if not (isinstance(key, keyboard.KeyCode) and key.char in ALLOWED_KEYS_IN_CHORD):
                    if word:
                        _log_and_reset_word()
                    self.q.task_done()
                    continue

                # Add new char to word and update word timing if no modifier keys are pressed
                if not modifier_keys:
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
                if word and (datetime.now() - word_end_time).total_seconds() > NEW_WORD_THRESHOLD:
                    _log_and_reset_word()
                elif not word and not self.logging:
                    break

    def stop_logging(self) -> None:
        self.listener.stop()
        self.mouse_listener.stop()
        self.logging = False
