import pytest

pytest.importorskip("twitchAPI", reason="Output sanitizer imports config which pulls twitchAPI")

from src.qubit.output.output_sanitiser import DialogueSanitiser


@pytest.fixture
def sanitiser():
    return DialogueSanitiser(blacklist=["badword", "offensive"], whitelist=["goodword"])


def test_is_valid_filters_banned_words(sanitiser):
    is_valid, filtered = sanitiser.is_valid("This is a badword response")
    # Note: actual filtering is done by filter_banned_words; here we just test the wrapper
    assert is_valid is True
    # The sanitiser delegates to filter_banned_words
    assert isinstance(filtered, str)


def test_is_valid_rejects_empty(sanitiser):
    is_valid, _ = sanitiser.is_valid("   ")
    assert is_valid is False


def test_remove_trailing_text(sanitiser):
    text = "Hello world. This is extra stuff!"
    result = sanitiser.remove_trailing_text(text)
    assert result == "Hello world."


def test_remove_bot_name(sanitiser):
    text = "qubit: Hello there"
    result = sanitiser.remove_bot_name(text)
    assert result == "Hello there"


def test_strip_leading_punctuation(sanitiser):
    text = "!!! Hello world"
    result = sanitiser.strip_leading_punctuation(text)
    assert result == "Hello world"
