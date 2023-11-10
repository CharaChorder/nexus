import logging
import os
import sqlite3
from datetime import datetime, timedelta
from sqlite3 import Cursor

from nexus import __version__
from nexus.Freqlog.backends.Backend import Backend
from nexus.Freqlog.Definitions import Age, BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, \
    ChordMetadataAttr, WordMetadata, WordMetadataAttr

# WARNING: Directly loaded into SQL query, do not use unsanitized user input
SQL_SELECT_STAR_FROM_FREQLOG = "SELECT word, frequency, lastused, avgspeed FROM freqlog"
SQL_SELECT_STAR_FROM_CHORDLOG = "SELECT chord, frequency, lastused FROM chordlog"
SQL_SELECT_STAR_FROM_BANLIST = "SELECT word, dateadded FROM banlist"


class SQLiteBackend(Backend):

    @staticmethod
    def encode_version(version: str) -> int:
        return int(version.split(".")[0]) << 16 | int(version.split(".")[1]) << 8 | int(version.split(".")[2])

    @staticmethod
    def decode_version(version: int) -> str:
        return f"{version >> 16}.{version >> 8 & 0xFF}.{version & 0xFF}"

    @staticmethod
    def _init_db(cursor: Cursor, sql_version: int):
        """
        Initialize the database
        """
        # WARNING: Remember to bump version and change _upgrade_database and merge_db when changing DDL
        cursor.execute(f"PRAGMA user_version = {sql_version}")

        # Freqloq table
        cursor.execute("CREATE TABLE IF NOT EXISTS freqlog (word TEXT NOT NULL PRIMARY KEY, frequency INTEGER, "
                       "lastused timestamp NOT NULL, avgspeed REAL NOT NULL) WITHOUT ROWID")
        cursor.execute("CREATE INDEX IF NOT EXISTS freqlog_lower ON freqlog(word COLLATE NOCASE)")
        cursor.execute("CREATE INDEX IF NOT EXISTS freqlog_frequency ON freqlog(frequency)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS freqlog_lastused ON freqlog(lastused)")
        cursor.execute("CREATE INDEX IF NOT EXISTS freqlog_avgspeed ON freqlog(avgspeed)")

        # Chordlog table
        cursor.execute("CREATE TABLE IF NOT EXISTS chordlog (chord TEXT NOT NULL PRIMARY KEY, frequency INTEGER, "
                       "lastused timestamp NOT NULL) WITHOUT ROWID")
        cursor.execute("CREATE INDEX IF NOT EXISTS chordlog_frequency ON chordlog(frequency)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS chordlog_lastused ON chordlog(lastused)")

        # Banlist table
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS banlist (word TEXT PRIMARY KEY, dateadded timestamp NOT NULL) WITHOUT ROWID")
        cursor.execute("CREATE INDEX IF NOT EXISTS banlist_dateadded ON banlist(dateadded)")
        cursor.execute("CREATE TABLE IF NOT EXISTS banlist_lower (word TEXT PRIMARY KEY COLLATE NOCASE,"
                       "dateadded timestamp NOT NULL) WITHOUT ROWID")

    def __init__(self, db_path: str, upgrade_callback: callable = None) -> None:
        """
        Initialize the SQLite backend
        :param db_path: Path to the database file
        :param upgrade_callback: Callback to call when upgrading the database.
                Should take one argument: the new version, and call sys.exit() if an upgrade is unwanted
        :raises ValueError: If the database version is newer than the current version
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.upgrade_callback = upgrade_callback

        # Versioning
        old_version = self._fetchone("PRAGMA user_version")[0]

        # Encode major, minor and patch version into a single 4-byte integer
        sql_version: int = self.encode_version(__version__)
        if old_version < sql_version:
            self._upgrade_database(sql_version)
        elif old_version > sql_version:
            raise ValueError(
                f"Database version {self.decode_version(old_version)} is newer than the current version {__version__}")

        self._init_db(self.cursor, sql_version)

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
        """
        Upgrade database to current version
        :param sql_version: New database version
        """
        if self.upgrade_callback:
            self.upgrade_callback(self.decode_version(sql_version))
        logging.warning(f"Upgrading database from {self.decode_version(self._fetchone('PRAGMA user_version')[0])} to "
                        f"{self.decode_version(sql_version)}")

        # TODO: populate this function when changing DDL

    def get_version(self) -> str:
        """Get the version of the database"""
        return self.decode_version(self._fetchone("PRAGMA user_version")[0])

    def set_version(self, version: str) -> None:
        """Set database version to a specific version"""
        self._execute(f"PRAGMA user_version = {self.encode_version(version)}")

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
                    else:  # Combine (or) same word with different casing
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
                if not word_meta_u:  # first operand in or must not be None
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
        res = self._fetchone(f"{SQL_SELECT_STAR_FROM_CHORDLOG} WHERE chord=?", (chord,))
        return ChordMetadata(res[0], res[1], datetime.fromtimestamp(res[2])) if res else None

    def get_banlist_entry(self, word: str, case: CaseSensitivity) -> BanlistEntry | None:
        """
        Get a banlist entry
        :param word: Word to get entry for
        :param case: Case sensitivity
        :return: BanlistEntry if word is banned for the specified case, None otherwise
        """
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                res = self._fetchone(f"{SQL_SELECT_STAR_FROM_BANLIST}_lower WHERE word = ? COLLATE NOCASE", (word,))
                return BanlistEntry(res[0], datetime.fromtimestamp(res[1])) if res else None
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                res_u = self._fetchone(f"{SQL_SELECT_STAR_FROM_BANLIST} WHERE word=?", (word_u,))
                res_l = self._fetchone(f"{SQL_SELECT_STAR_FROM_BANLIST} WHERE word=?", (word_l,))
                if res_u and res_l:
                    return BanlistEntry(res_l[0], datetime.fromtimestamp(res_l[1]))
                return None  # if only one or none are banned
            case CaseSensitivity.SENSITIVE:
                res = self._fetchone(f"{SQL_SELECT_STAR_FROM_BANLIST} WHERE word=?", (word,))
                return BanlistEntry(res[0], datetime.fromtimestamp(res[1])) if res else None

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Log a word entry if not banned, creating it if it doesn't exist
        :param word: Word to log
        :param start_time: Timestamp of start of word started
        :param end_time: Timestamp of end of word
        :returns: True if word was logged, False if it was banned
        """
        if self.check_banned(word, CaseSensitivity.SENSITIVE):
            return False  # banned
        metadata = self.get_word_metadata(word, CaseSensitivity.SENSITIVE)
        if metadata:  # Use or operator to combine metadata with existing entry
            metadata |= WordMetadata(word, 1, end_time, end_time - start_time)
            self._execute("UPDATE freqlog SET frequency=?, lastused=?, avgspeed=? WHERE word=?",
                          (metadata.frequency, metadata.last_used.timestamp(), metadata.average_speed.total_seconds(),
                           word))
        else:  # New entry
            self._execute("INSERT INTO freqlog VALUES (?, ?, ?, ?)",
                          (word, 1, end_time.timestamp(), (end_time - start_time).total_seconds()))
        return True

    def _insert_word(self, word: str, frequency: int, last_used: datetime, average_speed: timedelta) -> None:
        """Insert a word entry"""
        self._execute("INSERT INTO freqlog VALUES (?, ?, ?, ?)",
                      (word, frequency, last_used.timestamp(), average_speed.total_seconds()))

    def _insert_chord(self, chord, frequency, last_used):
        """Insert a chord entry"""
        self._execute("INSERT INTO chordlog VALUES (?, ?, ?)", (chord, frequency, last_used.timestamp()))

    def log_chord(self, chord: str, end_time: datetime) -> bool:
        """
        Log a chord entry if not banned, creating it if it doesn't exist
        :param chord: Chord to log
        :param end_time: Timestamp of end of chord
        :returns: True if chord was logged, False if it was banned
        """
        if self.check_banned(chord, CaseSensitivity.SENSITIVE):
            return False  # banned
        metadata = self.get_chord_metadata(chord)
        if metadata:  # Use or operator to combine metadata with existing entry
            metadata |= ChordMetadata(chord, 1, end_time)
            self._execute("UPDATE chordlog SET frequency=?, lastused=? WHERE chord=?",
                          (metadata.frequency, metadata.last_used.timestamp(), chord))
        else:  # New entry
            self._execute("INSERT INTO chordlog VALUES (?, ?, ?)", (chord, 1, end_time.timestamp()))
        return True

    def check_banned(self, word: str, case: CaseSensitivity) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        match case:
            case CaseSensitivity.INSENSITIVE:  # Only banned insensitively
                word = word.lower()
                res = self._fetchone("SELECT word FROM banlist_lower WHERE word = ?", (word,))
                return res is not None
            case CaseSensitivity.FIRST_CHAR:  # Banned insensitively or by first char
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                res_u = self._fetchone("SELECT word FROM banlist WHERE word=?", (word_u,))
                res_l = self._fetchone("SELECT word FROM banlist WHERE word=?", (word_l,))
                res = self._fetchone("SELECT word FROM banlist_lower WHERE word = ?", (word,))
                return res is not None or (res_u is not None and res_l is not None)
            case CaseSensitivity.SENSITIVE:  # Banned insensitively or sensitively
                res = self._fetchone("SELECT word FROM banlist WHERE word=?", (word,))
                res_lower = self._fetchone("SELECT word FROM banlist_lower WHERE word = ?", (word,))
                return res is not None or res_lower is not None

    def ban_word(self, word: str, case: CaseSensitivity, time: datetime) -> bool:
        """
        Delete a word/chord entry and add it to the ban list
        :returns: True if word was banned, False if it was already banned
        """
        if self.check_banned(word, case):
            return False  # already banned

        # Freqlog
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                self._execute("DELETE FROM freqlog WHERE word = ? COLLATE NOCASE", (word,))
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

        # Chordlog
        self._execute("DELETE FROM chordlog WHERE chord=?", (word,))
        return True

    def delete_word(self, word: str, case: CaseSensitivity) -> bool:
        """
        Delete a word/chord entry
        :returns: True if word was deleted, False if it's not in the database
        """
        if not self.get_word_metadata(word, case):
            return False
        match case:
            case CaseSensitivity.INSENSITIVE:
                word = word.lower()
                self._execute("DELETE FROM freqlog WHERE word = ? COLLATE NOCASE", (word,))
            case CaseSensitivity.FIRST_CHAR:
                word_u = word[0].upper() + word[1:]
                word_l = word[0].lower() + word[1:]
                self._execute("DELETE FROM freqlog WHERE word=?", (word_u,))
                self._execute("DELETE FROM freqlog WHERE word=?", (word_l,))
            case CaseSensitivity.SENSITIVE:
                self._execute("DELETE FROM freqlog WHERE word=?", (word,))
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

    def num_words(self, case: CaseSensitivity = CaseSensitivity.INSENSITIVE) -> int:
        """
        Get number of words in db
        :param case: Case sensitivity
        :return: Number of words in db
        """
        match case:
            case CaseSensitivity.SENSITIVE:
                return self._fetchone("SELECT COUNT(*) FROM freqlog")[0]
            case CaseSensitivity.INSENSITIVE:
                return len({row[0].lower() for row in self._fetchall("SELECT word FROM freqlog")})
            case CaseSensitivity.FIRST_CHAR:
                return len({row[0][0].lower() + row[0][1:] for row in self._fetchall("SELECT word FROM freqlog")})

    def list_words(self, limit: int = -1, sort_by: WordMetadataAttr = WordMetadataAttr.score, reverse: bool = True,
                   case: CaseSensitivity = CaseSensitivity.INSENSITIVE, search: str = "") -> list[WordMetadata]:
        """
        List words in the db
        :param limit: Maximum number of words to return
        :param sort_by: Attribute to sort by: word, frequency, last_used, average_speed, score
        :param reverse: Reverse sort order
        :param case: Case sensitivity
        :param search: Part of word to search for
        """
        sql_search = f" WHERE word LIKE '%{search}%'" if search else ""
        if case == CaseSensitivity.SENSITIVE:
            # WARNING: Directly loaded into SQL query, do not use unsanitized user input
            sql_sort_limit: str = sort_by.value
            if reverse:
                sql_sort_limit += " DESC"
            if limit > 0:
                sql_sort_limit += f" LIMIT {limit}"
            if sort_by == WordMetadataAttr.score:  # Score is not a column in the database
                res = self._fetchall(
                    f"{SQL_SELECT_STAR_FROM_FREQLOG}{sql_search}")
                ret = sorted([WordMetadata(row[0], row[1], datetime.fromtimestamp(row[2]), timedelta(seconds=row[3]))
                              for row in res], key=lambda x: x.score, reverse=reverse)
                return ret[:limit] if limit > 0 else ret

            # Valid sort_by column
            res = self._fetchall(f"{SQL_SELECT_STAR_FROM_FREQLOG}{sql_search}{f' LIMIT {limit}' if limit > 0 else ''}"
                                 f" ORDER BY {sql_sort_limit}")
            return [WordMetadata(row[0], row[1], datetime.fromtimestamp(row[2]), timedelta(seconds=row[3]))
                    for row in res]

        # Case INSENSITIVE or FIRST_CHAR
        res = self._fetchall(SQL_SELECT_STAR_FROM_FREQLOG + sql_search)
        d: dict[WordMetadata] = {}
        for row in res:
            word = row[0]
            word = word[0].lower() + word[1:] if case == CaseSensitivity.FIRST_CHAR else word.lower()  # un-case
            word_metadata = WordMetadata(word, row[1], datetime.fromtimestamp(row[2]), timedelta(seconds=row[3]))
            try:  # Combine (or) same word with different casing
                d[word] |= word_metadata
            except KeyError:  # New word
                d[word] = word_metadata
        ret = sorted(list(d.values()), key=lambda x: getattr(x, sort_by.name), reverse=reverse)
        return ret[:limit] if limit > 0 else ret

    def num_chords(self):
        """Get number of chords in db"""
        return self._fetchone("SELECT COUNT(*) FROM chordlog")[0]

    def list_chords(self, limit: int = -1, sort_by: ChordMetadataAttr = ChordMetadataAttr.score, reverse: bool = True,
                    search: str = "") -> list[ChordMetadata]:
        """
        List chords in the db
        :param limit: Maximum number of chords to return
        :param sort_by: Attribute to sort by: chord, frequency, last_used, average_speed
        :param reverse: Reverse sort order
        :param search: Part of chord to search for
        """
        sql_search = f" WHERE chord LIKE '%{search}%'" if search else ""
        sql_sort_limit = sort_by.value
        if reverse:
            sql_sort_limit += " DESC"
        if limit > 0:
            sql_sort_limit += f" LIMIT {limit}"
        if sort_by == ChordMetadataAttr.score:  # Score is not a column in the database
            res = self._fetchall(
                f"{SQL_SELECT_STAR_FROM_CHORDLOG}{sql_search}")
            ret = sorted([ChordMetadata(row[0], row[1], datetime.fromtimestamp(row[2])) for row in res],
                         key=lambda x: x.score, reverse=reverse)
            return ret[:limit] if limit > 0 else ret

        # Valid sort_by column
        res = self._fetchall(f"{SQL_SELECT_STAR_FROM_CHORDLOG}{sql_search}{f' LIMIT {limit}' if limit > 0 else ''}"
                             f" ORDER BY {sql_sort_limit}")
        return [ChordMetadata(row[0], row[1], datetime.fromtimestamp(row[2])) for row in res]

    def delete_chord(self, chord: str) -> bool:
        """
        Delete a chord entry
        :returns: True if chord was deleted, False if it's not in the database
        """
        if not self.get_chord_metadata(chord):
            return False
        self._execute("DELETE FROM chordlog WHERE chord=?", (chord,))
        return True

    def list_banned_words(self, limit: int, sort_by: BanlistAttr,
                          reverse: bool) -> tuple[set[BanlistEntry], set[BanlistEntry]]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word
        :param reverse: Reverse sort order
        :returns: Tuple of (banned words with case, banned words without case)
        """
        sql_sort_limit = sort_by.value
        if reverse:
            sql_sort_limit += " DESC"
        if limit > 0:
            sql_sort_limit += f" LIMIT {limit}"
        res = self._fetchall(f"{SQL_SELECT_STAR_FROM_BANLIST} ORDER BY {sql_sort_limit}")
        res_lower = self._fetchall(f"{SQL_SELECT_STAR_FROM_BANLIST}_lower ORDER BY {sql_sort_limit}")
        return {BanlistEntry(row[0], datetime.fromtimestamp(row[1])) for row in res}, \
            {BanlistEntry(row[0], datetime.fromtimestamp(row[1])) for row in res_lower}

    def merge_backend(self, src_db_path: str, dst_db_path: str, ban_date: Age) -> None:
        """
        Merge another database and this one into a new database
        :param src_db_path: Path to the source database
        :param dst_db_path: Path to the destination database
        :param ban_date: Whether to use older or newer date banned for banlist entries of the same word (OLDER or NEWER)
        :requires: src_db_path != dst_db_path != self.db_path
        :requires: src_db_path must be a valid Freqlog database and readable
        :requires: dst_db_path must not be an existing file but must be writable
        :raises ValueError: If requirements are not met
        """
        # Assert requirements
        if src_db_path == dst_db_path:
            raise ValueError("src_db_path and dst_db_path must be different")
        if src_db_path == self.db_path:
            raise ValueError("src_db_path and self.db_path must be different")
        if dst_db_path == self.db_path:
            raise ValueError("dst_db_path and self.db_path must be different")
        if os.path.isfile(dst_db_path):
            raise ValueError("dst_db_path must not be an existing file")
        try:  # ensure that src is writable (WARNING: Must use 'a' instead of 'w' mode to avoid erasing file!!!)
            with open(src_db_path, "a"):
                pass
        except OSError as e:
            raise ValueError("src_db_path must be writable") from e
        try:
            with open(dst_db_path, "w"):
                pass
        except OSError as e:
            raise ValueError("dst_db_path must be writable") from e

        # DB meta
        src_db = SQLiteBackend(src_db_path, self.upgrade_callback)
        dst_db = SQLiteBackend(dst_db_path)

        # Merge databases
        # TODO: optimize this/add progress bars (this takes a long time)
        try:
            # Merge banlist
            logging.info("Merging banlist")
            src_banned_words_cased, src_banned_words_uncased = src_db.list_banned_words(0, BanlistAttr.word, False)
            banned_words_cased, banned_words_uncased = self.list_banned_words(0, BanlistAttr.word, False)

            # Ban words from self banlist in dst db
            for entry in banned_words_cased:
                dst_db.ban_word(entry.word, CaseSensitivity.SENSITIVE, entry.date_added)
            for entry in banned_words_uncased:
                dst_db.ban_word(entry.word, CaseSensitivity.INSENSITIVE, entry.date_added)

            # Ban words from src banlist in dst db
            for entry in src_banned_words_cased:
                dst_entry = dst_db.get_banlist_entry(entry.word, CaseSensitivity.SENSITIVE)
                if dst_entry and ((ban_date == Age.OLDER and entry.date_added < dst_entry.date_added) or
                                  (ban_date == Age.NEWER and entry.date_added > dst_entry.date_added)):
                    dst_db.unban_word(entry.word, CaseSensitivity.SENSITIVE)
                    dst_db.ban_word(entry.word, CaseSensitivity.SENSITIVE, entry.date_added)
                else:
                    dst_db.ban_word(entry.word, CaseSensitivity.SENSITIVE, entry.date_added)
            for entry in src_banned_words_uncased:
                dst_entry = dst_db.get_banlist_entry(entry.word, CaseSensitivity.INSENSITIVE)
                if dst_entry and ((ban_date == Age.OLDER and entry.date_added < dst_entry.date_added) or
                                  (ban_date == Age.NEWER and entry.date_added > dst_entry.date_added)):
                    dst_db.unban_word(entry.word, CaseSensitivity.INSENSITIVE)
                    dst_db.ban_word(entry.word, CaseSensitivity.INSENSITIVE, entry.date_added)
                else:
                    dst_db.ban_word(entry.word, CaseSensitivity.INSENSITIVE, entry.date_added)

            # Merge freqlog
            logging.info("Merging freqlog")
            src_words = src_db.list_words(0, WordMetadataAttr.word, False, CaseSensitivity.SENSITIVE)
            words = [word.word for word in self.list_words(0, WordMetadataAttr.word, False, CaseSensitivity.SENSITIVE)]
            entries = self.list_words(0, WordMetadataAttr.word, False, CaseSensitivity.SENSITIVE)
            for src_word in src_words:
                if src_word.word in words:
                    entries[words.index(src_word.word)] |= src_word
                else:
                    entries.append(src_word)
            for word in entries:
                dst_db._insert_word(word.word, word.frequency, word.last_used, word.average_speed)

            # Merge chordlog
            logging.info("Merging chordlog")
            src_chords = src_db.list_chords(0, ChordMetadataAttr.chord, False, "")
            chords = [chord.chord for chord in self.list_chords(0, ChordMetadataAttr.chord, False, "")]
            entries = self.list_chords(0, ChordMetadataAttr.chord, False, "")
            for src_chord in src_chords:
                if src_chord.chord in chords:
                    entries[chords.index(src_chord.chord)] |= src_chord
                else:
                    entries.append(src_chord)
            for chord in entries:
                dst_db._insert_chord(chord.chord, chord.frequency, chord.last_used)
        finally:  # Close databases
            src_db.close()
            dst_db.close()

    def close(self) -> None:
        """Close the database connection"""
        self.cursor.close()
        self.conn.close()
