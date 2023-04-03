from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class Backend(ABC):
    """Base class for all backends"""

    @abstractmethod
    def get_word_metadata(self, word: str) -> (int, datetime, timedelta):
        """
        Get metadata for a word
        :raises KeyError: if word is not found
        :returns: (frequency, last_used, average_speed)
        """

    @abstractmethod
    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a word entry, creating it if it doesn't exist"""

    @abstractmethod
    def check_banned(self, word: str) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """

    @abstractmethod
    def ban_word(self, word: str) -> None:
        """
        Delete a word entry and add it to the ban list
        """

    @abstractmethod
    def unban_word(self, word: str) -> None:
        """
        Remove a word from the ban list
        """

    @abstractmethod
    def list_all_words(self) -> list[(str, int, datetime, timedelta)]:
        """
        List all words in the database
        :returns: list of (word, frequency, last_used, average_speed)
        """

    @abstractmethod
    def list_banned_words(self) -> list[str]:
        """
        List all banned words
        :returns: list of banned words
        """

    def cleanup(self):
        """Close the backend"""
        pass
