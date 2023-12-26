import base64
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from sqlite3 import Cursor

import cryptography.fernet as cryptography
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from nexus import __version__
from nexus.Freqlog.backends.Backend import Backend
from nexus.Freqlog.Definitions import Age, BanlistAttr, BanlistEntry, CaseSensitivity, ChordMetadata, \
    ChordMetadataAttr, WordMetadata, WordMetadataAttr
from nexus.Version import Version

# WARNING: Directly loaded into SQL query, do not use unsanitized user input
SQL_SELECT_STAR_FROM_FREQLOG = "SELECT word, frequency, lastused, avgspeed FROM freqlog"
SQL_SELECT_STAR_FROM_CHORDLOG = "SELECT chord, frequency, lastused FROM chordlog"
SQL_SELECT_STAR_FROM_BANLIST = "SELECT word, dateadded FROM banlist"


class SQLiteBackend(Backend):

    @staticmethod
    def _init_db(cursor: Cursor, version: Version):
        """
        Initialize the database
        """
        # WARNING: Remember to bump version and change _upgrade_database and merge_db when changing DDL
        cursor.execute(f"PRAGMA user_version = {int(version)}")

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
        cursor.execute("CREATE TABLE IF NOT EXISTS banlist (word TEXT PRIMARY KEY, dateadded timestamp NOT NULL) "
                       "WITHOUT ROWID")
        cursor.execute("CREATE INDEX IF NOT EXISTS banlist_dateadded ON banlist(dateadded)")

        # Config table
        cursor.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID")

        # Add salt to settings table if it doesn't exist
        cursor.execute("INSERT OR IGNORE INTO config VALUES ('salt', ?)", (os.urandom(16),))

    @staticmethod
    def is_db_populated(db_path: str) -> bool:
        """
        Check if the database path is valid, and if the database file exists
        :param db_path: Path to the database file
        :raises ValueError: If the database path is empty
        :raises PermissionError: If the database path is not readable or writable
        :raises IsADirectoryError: If the database path is not a file (because Python has no NotAFileError and
                                   we don't talk about specials and sockets)
        :returns: True if the database file exists, False otherwise
        """
        if not db_path:
            raise ValueError("Database path is empty")
        if db_path == ":memory:":
            return False  # in-memory database, needs to be False for db to be inited
        if os.path.exists(db_path):
            if not os.path.isfile(db_path):
                raise IsADirectoryError(f"Database path {db_path} is not a file")
            if not os.access(db_path, os.R_OK):
                raise PermissionError(f"Database path {db_path} is not readable")
            if not os.access(db_path, os.W_OK):
                raise PermissionError(f"Database path {db_path} is not writable")
            if os.stat(db_path).st_size == 0:  # Empty file
                return False
            tmp_conn = sqlite3.connect(db_path)
            if tmp_conn.cursor().execute("PRAGMA user_version").fetchone()[0] == 0:
                tmp_conn.close()
                return False
            tmp_conn.close()
            return True
        else:
            parent_dir = os.path.dirname(db_path) or os.curdir
            if not os.path.exists(parent_dir):
                raise FileNotFoundError(f"Database path {db_path} does not exist")
            if not os.access(parent_dir, os.W_OK):
                raise PermissionError(f"Database path {db_path} is not writable")
            return False

    def __init__(self, db_path: str, password_callback: callable, upgrade_callback: callable = None) -> None:
        """
        Initialize the SQLite backend
        :param db_path: Path to the database file
        :param password_callback: Callback to call to get password to encrypt/decrypt banlist entries
                Should take one argument: whether the password is being set for the first time
        :param upgrade_callback: Callback to call when upgrading the database.
                Should take one argument: the new version, and call sys.exit() if an upgrade is unwanted
        :raises ValueError: If the database version is newer than the current version
        :raises PermissionError: If the database path is not readable or writable
        :raises IsADirectoryError: If the database path is not a file
        :raises FileNotFoundError: If the database path does not exist
        :raises cryptography.fernet.InvalidToken: If the password is incorrect
        """
        self.db_path = db_path
        db_populated = self.is_db_populated(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.password_callback = password_callback
        self.upgrade_callback = upgrade_callback

        version = Version(__version__)

        # Declare before upgrading database (for v<0.5.0)
        self.salt: bytes | None = None
        self.fernet: Fernet | None = None
        self.password: str | None = None

        if db_populated:  # Versioning
            old_version = self.get_version()
            if old_version < version:
                self._upgrade_database(old_version)
            elif old_version > version:
                raise ValueError(f"Database version {old_version} is newer than the current version {version}")
            if self.password is None:  # Get password if not set
                self.password = self.password_callback(False)
        else:  # Populate database
            try:
                self._init_db(self.cursor, version)
                self.password = self.password_callback(True)
            except Exception:
                self.close()

                if self.db_path != ":memory:" and os.path.exists(self.db_path) is True:
                    # Delete database file as it was created
                    os.remove(self.db_path)
                raise

        # Fetch salt from config table and initialize Fernet for encryption/decryption using user-supplied password
        self.salt = self._fetchconfig("salt")
        self.fernet = Fernet(base64.urlsafe_b64encode(
            PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self.salt,
                       iterations=480000).derive(self.password.encode())))

        # Initialize password check if it doesn't exist
        self._execute("INSERT OR IGNORE INTO config VALUES ('check', ?)", (self.fernet.encrypt(self.salt),))

        # Check password
        if not self.check_password(self.password):
            raise cryptography.InvalidToken("Incorrect password")

        # Decrypt banlist
        self.banlist = [BanlistEntry(self.decrypt(row[0]), datetime.fromtimestamp(row[1])) for row in
                        self._fetchall(f"{SQL_SELECT_STAR_FROM_BANLIST}")]

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

    def _fetchconfig(self, key: str) -> str | bytes:
        return self._fetchone("SELECT value FROM config WHERE key = ?", (key,))[0]

    def encrypt(self, word: str) -> str:
        """Encrypt a word"""
        return self.fernet.encrypt(word.encode()).decode()

    def decrypt(self, word: str) -> str:
        """Decrypt a word"""
        return self.fernet.decrypt(word.encode()).decode()

    def _upgrade_database(self, old_version: Version) -> None:
        """
        Upgrade database to current version
        :param old_version: Existing database version
        """
        if self.upgrade_callback:
            self.upgrade_callback(old_version)
        logging.warning(f"Upgrading database from {old_version} to {Version(__version__)}")

        if old_version < '0.4.1':  # Restore first 4 tables
            # Freqloq table
            self._execute("CREATE TABLE IF NOT EXISTS freqlog (word TEXT NOT NULL PRIMARY KEY, frequency INTEGER, "
                          "lastused timestamp NOT NULL, avgspeed REAL NOT NULL) WITHOUT ROWID")
            self._execute("CREATE INDEX IF NOT EXISTS freqlog_lower ON freqlog(word COLLATE NOCASE)")
            self._execute("CREATE INDEX IF NOT EXISTS freqlog_frequency ON freqlog(frequency)")
            self._execute("CREATE UNIQUE INDEX IF NOT EXISTS freqlog_lastused ON freqlog(lastused)")
            self._execute("CREATE INDEX IF NOT EXISTS freqlog_avgspeed ON freqlog(avgspeed)")

            # Chordlog table
            self._execute("CREATE TABLE IF NOT EXISTS chordlog (chord TEXT NOT NULL PRIMARY KEY, frequency INTEGER, "
                          "lastused timestamp NOT NULL) WITHOUT ROWID")
            self._execute("CREATE INDEX IF NOT EXISTS chordlog_frequency ON chordlog(frequency)")
            self._execute("CREATE UNIQUE INDEX IF NOT EXISTS chordlog_lastused ON chordlog(lastused)")

            # Banlist tables
            self._execute("CREATE TABLE IF NOT EXISTS banlist (word TEXT PRIMARY KEY, dateadded timestamp NOT NULL) "
                          "WITHOUT ROWID")
            self._execute("CREATE INDEX IF NOT EXISTS banlist_dateadded ON banlist(dateadded)")
            self._execute("CREATE TABLE IF NOT EXISTS banlist_lower (word TEXT PRIMARY KEY COLLATE NOCASE, "
                          "dateadded timestamp NOT NULL) WITHOUT ROWID")

            # Bump version
            self.set_version(Version('0.4.1'))
        if old_version < '0.5.0':
            # Get password
            self.password = self.password_callback(True)

            # Merge data in banlist table into banlist_lower and drop banlist table
            self._execute("INSERT OR IGNORE INTO banlist_lower SELECT word, dateadded FROM banlist")

            # Drop old banlist table
            self._execute("DROP TABLE banlist")

            # Move banlist_lower table to banlist and encrypt entries
            # Read from banlist_lower
            res = self._fetchall("SELECT word, dateadded FROM banlist_lower")

            # Config table
            self._execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID")

            # Initialize Fernet for encryption/decryption using user-supplied password
            self.salt = os.urandom(16)
            self._execute("INSERT INTO config VALUES ('salt', ?)", (self.salt,))
            self.fernet = Fernet(base64.urlsafe_b64encode(
                PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self.salt,
                           iterations=480000).derive(self.password.encode())))

            # Encrypt and write to banlist
            self._execute("CREATE TABLE banlist (word TEXT PRIMARY KEY, dateadded timestamp NOT NULL)")
            for word, dateadded in res:
                self._execute("INSERT INTO banlist VALUES (?, ?)", (self.encrypt(word.lower()), dateadded))

            # Drop banlist_lower table
            self._execute("DROP TABLE banlist_lower")

            # Bump version
            self.set_version(Version('0.5.0'))
        # TODO: update this function when changing DDL

    def get_version(self) -> Version:
        """Get the version of the database"""
        return Version(self._fetchone("PRAGMA user_version")[0])

    def set_version(self, version: Version) -> None:
        """Set database version to a specific version"""
        self._execute(f"PRAGMA user_version = {int(version)}")

    def set_password(self, password: str) -> None:
        """Set the password used to encrypt/decrypt banlist entries"""
        self.fernet = Fernet(base64.urlsafe_b64encode(
            PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self.salt,
                       iterations=480000).derive(password.encode())))
        self._execute("UPDATE config SET value = ? WHERE key = 'check'",
                      (self.fernet.encrypt(self.salt),))

    def check_password(self, password) -> bool:
        """Check if the password is correct"""
        try:
            return (Fernet(base64.urlsafe_b64encode(
                PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self.salt, iterations=480000).derive(
                    password.encode()))).decrypt(self._fetchconfig("check")) == self.salt)
        except cryptography.InvalidToken:
            return False

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
                if not word_meta_u:  # First operand in or must not be None
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

    def get_banlist_entry(self, word: str) -> BanlistEntry | None:
        """
        Get a banlist entry
        :param word: Word to get entry for
        :return: BanlistEntry if word is banned for the specified case, None otherwise
        """
        word = word.lower()
        return next((entry for entry in self.banlist if entry.word == word), None)

    def log_word(self, word: str, start_time: datetime, end_time: datetime) -> bool:
        """
        Log a word entry if not banned, creating it if it doesn't exist
        :param word: Word to log
        :param start_time: Timestamp of start of word started
        :param end_time: Timestamp of end of word
        :returns: True if word was logged, False if it was banned
        """
        if self.check_banned(word):
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
        if self.check_banned(chord):
            return False  # banned
        metadata = self.get_chord_metadata(chord)
        if metadata:  # Use or operator to combine metadata with existing entry
            metadata |= ChordMetadata(chord, 1, end_time)
            self._execute("UPDATE chordlog SET frequency=?, lastused=? WHERE chord=?",
                          (metadata.frequency, metadata.last_used.timestamp(), chord))
        else:  # New entry
            self._execute("INSERT INTO chordlog VALUES (?, ?, ?)", (chord, 1, end_time.timestamp()))
        return True

    def check_banned(self, word: str) -> bool:
        """
        Check if a word is banned
        :returns: True if word is banned, False otherwise
        """
        return self.get_banlist_entry(word) is not None

    def ban_word(self, word: str, time: datetime) -> bool:
        """
        Delete a word/chord entry and add it to the ban list
        :returns: True if word was banned, False if it was already banned
        """
        if self.check_banned(word):
            return False  # already banned

        # Freqlog
        word = word.lower()
        self._execute("DELETE FROM freqlog WHERE word = ? COLLATE NOCASE", (word,))

        # Chordlog
        self._execute("DELETE FROM chordlog WHERE chord=?", (word,))

        # Ban
        self.banlist.append(BanlistEntry(word, time))
        self._execute("INSERT OR IGNORE INTO banlist VALUES (?, ?)", (self.encrypt(word), time.timestamp()))
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

    def unban_word(self, word: str) -> bool:
        """
        Remove a word from the ban list
        :returns: True if word was unbanned, False if it was already not banned
        """
        if not self.check_banned(word):
            return False  # not banned
        self._execute("DELETE FROM banlist WHERE dateadded=?", (self.get_banlist_entry(word).date_added.timestamp(),))
        self.banlist.remove(self.get_banlist_entry(word))
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
                          reverse: bool) -> list[BanlistEntry]:
        """
        List banned words
        :param limit: Maximum number of banned words to return
        :param sort_by: Attribute to sort by: word, dateadded
        :param reverse: Reverse sort order
        :returns: List of banned words
        """
        res = sorted(self.banlist, key=lambda x: getattr(x, sort_by.name), reverse=reverse)
        return res[:limit] if limit > 0 else res

    def merge_backend(self, src_db_path: str, dst_db_path: str, ban_date: Age,
                      src_db_passwd_callback: callable, dst_db_passwd_callback: callable) -> None:
        """
        Merge another database and this one into a new database
        :param src_db_path: Path to the source database
        :param dst_db_path: Path to the destination database
        :param src_db_passwd_callback: Callback to call to get password to decrypt the source database banlist
                Should take one argument: whether the password is being set for the first time
        :param dst_db_passwd_callback: Callback to call to get password to decrypt the destination database banlist
                Should take one argument: whether the password is being set for the first time
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
        try:  # Ensure that src is writable (WARNING: Must use 'a' instead of 'w' mode to avoid erasing file!!!)
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
        src_db = SQLiteBackend(src_db_path, src_db_passwd_callback, self.upgrade_callback)
        dst_db = SQLiteBackend(dst_db_path, dst_db_passwd_callback)

        # Merge databases
        # TODO: optimize this/add progress bars (this takes a long time)
        try:
            # Merge banlist
            logging.info("Merging banlist")
            src_banned_words = src_db.list_banned_words(0, BanlistAttr.word, False)
            banned_words = self.list_banned_words(0, BanlistAttr.word, False)

            # Ban words from self banlist in dst db
            for entry in banned_words:
                dst_db.ban_word(entry.word, entry.date_added)

            # Ban words from src banlist in dst db
            for entry in src_banned_words:
                dst_entry = dst_db.get_banlist_entry(entry.word)
                if dst_entry and ((ban_date == Age.OLDER and entry.date_added < dst_entry.date_added) or
                                  (ban_date == Age.NEWER and entry.date_added > dst_entry.date_added)):
                    dst_db.unban_word(entry.word)
                    dst_db.ban_word(entry.word, entry.date_added)
                else:
                    dst_db.ban_word(entry.word, entry.date_added)

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
