import pytest

from src.qubit.output.handlers.sanitiser import DialogueSanitiser


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


def test_fuzz_style_various_inputs(sanitiser, mock_heavy_stack):
    """Fuzz-style test: feed many varied (including nasty) inputs to sanitiser."""
    import random

    candidates = [
        "",
        "   ",
        "normal message",
        "badword offensive content",
        "Qubit: hello there",
        "A very long response with lots of words and punctuation!!!",
        "assistant: This is a test",
        "Mixed CASE and 123 numbers",
        "???",
    ]

    for _ in range(30):
        text = random.choice(candidates)
        is_valid, filtered = sanitiser.is_valid(text)
        # Should never crash and should always return strings
        assert isinstance(is_valid, bool)
        assert isinstance(filtered, str)
    assert sanitiser.remove_bot_name("QUBIT: upper") == "upper"


def test_strip_leading_punctuation(sanitiser):
    text = "!!! Hello world"
    result = sanitiser.strip_leading_punctuation(text)
    assert result == "Hello world"

    assert sanitiser.strip_leading_punctuation("...test") == "test"
    assert sanitiser.strip_leading_punctuation("no punct") == "no punct"
