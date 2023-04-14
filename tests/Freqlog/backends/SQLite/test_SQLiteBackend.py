from datetime import datetime, timedelta

import pytest

from nexus.Freqlog.backends import SQLiteBackend
from nexus.Freqlog.Definitions import CaseSensitivity, WordMetadataAttr

time = datetime.now()


@pytest.fixture
def loaded_backend():
    backend = SQLiteBackend(":memory:")
    backend.log_word("one", time - timedelta(seconds=1), time)
    backend.log_word("two", time + timedelta(minutes=1) - timedelta(seconds=2), time + timedelta(minutes=1))
    backend.log_word("two", time + timedelta(minutes=2) - timedelta(seconds=3), time + timedelta(minutes=2))
    backend.log_word("three", time + timedelta(minutes=3) - timedelta(seconds=1), time + timedelta(minutes=3))
    backend.log_word("Three", time + timedelta(minutes=4) - timedelta(seconds=2), time + timedelta(minutes=4))
    backend.log_word("tHrEe", time + timedelta(minutes=5) - timedelta(seconds=6), time + timedelta(minutes=5))
    return backend


def close_to(a, b):
    return abs(a - b) < timedelta(microseconds=100)


@pytest.mark.parametrize("word,case,freq,last_used,avg_speed", [
    ("one", CaseSensitivity.SENSITIVE, 1, time, timedelta(seconds=1)),
    ("two", CaseSensitivity.SENSITIVE, 2, time + timedelta(minutes=2), timedelta(seconds=2.5)),
    ("three", CaseSensitivity.SENSITIVE, 1, time + timedelta(minutes=3), timedelta(seconds=1)),
    ("three", CaseSensitivity.FIRST_CHAR, 2, time + timedelta(minutes=4), timedelta(seconds=1.5)),
    ("three", CaseSensitivity.INSENSITIVE, 3, time + timedelta(minutes=5), timedelta(seconds=3)),
])
def test_get_word_metadata(loaded_backend, word, case, freq, last_used, avg_speed):
    backend = loaded_backend
    data = backend.get_word_metadata(word, case)
    assert data.word == word
    assert data.frequency == freq
    assert close_to(data.last_used, last_used)
    assert close_to(data.average_speed, avg_speed)


def test_list_words(loaded_backend):
    backend = loaded_backend
    data = backend.list_words(2, WordMetadataAttr.FREQUENCY, True, CaseSensitivity.INSENSITIVE)
    assert data[0].word == "three"
    assert data[0].frequency == 3
    assert close_to(data[0].last_used, time + timedelta(minutes=5))
    assert close_to(data[0].average_speed, timedelta(seconds=3))
    assert data[1].word == "two"
    assert data[1].frequency == 2
    assert close_to(data[1].last_used, time + timedelta(minutes=2))
    assert close_to(data[1].average_speed, timedelta(seconds=2.5))
    assert data[2].word == "one"
    assert data[2].frequency == 1
    assert close_to(data[2].last_used, time)
    assert close_to(data[2].average_speed, timedelta(seconds=1))
