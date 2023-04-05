import sqlite3
from datetime import datetime, timedelta

from Freqlog.backends.Backend import Backend
from Freqlog.Definitions import Banlist, BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, WordMetadata, \
    WordMetadataAttr


class SQLiteBackend(Backend):

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._execute("CREATE TABLE IF NOT EXISTS freqlog"
                      "(word TEXT PRIMARY KEY, frequency INTEGER, lastused timestamp, avgspeed REAL)")
        self._execute("CREATE TABLE IF NOT EXISTS banlist (word TEXT PRIMARY KEY)")

    def _execute(self, query: str, params=None) -> None:
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        self.conn.commit()

    def _fetchone(self, query: str, params=None) -> tuple:
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self.cursor.fetchone()

    def _fetchall(self, query: str, params=None) -> list[tuple]:
        if params:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self.cursor.fetchall()

    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata:
        """
        Get metadata for a word
        :raises KeyError: if word is not found
        """
        # TODO: Handle case sensitivity
        res = self._fetchone("SELECT frequency, lastused, avgspeed FROM freqlog WHERE word=?", (word,))
        if res:
            return WordMetadata(word, res[0], datetime.fromtimestamp(res[1]), timedelta(seconds=res[2]))
        else:
            raise KeyError(f"Word '{word}' not found")

    def get_chord_metadata(self, chord: str) -> WordMetadata:
        """
        Get metadata for a chord
        :raises KeyError: if chord is not found
        """
        raise NotImplementedError  # TODO: implement

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a word entry, creating it if it doesn't exist"""
        try:
            freq, last_used, avg_time = self.get_word_metadata(word, CaseSensitivity.SENSITIVE)
            freq += 1
            avg_time = (avg_time * (freq - 1) + (end_time - start_time)) / freq
            self._execute("UPDATE freqlog SET frequency=?, lastused=?, avgspeed=? WHERE word=?",
                          (freq, end_time.timestamp(), avg_time.total_seconds(), word))
        except KeyError:
            self._execute("INSERT INTO freqlog VALUES (?, ?, ?, ?)",
                          (word, 1, end_time.timestamp(), (end_time - start_time).total_seconds()))

    def log_chord(self, word: str, start_time: datetime, end_time: datetime) -> None:
        raise NotImplementedError  # TODO: implement

    def check_banned(self, word: str, case: CaseSensitivity) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        raise NotImplementedError  # TODO: implement

    def ban_word(self, word: str, case: CaseSensitivity) -> None:
        """Delete a word entry and add it to the ban list"""
        self._execute("DELETE FROM freqlog WHERE word=?", (word,))
        self._execute("INSERT INTO banlist VALUES (?)", (word,))
        # TODO: implement case sensitivity

    def unban_word(self, word: str, case: CaseSensitivity) -> None:
        """Remove a word from the ban list"""
        raise NotImplementedError  # TODO: implement

    def list_words(self, limit: int, sort_by: WordMetadataAttr,
                   reverse: bool, case: CaseSensitivity) -> set[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """

    def list_chords(self, limit: int, sort_by: ChordMetadataAttr,
                    reverse: bool, case: CaseSensitivity) -> set[ChordMetadata]:
        """
        List chords in the store
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        """
        raise NotImplementedError  # TODO: implement

    def list_banned_words(self, limit: int, sort_by: BanlistAttr, reverse: bool) -> list[Banlist]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        """
        raise NotImplementedError  # TODO: implement

    def cleanup(self):
        self.conn.close()
