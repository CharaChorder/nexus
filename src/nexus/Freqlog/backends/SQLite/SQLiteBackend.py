import sqlite3
from datetime import datetime, timedelta

from nexus import __version__
from nexus.Freqlog.backends.Backend import Backend
from nexus.Freqlog.Definitions import BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, ChordMetadataAttr, \
    WordMetadata, WordMetadataAttr

# WARNING: Loaded into SQL query, do not use unsanitized user input
SQL_SELECT_STAR_FROM_FREQLOG = "SELECT word, frequency, lastused, avgspeed FROM freqlog"


class SQLiteBackend(Backend):

    def __init__(self, db_path: str) -> None:
        """
        Initialize the SQLite backend
        :param db_path: Path to the database file
        :raises ValueError: If the database version is newer than the current version
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Versioning
        old_version = self._fetchone("PRAGMA user_version")[0]

        # Encode major, minor and patch version into a single 4-byte integer
        sql_version: int = int(__version__.split(".")[0]) << 16 | int(__version__.split(".")[1]) << 8 | int(
            __version__.split(".")[2])
        if old_version < sql_version:
            self._upgrade_database(sql_version)
        elif old_version > sql_version:
            raise ValueError(f"Database version {old_version} is newer than the current version {sql_version}")

        self._execute(f"PRAGMA user_version = {sql_version}")

        # Freqloq table
        self._execute("CREATE TABLE IF NOT EXISTS freqlog (word TEXT NOT NULL PRIMARY KEY, frequency INTEGER, "
                      "lastused timestamp NOT NULL, avgspeed REAL NOT NULL) WITHOUT ROWID")
        self._execute("CREATE INDEX IF NOT EXISTS freqlog_lower ON freqlog(word COLLATE NOCASE)")
        self._execute("CREATE INDEX IF NOT EXISTS freqlog_frequency ON freqlog(frequency)")
        self._execute("CREATE UNIQUE INDEX IF NOT EXISTS freqlog_lastused ON freqlog(lastused)")
        self._execute("CREATE INDEX IF NOT EXISTS freqlog_avgspeed ON freqlog(avgspeed)")

        # Banlist table
        self._execute(
            "CREATE TABLE IF NOT EXISTS banlist (word TEXT PRIMARY KEY, dateadded timestamp NOT NULL) WITHOUT ROWID")
        self._execute("CREATE INDEX IF NOT EXISTS banlist_dateadded ON banlist(dateadded)")
        self._execute("CREATE TABLE IF NOT EXISTS banlist_lower (word TEXT PRIMARY KEY COLLATE NOCASE,"
                      "dateadded timestamp NOT NULL) WITHOUT ROWID")

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

    def _upgrade_database(self, sql_version: int) -> None:
        """Upgrade database to current version"""
        # TODO: populate this function when changing DDL
        # Remember to warn users to back up their database before upgrading
        pass

    def get_word_metadata(self, word: str, case: CaseSensitivity) -> WordMetadata | None:
        """
        Get metadata for a word
        :returns: WordMetadata if word is found, None otherwise
        """
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                res = self._fetchall(f"{SQL_SELECT_STAR_FROM_FREQLOG} WHERE word = ? COLLATE NOCASE", (word,))
                word_metadata = None
                for row in res:
                    if word_metadata is None:
                        word_metadata = WordMetadata(word, row[1], datetime.fromtimestamp(row[2]),
                                                     timedelta(seconds=row[3]))
                    else:
                        word_metadata |= WordMetadata(word, row[1], datetime.fromtimestamp(row[2]),
                                                      timedelta(seconds=row[3]))
                return word_metadata
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                res_u = self._fetchone(f"{SQL_SELECT_STAR_FROM_FREQLOG} WHERE word=?", (word_u,))
                res_l = self._fetchone(f"{SQL_SELECT_STAR_FROM_FREQLOG} WHERE word=?", (word_l,))
                word_meta_u = WordMetadata(word, res_u[1], datetime.fromtimestamp(res_u[2]),
                                           timedelta(seconds=res_u[3])) if res_u else None
                word_meta_l = WordMetadata(word, res_l[1], datetime.fromtimestamp(res_l[2]),
                                           timedelta(seconds=res_l[3])) if res_l else None
                if not word_meta_u:
                    return word_meta_l
                return word_meta_u | word_meta_l
            case CaseSensitivity.SENSITIVE:
                res = self._fetchone(f"{SQL_SELECT_STAR_FROM_FREQLOG} WHERE word=?", (word,))
                return WordMetadata(word, res[1], datetime.fromtimestamp(res[2]),
                                    timedelta(seconds=res[3])) if res else None

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
            metadata |= WordMetadata(word, 1, end_time, end_time - start_time)
            self._execute("UPDATE freqlog SET frequency=?, lastused=?, avgspeed=? WHERE word=?",
                          (metadata.frequency, metadata.last_used.timestamp(), metadata.average_speed.total_seconds(),
                           word))
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
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                res = self._fetchone("SELECT word FROM banlist WHERE word = ? COLLATE NOCASE", (word,))
                res_l = self._fetchone("SELECT word FROM banlist_lower WHERE word = ?", (word,))
                return res is not None or res_l is not None
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                res_u = self._fetchone("SELECT word FROM banlist WHERE word=?", (word_u,))
                res_l = self._fetchone("SELECT word FROM banlist WHERE word=?", (word_l,))
                return res_u is not None or res_l is not None
            case CaseSensitivity.SENSITIVE:
                res = self._fetchone("SELECT word FROM banlist WHERE word=?", (word,))
                return res is not None

    def ban_word(self, word: str, case: CaseSensitivity, time: datetime) -> bool:
        """
        Delete a word entry and add it to the ban list
        :returns: True if word was banned, False if it was already banned
        """
        if self.check_banned(word, case):
            return False  # already banned
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                self._execute("DELETE FROM freqlog WHERE word = ? COLLATE NOCASE", (word,))
                self._execute("INSERT OR IGNORE INTO banlist VALUES (?, ?)", (word, time.timestamp()))
                self._execute("INSERT OR IGNORE INTO banlist_lower VALUES (?, ?)", (word, time.timestamp()))
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                self._execute("DELETE FROM freqlog WHERE word=?", (word_u,))
                self._execute("DELETE FROM freqlog WHERE word=?", (word_l,))
                self._execute("INSERT OR IGNORE INTO banlist VALUES (?, ?)", (word_u, time.timestamp()))
                self._execute("INSERT OR IGNORE INTO banlist VALUES (?, ?)", (word_l, time.timestamp()))
            case CaseSensitivity.SENSITIVE:
                self._execute("DELETE FROM freqlog WHERE word=?", (word,))
                self._execute("INSERT OR IGNORE INTO banlist VALUES (?, ?)", (word, time.timestamp()))
        return True

    def unban_word(self, word: str, case: CaseSensitivity) -> bool:
        """
        Remove a word from the ban list
        :returns: True if word was unbanned, False if it was already not banned
        """
        if not self.check_banned(word, case):
            return False  # not banned
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                self._execute("DELETE FROM banlist WHERE word = ? COLLATE NOCASE", (word,))
                self._execute("DELETE FROM banlist_lower WHERE word = ? COLLATE NOCASE", (word,))
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                self._execute("DELETE FROM banlist WHERE word=?", (word_u,))
                self._execute("DELETE FROM banlist WHERE word=?", (word_l,))
            case CaseSensitivity.SENSITIVE:
                self._execute("DELETE FROM banlist WHERE word=?", (word,))
        return True

    def list_words(self, limit: int = -1, sort_by: WordMetadataAttr = WordMetadataAttr.word,
                   reverse: bool = False, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> list[WordMetadata]:
        """
        List words in the store
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed, score
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        :raises ValueError: if sort_by is invalid
        """
        if case == CaseSensitivity.SENSITIVE:
            sql_sort_limit: str = sort_by.value  # WARNING: Loaded into SQL query, do not use unsanitized user input
            if reverse:
                sql_sort_limit += " DESC"
            if limit > 0:
                sql_sort_limit += f" LIMIT {limit}"
            res = self._fetchall(f"{SQL_SELECT_STAR_FROM_FREQLOG} ORDER BY {sql_sort_limit}")
            return [WordMetadata(row[0], row[1], datetime.fromtimestamp(row[2]), timedelta(seconds=row[3]))
                    for row in res]
        res = self._fetchall(SQL_SELECT_STAR_FROM_FREQLOG)
        d: dict[WordMetadata] = {}
        for row in res:
            word = row[0][0].lower() + row[0][1:] if case == CaseSensitivity.FIRST_CHAR else row[0].lower()
            word_metadata = WordMetadata(word, row[1], datetime.fromtimestamp(row[2]), timedelta(seconds=row[3]))
            try:
                d[word] |= word_metadata
            except KeyError:
                d[word] = word_metadata
        ret = sorted(list(d.values()), key=lambda x: getattr(x, sort_by.name), reverse=reverse)
        return ret[:limit] if limit > 0 else ret

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

    def list_banned_words(self, limit: int, sort_by: BanlistAttr, reverse: bool) \
            -> tuple[set[BanlistEntry], set[BanlistEntry]]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        :returns: Tuple of (banned words with case, banned words without case)
        """
        if reverse:
            sql_sort_limit = f"{sort_by.value} DESC"
        else:
            sql_sort_limit = sort_by.value
        if limit > 0:
            sql_sort_limit += f" LIMIT {limit}"
        res = self._fetchall(f"SELECT * FROM banlist ORDER BY {sql_sort_limit}")
        res_lower = self._fetchall(f"SELECT * FROM banlist_lower ORDER BY {sql_sort_limit}")
        return {BanlistEntry(row[0], datetime.fromtimestamp(row[1])) for row in res}, \
            {BanlistEntry(row[0], datetime.fromtimestamp(row[1])) for row in res_lower}

    def close(self) -> None:
        """Close the database connection"""
        self.cursor.close()
        self.conn.close()
