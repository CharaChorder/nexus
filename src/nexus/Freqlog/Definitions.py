from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Self

from pynput.keyboard import Key


class Defaults:
    # Allowed keys in chord output: a-z, A-Z, 0-9, apostrophe, dash, underscore, slash, backslash, tilde
    DEFAULT_ALLOWED_KEYS_IN_CHORD: set = {chr(i) for i in range(97, 123)} | {chr(i) for i in range(65, 91)} | \
                                         {chr(i) for i in range(48, 58)} | {"'", "-", "_", "/", "\\", "~"}
    DEFAULT_MODIFIER_KEYS: set = {Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr, Key.cmd,
                                  Key.cmd_l, Key.cmd_r}
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
    FIRST_CHAR = 3


class Order(Enum):
    """Enum for order"""
    ASCENDING = True
    DESCENDING = False


class WordMetadata:
    """Metadata for a word"""

    def __init__(self, word: str, frequency: int, last_used: datetime, average_speed: timedelta) -> None:
        self.word = word
        self.frequency = frequency
        self.last_used = last_used
        self.average_speed = average_speed
        self.score = len(word) * frequency

    def __or__(self, other: Any) -> Self:
        """Merge two WordMetadata objects"""
        if other is not None and not isinstance(other, WordMetadata):
            raise TypeError(f"unsupported operand type(s) for |: '{type(self).__name__}' and '{type(other).__name__}'")
        if other is None:
            return self
        if self.word != other.word:
            raise ValueError(f"Cannot merge WordMetadata objects with different words: {self.word} and {other.word}")
        return WordMetadata(
            self.word,
            self.frequency + other.frequency,
            max(self.last_used, other.last_used),
            (self.average_speed * self.frequency + other.average_speed * other.frequency) / (
                    self.frequency + other.frequency)
        )

    def __str__(self) -> str:
        return f"Word: {self.word} | Frequency: {self.frequency} | Last used: {self.last_used} | " \
               f"Average speed: {self.average_speed} | Score: {self.score}"

    def __repr__(self) -> str:
        return f"WordMetadata({self.word})"


class WordMetadataAttr(Enum):
    """Enum for word metadata attributes"""
    word = "word"
    frequency = "frequency"
    last_used = "lastused"
    average_speed = "avgspeed"
    score = "score"


WordMetadataAttrLabel = {WordMetadataAttr.word: "Word",
                         WordMetadataAttr.frequency: "Freq.",
                         WordMetadataAttr.last_used: "Last used",
                         WordMetadataAttr.average_speed: "Avg. speed",
                         WordMetadataAttr.score: "Score"}


class ChordMetadata:
    """Metadata for a chord"""

    def __init__(self, chord: str, frequency: int, last_used: datetime) -> None:
        self.chord = chord
        self.frequency = frequency
        self.last_used = last_used

    def __str__(self) -> str:
        return f"Chord: {self.chord} | Frequency: {self.frequency} | Last used: {self.last_used} | "


class ChordMetadataAttr(Enum):
    """Enum for chord metadata attributes"""
    chord = "chord"
    frequency = "frequency"
    last_used = "lastused"


class BanlistEntry:
    """Banlist entry"""

    def __init__(self, word: str, date_added: datetime) -> None:
        self.word = word
        self.date_added = date_added

    def __str__(self) -> str:
        return f"Word: {self.word} | Date added: {self.date_added}"


class BanlistAttr(Enum):
    """Enum for banlist attributes"""
    word = "word"
    date_added = "dateadded"
