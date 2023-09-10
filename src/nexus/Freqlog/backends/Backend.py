from abc import ABC, abstractmethod
from datetime import datetime

from nexus.Freqlog.Definitions import BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    WordMetadata, WordMetadataAttr


class Backend(ABC):
    """Base class for all backends"""

    @abstractmethod
    def get_version(self) -> str:
        """Get backend version"""

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
    def get_banlist_entry(self, word: str, case: CaseSensitivity) -> BanlistEntry | None:
        """
        Get a banlist entry
        :param word: Word to get entry for
        :param case: Case sensitivity
        :return: BanlistEntry if word is banned for the specified case, None otherwise
        """

    @abstractmethod
    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> bool:
        """Log a word entry if not banned, creating it if it doesn't exist"""

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
    def num_words(self, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> int:
        """
        Get number of words in store
        :param case: Case sensitivity
        :return: Number of words in store
        """

    @abstractmethod
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

    @abstractmethod
    def list_chords(self, limit: int, sort_by: ChordMetadataAttr, reverse: bool,
                    case: CaseSensitivity) -> list[ChordMetadata]:
        """
        List chords in the store
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """

    @abstractmethod
    def list_banned_words(self, limit: int, sort_by: BanlistAttr,
                          reverse: bool) -> tuple[set[BanlistEntry], set[BanlistEntry]]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        :returns: Tuple of (banned words with case, banned words without case)
        """

    @abstractmethod
    def merge_backend(self, *args, **kwargs):
        """
        Merge backends
        :raises ValueError: If backend-specific requirements are not met
        """

    def close(self) -> None:
        """Close the backend"""
