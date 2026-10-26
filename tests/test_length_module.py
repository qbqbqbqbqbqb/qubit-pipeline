"""Tests for the randomised response length injection module."""

import pytest
from collections import Counter
from src.qubit.prompting.modules.length import length_module, _STT, _MONOLOGUE, _DEFAULT


def test_returns_prompt_injection():
    from src.qubit.prompting.injections import PromptInjection
    inj = length_module()
    assert isinstance(inj, PromptInjection)


def test_priority_is_35():
    inj = length_module()
    assert inj.priority == 35


def test_content_is_non_empty():
    inj = length_module()
    assert inj.content.strip()


def test_stt_source_produces_valid_instruction():
    inj = length_module(source="stt_filtered")
    valid = [i for i, _ in _STT]
    assert inj.content in valid


def test_monologue_event_produces_valid_instruction():
    inj = length_module(event_type="monologue_prompt")
    valid = [i for i, _ in _MONOLOGUE]
    assert inj.content in valid


def test_chat_source_produces_valid_instruction():
    inj = length_module(event_type="response_prompt", source="twitch_chat_filtered")
    valid = [i for i, _ in _DEFAULT]
    assert inj.content in valid


def test_no_args_produces_valid_instruction():
    inj = length_module()
    valid = [i for i, _ in _DEFAULT]
    assert inj.content in valid


def test_stt_biases_toward_short(runs=500):
    counts = Counter()
    for _ in range(runs):
        inj = length_module(source="stt_filtered")
        counts[inj.content] += 1
    short = [i for i, _ in _STT][0]  # "One sentence..."
    assert counts[short] > runs * 0.35, "STT should heavily favour one-sentence responses"


def test_monologue_biases_toward_longer(runs=500):
    counts = Counter()
    for _ in range(runs):
        inj = length_module(event_type="monologue_prompt")
        counts[inj.content] += 1
    longer = [i for i, _ in _MONOLOGUE][-1]  # "Take your time..."
    assert counts[longer] > runs * 0.15, "Monologue should favour longer responses more often"


def test_default_weights_sum_to_one():
    total = sum(w for _, w in _DEFAULT)
    assert abs(total - 1.0) < 0.01


def test_stt_weights_sum_to_one():
    total = sum(w for _, w in _STT)
    assert abs(total - 1.0) < 0.01


def test_monologue_weights_sum_to_one():
    total = sum(w for _, w in _MONOLOGUE)
    assert abs(total - 1.0) < 0.01


def test_all_pools_have_same_number_of_entries():
    assert len(_DEFAULT) == len(_STT) == len(_MONOLOGUE)


def test_kick_source_uses_default_pool():
    inj = length_module(event_type="response_prompt", source="kick_chat_filtered")
    valid = [i for i, _ in _DEFAULT]
    assert inj.content in valid


def test_community_event_uses_default_pool():
    # Community events arrive as monologue_prompt type but should still work
    inj = length_module(event_type="monologue_prompt", source=None)
    valid = [i for i, _ in _MONOLOGUE]
    assert inj.content in valid