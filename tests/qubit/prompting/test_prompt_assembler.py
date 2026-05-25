import pytest
from src.qubit.prompting.prompt_assembler import PromptAssembler
from src.qubit.prompting.injections import PromptInjection


def test_prompt_assembler_initialization():
    assembler = PromptAssembler()
    assert assembler.injections == []


def test_add_injection(assembler=None):
    if assembler is None:
        assembler = PromptAssembler()
    injection = PromptInjection(content="Test", priority=5)
    assembler.add(injection)
    assert len(assembler.injections) == 1
    assert assembler.injections[0] == injection


def test_build_joins_injections_by_priority():
    assembler = PromptAssembler()
    assembler.add(PromptInjection(content="Low", priority=1))
    assembler.add(PromptInjection(content="High", priority=10))
    assembler.add(PromptInjection(content="Medium", priority=5))

    prompt = assembler.build()
    # Highest priority first
    expected = "High\n\nMedium\n\nLow"
    assert prompt == expected