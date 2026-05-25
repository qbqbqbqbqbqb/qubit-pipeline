import pytest
from unittest.mock import MagicMock, AsyncMock

# This directory uses the shared mock_heavy_stack via pytestmark in conftest.py
from src.qubit.memory.reflections_generator import ReflectionGenerator


class TestReflectionGeneratorParsing:
    @pytest.fixture
    def generator(self):
        # The autouse fixture already mocks the LLM; just construct with required llm_service
        mock_llm = MagicMock()
        return ReflectionGenerator(llm_service=mock_llm)

    def test_parse_qa_pairs_standard_format(self, generator):
        response = """Q1: What is the main topic?
A1: AI and streaming.

Q2: Who is the user?
A2: kubi

Q3: What is the mood?
A3: Fun and chaotic"""

        pairs = generator._parse_qa_pairs(response)
        assert len(pairs) == 3
        assert pairs[0] == ("What is the main topic?", "AI and streaming.")
        assert pairs[1][0] == "Who is the user?"

    def test_parse_qa_pairs_fallback_line_parsing(self, generator):
        response = """Q: What happened?
A: Something funny

Q: Another question
A: Another answer"""

        pairs = generator._parse_qa_pairs(response)
        # The fallback is a bit loose, but should extract something
        assert len(pairs) >= 1

    def test_parse_qa_pairs_limits_to_three(self, generator):
        response = """Q1: Q1?
A1: A1

Q2: Q2?
A2: A2

Q3: Q3?
A3: A3

Q4: Q4?
A4: A4"""

        pairs = generator._parse_qa_pairs(response)
        assert len(pairs) <= 3


@pytest.mark.asyncio
async def test_perform_reflection_returns_empty_when_few_messages():
    mock_llm = MagicMock()
    gen = ReflectionGenerator(llm_service=mock_llm)
    mock_memory_manager = MagicMock()
    mock_memory_manager.get_recent_items.return_value = [{"role": "User", "content": "hi"}] * 5

    result = await gen.perform_reflection(mock_memory_manager)
    assert result == []
