from abc import ABC, abstractmethod
from datetime import datetime

from Freqlog.Definitions import Banlist, BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, WordMetadata, \
    WordMetadataAttr


class Backend(ABC):
    """Base class for all backends"""

    @abstractmethod
    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata | None:
        """
        Get metadata for a word
        :returns: WordMetadata if word is found, None otherwise
        """

    @abstractmethod
    def get_chord_metadata(self, chord: str) -> ChordMetadata | None:
        """
        Get metadata for a chord
        :returns: ChordMetadata if chord is found, None otherwise
        """

    @abstractmethod
    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a word entry, creating it if it doesn't exist"""

    @abstractmethod
    def log_chord(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a chord entry, creating it if it doesn't exist"""

    @abstractmethod
    def check_banned(self, word: str, case: CaseSensitivity) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """

    # TODO: Ban chords

    @abstractmethod
    def ban_word(self, word: str, case: CaseSensitivity) -> None:
        """Delete a word entry and add it to the ban list"""

    @abstractmethod
    def unban_word(self, word: str, case: CaseSensitivity) -> None:
        """Remove a word from the ban list"""

    @abstractmethod
    def list_words(self, limit: int, sort_by: WordMetadataAttr,
                   reverse: bool, case: CaseSensitivity) -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """

    @abstractmethod
    def list_chords(self, limit: int, sort_by: ChordMetadataAttr,
                    reverse: bool, case: CaseSensitivity) -> list[ChordMetadata]:
        """
        List chords in the store
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """

    @abstractmethod
    def list_banned_words(self, limit: int, sort_by: BanlistAttr, reverse: bool) -> list[Banlist]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        """

    def cleanup(self):
        """Close the backend"""
