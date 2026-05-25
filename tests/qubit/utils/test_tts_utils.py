import pytest
from unittest.mock import patch

# inflect pre-mocked in conftest when not present.


class TestTTSUtils:
    @pytest.fixture
    def mock_config(self):
        with patch('src.qubit.utils.tts_utils.ACRONYMS_LIST', ['AI', 'API']):
            yield

    def test_spell_out_acronyms(self, mock_config):
        from src.qubit.utils.tts_utils import spell_out_acronyms
        result = spell_out_acronyms("The AI uses an API", ['AI', 'API'])
        assert 'AI' not in result or 'A I' in result
        assert 'API' not in result or 'A P I' in result

    def test_replace_ellipses(self):
        from src.qubit.utils.tts_utils import replace_ellipses
        result = replace_ellipses("Hello...")
        assert "dot dot dot" in result

        result = replace_ellipses("Hello…")
        assert "dot dot dot" in result

    def test_remove_quotes(self):
        from src.qubit.utils.tts_utils import remove_quotes
        result = remove_quotes('"hello"')
        assert result == "hello"

        result = remove_quotes('"hello"')
        assert '"' not in result

    def test_remove_consecutive_whitespace(self):
        from src.qubit.utils.tts_utils import remove_consecutive_whitespace
        result = remove_consecutive_whitespace("hello   world")
        assert result == "hello world"

    def test_remove_unsupported_chars(self):
        from src.qubit.utils.tts_utils import remove_unsupported_chars
        result = remove_unsupported_chars("hello 👋 world")
        assert "hello" in result
        assert "world" in result
        assert "👋" not in result

    def test_remove_brackets_and_parentheses(self):
        from src.qubit.utils.tts_utils import remove_brackets_and_parentheses
        result = remove_brackets_and_parentheses("hello [remove] world")
        assert "remove" not in result
        assert "hello" in result

        result = remove_brackets_and_parentheses("hello (remove) world")
        assert "remove" not in result

    def test_convert_numbers_to_words(self):
        from src.qubit.utils.tts_utils import convert_numbers_to_words
        def mock_converter(n):
            return "ONE" if n == "1" else "TWO"
        result = convert_numbers_to_words("I have 1 apple and 2 oranges", mock_converter)
        assert "ONE" in result
        assert "TWO" in result