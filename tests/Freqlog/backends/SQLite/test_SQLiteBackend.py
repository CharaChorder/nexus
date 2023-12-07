from datetime import datetime, timedelta

import pytest

from nexus.Freqlog.backends import SQLiteBackend
from nexus.Freqlog.Definitions import BanlistAttr, CaseSensitivity, WordMetadataAttr

TIME = datetime.now()


@pytest.fixture(autouse=True)
def loaded_backend() -> SQLiteBackend:
    backend = SQLiteBackend(":memory:", lambda _: "test")
    backend.log_word("one", TIME - timedelta(seconds=0.5), TIME)
    backend.log_word("two", TIME + timedelta(minutes=1) - timedelta(seconds=2), TIME + timedelta(minutes=1))
    backend.log_word("two", TIME + timedelta(minutes=2) - timedelta(seconds=3), TIME + timedelta(minutes=2))
    backend.log_word("three", TIME + timedelta(minutes=3) - timedelta(seconds=1), TIME + timedelta(minutes=3))
    backend.log_word("Three", TIME + timedelta(minutes=4) - timedelta(seconds=2), TIME + timedelta(minutes=4))
    backend.log_word("tHrEe", TIME + timedelta(minutes=5) - timedelta(seconds=6), TIME + timedelta(minutes=5))
    yield backend
    backend.close()


def close_to(a: datetime | timedelta, b: datetime | timedelta) -> bool:
    return abs(a - b) < timedelta(microseconds=100)


def test_check_password(loaded_backend):
    backend = loaded_backend
    assert backend.check_password("test") is True
    assert backend.check_password("wrong") is False
    backend.set_password("new")
    assert backend.check_password("new") is True
    assert backend.check_password("test") is False


@pytest.mark.parametrize("word,case,freq,last_used,avg_speed", [
    ("one", CaseSensitivity.SENSITIVE, 1, 0, 0.5),
    ("two", CaseSensitivity.SENSITIVE, 2, 2, 2.5),
    ("three", CaseSensitivity.SENSITIVE, 1, 3, 1),
    ("three", CaseSensitivity.FIRST_CHAR, 2, 4, 1.5),
    ("three", CaseSensitivity.INSENSITIVE, 3, 5, 3),
])
def test_get_word_metadata(loaded_backend, word, case, freq, last_used, avg_speed):
    backend = loaded_backend
    data = backend.get_word_metadata(word, case)
    assert data.word == word
    assert data.frequency == freq
    assert close_to(data.last_used, TIME + timedelta(minutes=last_used))
    assert close_to(data.average_speed, timedelta(seconds=avg_speed))


@pytest.mark.parametrize("case,sortby,reverse,vals", [
    # (word, frequency, last_used, average_speed)
    (CaseSensitivity.INSENSITIVE, WordMetadataAttr.frequency, True, [
        ("three", 3, 5, 3),
        ("two", 2, 2, 2.5),
        ("one", 1, 0, 0.5)]),
    (CaseSensitivity.SENSITIVE, WordMetadataAttr.last_used, True, [
        ("tHrEe", 1, 5, 6),
        ("Three", 1, 4, 2),
        ("three", 1, 3, 1),
        ("two", 2, 2, 2.5),
        ("one", 1, 0, 0.5)]),
    (CaseSensitivity.FIRST_CHAR, WordMetadataAttr.average_speed, False, [
        ("one", 1, 0, 0.5),
        ("three", 2, 4, 1.5),
        ("two", 2, 2, 2.5),
        ("tHrEe", 1, 5, 6)]),
])
def test_list_words(loaded_backend, case, sortby, reverse, vals):
    backend = loaded_backend
    data = backend.list_words(0, sortby, reverse, case)
    for v in vals:
        assert data[0].word == v[0]
        assert data[0].frequency == v[1]
        assert close_to(data[0].last_used, TIME + timedelta(minutes=v[2]))  # type: ignore[union-attr]
        assert close_to(data[0].average_speed, timedelta(seconds=v[3]))  # type: ignore[union-attr]
        data = data[1:]
    assert len(data) == 0


def test_list_words_limit(loaded_backend):
    backend = loaded_backend
    data = backend.list_words(2, WordMetadataAttr.frequency, True, CaseSensitivity.INSENSITIVE)
    assert len(data) == 2
    assert data[0].word == "three"
    assert data[1].word == "two"


@pytest.mark.parametrize("word,original,remaining", [
    ("one", 5, 4),
    ("two", 5, 4),
    ("three", 5, 2),
])
def test_ban_unban_word(loaded_backend, word, original, remaining):
    backend = loaded_backend

    # Pre-ban
    assert backend.check_banned(word) is False
    assert len(backend.list_words(sort_by=WordMetadataAttr.frequency, case=CaseSensitivity.SENSITIVE)) == original
    assert backend.list_banned_words(0, BanlistAttr.word, True) == []

    assert backend.ban_word(word, TIME) is True

    # Post-ban, pre-unban
    assert backend.check_banned(word) is True
    assert backend.get_word_metadata(word, CaseSensitivity.INSENSITIVE) is None
    assert backend.log_word(word, TIME, TIME) is False
    res = backend.list_banned_words(0, BanlistAttr.word, True)
    res_word = None
    for w in res:
        if w.word == word:
            res_word = w
            break
    assert res_word is not None
    assert close_to(res_word.date_added, TIME)
    assert len(backend.list_words(0, WordMetadataAttr.frequency, True, CaseSensitivity.SENSITIVE)) == remaining

    backend.unban_word(word)

    # Post-unban
    assert backend.check_banned(word) is False
    assert backend.list_banned_words(0, BanlistAttr.word, False) == []


def test_dup_ban_unban(loaded_backend):
    backend = loaded_backend
    assert backend.ban_word("one", TIME) is True
    assert backend.ban_word("one", TIME) is False
    assert backend.unban_word("one") is True
    assert backend.unban_word("one") is False


def test_num_words(loaded_backend):
    backend = loaded_backend
    assert backend.num_words(CaseSensitivity.INSENSITIVE) == 3
    assert backend.num_words(CaseSensitivity.SENSITIVE) == 5
    assert backend.num_words(CaseSensitivity.FIRST_CHAR) == 4
