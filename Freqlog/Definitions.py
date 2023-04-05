from datetime import datetime, timedelta
from enum import Enum

from pynput import keyboard as kbd


class Defaults:
    # Allowed keys in chord output: a-z, A-Z, 0-9, apostrophe, dash, underscore, slash, backslash, tilde
    DEFAULT_ALLOWED_KEYS_IN_CHORD: set = {chr(i) for i in range(97, 123)} | {chr(i) for i in range(65, 91)} | \
                                         {chr(i) for i in range(48, 58)} | {"'", "-", "_", "/", "\\", "~"}
    DEFAULT_MODIFIER_KEYS: set = {kbd.Key.ctrl, kbd.Key.ctrl_l, kbd.Key.ctrl_r, kbd.Key.alt, kbd.Key.alt_l,
                                  kbd.Key.alt_r,
                                  kbd.Key.alt_gr, kbd.Key.cmd, kbd.Key.cmd_l, kbd.Key.cmd_r}
    DEFAULT_NEW_WORD_THRESHOLD: float = 5  # seconds after which character input is considered a new word
    DEFAULT_CHORD_CHAR_THRESHOLD: int = 30  # milliseconds between characters in a chord to be considered a chord
    DEFAULT_DB_PATH: str = "nexus_freqlog_db.sqlite3"


class ActionType(Enum):
    """Enum for key action type"""
    PRESS = 1
    RELEASE = 2


class CaseSensitivity(Enum):
    """Enum for case sensitivity"""
    INSENSITIVE = 1
    SENSITIVE = 2
    SENSITIVE_FIRST_CHAR = 3


class WordMetadata:
    """Metadata for a word"""

    def __init__(self, word: str, frequency: int, last_used: datetime, average_speed: timedelta) -> None:
        self.word = word
        self.frequency = frequency
        self.last_used = last_used
        self.average_speed = average_speed


class WordMetadataAttr(Enum):
    """Enum for word metadata attributes"""
    WORD = "word"
    FREQUENCY = "frequency"
    LAST_USED = "lastused"
    AVERAGE_SPEED = "avgspeed"


class ChordMetadata:
    """Metadata for a chord"""

    def __init__(self, chord: str, frequency: int, last_used: datetime, average_speed: timedelta) -> None:
        self.chord = chord
        self.frequency = frequency
        self.last_used = last_used


class ChordMetadataAttr(Enum):
    """Enum for chord metadata attributes"""
    CHORD = "chord"
    FREQUENCY = "frequency"
    LAST_USED = "lastused"


class Banlist:
    """Banlist entry"""

    def __init__(self, word: str, date_added: datetime) -> None:
        self.word = word
        self.date_added = date_added


class BanlistAttr(Enum):
    """Enum for banlist attributes"""
    WORD = "word"
    DATE_ADDED = "dateadded"
