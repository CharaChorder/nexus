import sqlite3
from datetime import datetime, timedelta

from Freqlog.backends.Backend import Backend


class SQLiteBackend(Backend):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._execute("CREATE TABLE IF NOT EXISTS freqlog"
                      "(word TEXT PRIMARY KEY, frequency INTEGER, lastused timestamp, avgtime REAL)")
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

    def get_word_metadata(self, word: str) -> (int, datetime, timedelta):
        """
        Get metadata for a word
        :raises KeyError: if word is not found
        :returns: (frequency, last_used, average_speed)
        """
        res = self._fetchone("SELECT frequency, lastused, avgtime FROM freqlog WHERE word=?", (word,))
        if res:
            return res[0], datetime.fromtimestamp(res[1]), timedelta(seconds=res[2])
        else:
            raise KeyError(f"Word '{word}' not found")

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> None:
        """Log a word entry, creating it if it doesn't exist"""
        try:
            freq, last_used, avg_time = self.get_word_metadata(word)
            freq += 1
            avg_time = (avg_time * (freq - 1) + (end_time - start_time)) / freq
            self._execute("UPDATE freqlog SET frequency=?, lastused=?, avgtime=? WHERE word=?",
                          (freq, end_time.timestamp(), avg_time.total_seconds(), word))
        except KeyError:
            self._execute("INSERT INTO freqlog VALUES (?, ?, ?, ?)",
                          (word, 1, end_time.timestamp(), (end_time - start_time).total_seconds()))

    def check_banned(self, word: str) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        res = self._fetchone("SELECT word FROM banlist WHERE word=?", (word,))
        return res is not None

    def ban_word(self, word: str) -> None:
        """
        Delete a word entry and add it to the ban list
        """
        self._execute("DELETE FROM freqlog WHERE word=?", (word,))
        self._execute("INSERT INTO banlist VALUES (?)", (word,))

    def unban_word(self, word: str) -> None:
        """
        Remove a word from the ban list
        """
        self._execute("DELETE FROM banlist WHERE word=?", (word,))

    def list_all_words(self) -> list[(str, int, datetime, timedelta)]:
        """
        List all words in the database
        :returns: list of (word, frequency, last_used, average_speed)
        """
        return [(res[0], res[1], datetime.fromtimestamp(res[2]), timedelta(seconds=res[3]))
                for res in self._fetchall("SELECT * FROM freqlog")]

    def list_banned_words(self) -> list[str]:
        """
        List all banned words
        :returns: list of banned words
        """
        return [res[0] for res in self._fetchall("SELECT * FROM banlist")]

    def cleanup(self):
        self.conn.close()
