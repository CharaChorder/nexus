import sqlite3
from datetime import datetime, timedelta

from nexus.Freqlog.backends.Backend import Backend
from nexus.Freqlog.Definitions import Banlist, BanlistAttr, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    WordMetadata, WordMetadataAttr


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

    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata | None:
        """
        Get metadata for a word
        :returns: WordMetadata if word is found, None otherwise
        """
        # TODO: Handle case sensitivity
        res = self._fetchone("SELECT frequency, lastused, avgspeed FROM freqlog WHERE word=?", (word,))
        return WordMetadata(word, res[0], datetime.fromtimestamp(res[1]), timedelta(seconds=res[2])) if res else None

    def get_chord_metadata(self, chord: str) -> ChordMetadata | None:
        """
        Get metadata for a chord
        :returns: ChordMetadata if chord is found, None otherwise
        """
        raise NotImplementedError  # TODO: implement

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a word entry, creating it if it doesn't exist"""
        metadata = self.get_word_metadata(word, CaseSensitivity.SENSITIVE)
        if metadata:
            freq, last_used, avg_speed = metadata.frequency, max(metadata.last_used, end_time), metadata.average_speed
            freq += 1
            avg_speed = (avg_speed * (freq - 1) + (end_time - start_time)) / freq
            self._execute("UPDATE freqlog SET frequency=?, lastused=?, avgspeed=? WHERE word=?",
                          (freq, last_used.timestamp(), avg_speed.total_seconds(), word))
        else:
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
                   reverse: bool, case: CaseSensitivity) -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        :raises ValueError: if sort_by is invalid
        """
        sql_sort_by: str  # WARNING: Will be loaded into SQL query, do not use user input
        match sort_by:
            case WordMetadataAttr.WORD:
                sql_sort_by = "word"
            case WordMetadataAttr.FREQUENCY:
                sql_sort_by = "frequency"
            case WordMetadataAttr.LAST_USED:
                sql_sort_by = "lastused"
            case WordMetadataAttr.AVERAGE_SPEED:
                sql_sort_by = "avgspeed"
            case _:
                raise ValueError(f"Invalid sort_by value: {sort_by}")
        if reverse:
            sql_sort_by += " DESC"
        res = self._fetchall(f"SELECT word, frequency, lastused, avgspeed FROM freqlog ORDER BY {sql_sort_by} LIMIT ?",
                             (limit,))
        return [WordMetadata(r[0], r[1], datetime.fromtimestamp(r[2]), timedelta(seconds=r[3])) for r in res]

    def list_chords(self, limit: int, sort_by: ChordMetadataAttr,
                    reverse: bool, case: CaseSensitivity) -> list[ChordMetadata]:
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

    def close(self):
        """Close the database connection"""
        self.cursor.close()
        self.conn.close()
