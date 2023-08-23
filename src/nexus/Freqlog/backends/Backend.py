from abc import ABC, abstractmethod
from datetime import datetime

from nexus.Freqlog.Definitions import BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    WordMetadata, WordMetadataAttr


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

    # TODO: Support banning chords

    @abstractmethod
    def ban_word(self, word: str, case: CaseSensitivity, time: datetime) -> bool:
        """
        Delete a word entry and add it to the ban list
        :returns: True if word was banned, False if it was already banned
        """

    @abstractmethod
    def unban_word(self, word: str, case: CaseSensitivity) -> bool:
        """
        Remove a word from the ban list
        :returns: True if word was unbanned, False if it was already not banned
        """

    @abstractmethod
    def list_words(self, limit: int = -1, sort_by: WordMetadataAttr = WordMetadataAttr.word,
                   reverse: bool = False, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed, score
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
    def list_banned_words(self, limit: int, sort_by: BanlistAttr, reverse: bool) \
            -> tuple[set[BanlistEntry], set[BanlistEntry]]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        :returns: Tuple of (banned words with case, banned words without case)
        """

    def close(self) -> None:
        """Close the backend"""
