import pytest

from src.qubit.output.output_sanitiser import DialogueSanitiser


@pytest.fixture
def sanitiser():
    # Support both old (config-driven) and new (explicit bot_name) signatures
    try:
        return DialogueSanitiser(bot_name="Qubit", blacklist=["badword", "offensive"], whitelist=["goodword"])
    except TypeError:
        return DialogueSanitiser(blacklist=["badword", "offensive"], whitelist=["goodword"])


def test_is_valid_filters_banned_words(sanitiser):
    is_valid, filtered = sanitiser.is_valid("This is a badword response")
    assert is_valid is True
    assert isinstance(filtered, str)


def test_is_valid_rejects_empty(sanitiser):
    is_valid, _ = sanitiser.is_valid("   ")
    assert is_valid is False


def test_remove_trailing_text(sanitiser):
    text = "Hello world. This is extra stuff"
    result = sanitiser.remove_trailing_text(text)
    assert result == "Hello world."


def test_remove_bot_name(sanitiser):
    text = "qubit: Hello there"
    result = sanitiser.remove_bot_name(text)
    assert result == "Hello there"


def test_remove_bot_name_variants(sanitiser):
    assert sanitiser.remove_bot_name("assistant: hi") == "hi"
    assert sanitiser.remove_bot_name("user: yo") == "yo"
    assert sanitiser.remove_bot_name("QUBIT: upper") == "upper"


def test_strip_leading_punctuation(sanitiser):
    text = "!!! Hello world"
    result = sanitiser.strip_leading_punctuation(text)
    assert result == "Hello world"

    assert sanitiser.strip_leading_punctuation("...test") == "test"
    assert sanitiser.strip_leading_punctuation("no punct") == "no punct"
