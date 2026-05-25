import pytest

# twitchAPI + config pre-mocked in conftest.

from src.qubit.utils.filter_utils import contains_banned_words, filter_banned_words


def test_contains_banned_words_basic():
    assert contains_banned_words("hello badword", ["bad"]) is True
    assert contains_banned_words("hello goodword", ["bad"]) is False


def test_contains_banned_words_case_insensitive():
    assert contains_banned_words("Hello BADWORD", ["bad"]) is True
    assert contains_banned_words("hello BadWoRd", ["bad"]) is True


def test_contains_banned_words_whitelist_allows_substring():
    # The word "badword" contains the whitelisted substring "bad" -> should be allowed (not banned)
    assert contains_banned_words("hello badword", ["bad"], ["bad"]) is False
    # The word "bad" does not contain the whitelisted substring "badword" as a substring? 
    # Actually, "bad" is a substring of "badword", but we check if any whitelisted substring is in the word.
    # The whitelisted substring "badword" is NOT in the word "bad" -> so the word is NOT skipped -> banned.
    assert contains_banned_words("hello bad", ["bad"], ["badword"]) is True


def test_filter_banned_words_replacement():
    assert filter_banned_words("hello badword", ["bad"]) == "hello [filtered]word"
    assert filter_banned_words("hello goodword", ["bad"]) == "hello goodword"


def test_filter_banned_words_whitelist_prevents_replacement():
    # Whitelisted substring "bad" in "badword" -> should not be filtered
    assert filter_banned_words("hello badword", ["bad"], ["bad"]) == "hello badword"
    # Whitelisted substring "word" in "badword" -> should not be filtered
    assert filter_banned_words("hello badword", ["bad"], ["word"]) == "hello badword"


def test_filter_banned_words_punctuation_preserved():
    assert filter_banned_words("hello badword!", ["bad"]) == "hello [filtered]word!"
    assert filter_banned_words("hello, badword.", ["bad"]) == "hello, [filtered]word."


def test_filter_banned_words_multiple_occurrences():
    assert filter_banned_words("bad bad bad", ["bad"]) == "[filtered] [filtered] [filtered]"
    assert filter_banned_words("badabad", ["bad"]) == "[filtered]a[filtered]"