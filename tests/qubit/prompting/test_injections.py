import pytest
from src.qubit.prompting.injections import PromptInjection


def test_prompt_injection_default_priority():
    inj = PromptInjection(content="test")
    assert inj.content == "test"
    assert inj.priority == 0


def test_prompt_injection_custom_priority():
    inj = PromptInjection(content="test", priority=5)
    assert inj.content == "test"
    assert inj.priority == 5
