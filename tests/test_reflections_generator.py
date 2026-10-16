"""Tests for ReflectionGenerator — JSON parser and fallback text parser."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.qubit.memory.reflections_generator import ReflectionGenerator


@pytest.fixture
def generator():
    g = ReflectionGenerator.__new__(ReflectionGenerator)
    import logging
    g.logger = logging.getLogger("test_reflections")
    g.llm_service = None
    g.reflection_profile = "reflection"
    g.reflection_threshold = 20
    return g


# -----------------------------------------------------------------------
# _try_json_parse
# -----------------------------------------------------------------------

def test_clean_json_parsed(generator):
    raw = '[{"q":"Who is Qubit?","a":"An AI VTuber"},{"q":"Game?","a":"Minecraft"},{"q":"Mood?","a":"Excited"}]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3
    assert pairs[0] == ("Who is Qubit?", "An AI VTuber")


def test_json_with_preamble_parsed(generator):
    raw = 'Sure! Here are reflections:\n[{"q":"Q1","a":"A1"},{"q":"Q2","a":"A2"},{"q":"Q3","a":"A3"}]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3


def test_json_in_markdown_fence_parsed(generator):
    raw = "```json\n[{\"q\":\"Q1\",\"a\":\"A1\"},{\"q\":\"Q2\",\"a\":\"A2\"},{\"q\":\"Q3\",\"a\":\"A3\"}]\n```"
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3


def test_json_trailing_commas_parsed(generator):
    raw = '[{"q":"Q1","a":"A1",},{"q":"Q2","a":"A2",},{"q":"Q3","a":"A3",},]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3


def test_json_question_answer_keys_parsed(generator):
    raw = '[{"question":"Q1","answer":"A1"},{"question":"Q2","answer":"A2"},{"question":"Q3","answer":"A3"}]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3


def test_json_uppercase_keys_parsed(generator):
    raw = '[{"Q":"Q1","A":"A1"},{"Q":"Q2","A":"A2"},{"Q":"Q3","A":"A3"}]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 3


def test_json_capped_at_three_via_parse(generator):
    # Cap is enforced by _parse_qa_pairs, not _try_json_parse directly
    raw = '[{"q":"Q1","a":"A1"},{"q":"Q2","a":"A2"},{"q":"Q3","a":"A3"},{"q":"Q4","a":"A4"}]'
    pairs = generator._parse_qa_pairs(raw)
    assert len(pairs) == 3


def test_invalid_json_returns_empty(generator):
    pairs = generator._try_json_parse("not json at all")
    assert pairs == []


def test_json_empty_array_returns_empty(generator):
    pairs = generator._try_json_parse("[]")
    assert pairs == []


def test_json_items_with_empty_strings_excluded(generator):
    raw = '[{"q":"","a":"A1"},{"q":"Q2","a":"A2"},{"q":"Q3","a":"A3"}]'
    pairs = generator._try_json_parse(raw)
    assert len(pairs) == 2


# -----------------------------------------------------------------------
# _try_text_parse
# -----------------------------------------------------------------------

def test_q1_a1_format_parsed(generator):
    raw = "Q1: Who is Qubit?\nA1: An AI VTuber\n\nQ2: Game?\nA2: Minecraft\n\nQ3: Mood?\nA3: Excited"
    pairs = generator._try_text_parse(raw)
    assert len(pairs) == 3
    assert pairs[0] == ("Who is Qubit?", "An AI VTuber")


def test_bold_q1_a1_format_parsed(generator):
    raw = "**Q1:** Who is Qubit?\n**A1:** An AI VTuber\n**Q2:** Game?\n**A2:** Minecraft\n**Q3:** Mood?\n**A3:** Excited"
    pairs = generator._try_text_parse(raw)
    assert len(pairs) == 3


def test_question_n_answer_n_format_parsed(generator):
    raw = "Question 1: Who?\nAnswer 1: Qubit\nQuestion 2: Game?\nAnswer 2: Minecraft\nQuestion 3: Mood?\nAnswer 3: Chill"
    pairs = generator._try_text_parse(raw)
    assert len(pairs) == 3


def test_unrecognised_format_returns_empty(generator):
    raw = "Some random text with no structure whatsoever"
    pairs = generator._try_text_parse(raw)
    assert pairs == []


def test_incomplete_pair_not_included(generator):
    raw = "Q1: A question with no answer"
    pairs = generator._try_text_parse(raw)
    assert pairs == []


# -----------------------------------------------------------------------
# _parse_qa_pairs (combined)
# -----------------------------------------------------------------------

def test_parse_prefers_json_over_text(generator):
    raw = '[{"q":"Q1","a":"A1"},{"q":"Q2","a":"A2"},{"q":"Q3","a":"A3"}]'
    pairs = generator._parse_qa_pairs(raw)
    assert len(pairs) == 3


def test_parse_falls_back_to_text_when_json_fails(generator):
    raw = "Q1: Who is Qubit?\nA1: An AI VTuber\n\nQ2: Game?\nA2: Minecraft\n\nQ3: Mood?\nA3: Happy"
    pairs = generator._parse_qa_pairs(raw)
    assert len(pairs) == 3


def test_parse_returns_empty_when_both_fail(generator):
    pairs = generator._parse_qa_pairs("completely unparseable content !@#$")
    assert pairs == []


# -----------------------------------------------------------------------
# perform_reflection (mocked LLM)
# -----------------------------------------------------------------------

async def test_perform_reflection_returns_pairs(generator):
    llm = MagicMock()
    llm.generate_with_retries = AsyncMock(
        return_value='[{"q":"Q1","a":"A1"},{"q":"Q2","a":"A2"},{"q":"Q3","a":"A3"}]'
    )
    generator.llm_service = llm

    memory_manager = MagicMock()
    memory_manager.get_recent_items = AsyncMock(return_value=[
        {"role": "User", "content": f"message {i}", "user_id": "viewer"}
        for i in range(15)
    ])

    pairs = await generator.perform_reflection(memory_manager)
    assert len(pairs) == 3


async def test_perform_reflection_too_few_messages_returns_empty(generator):
    generator.llm_service = MagicMock()

    memory_manager = MagicMock()
    memory_manager.get_recent_items = AsyncMock(return_value=[
        {"role": "User", "content": "hi", "user_id": "viewer"}
    ])

    pairs = await generator.perform_reflection(memory_manager)
    assert pairs == []


async def test_perform_reflection_llm_error_returns_empty(generator):
    llm = MagicMock()
    llm.generate_with_retries = AsyncMock(side_effect=Exception("LLM offline"))
    generator.llm_service = llm

    memory_manager = MagicMock()
    memory_manager.get_recent_items = AsyncMock(return_value=[
        {"role": "User", "content": f"msg {i}", "user_id": "v"}
        for i in range(15)
    ])

    pairs = await generator.perform_reflection(memory_manager)
    assert pairs == []
