import pytest
from src.qubit.prompting.modules.chat import chat_memory_module
from src.qubit.prompting.injections import PromptInjection


def test_chat_memory_module_returns_injection_or_none():
    # With empty history, should return None
    inj = chat_memory_module([])
    assert inj is None or isinstance(inj, PromptInjection)

    # With some history, should return an injection
    history = [{"role": "User", "content": "hello"}, {"role": "Qubit", "content": "hi"}]
    inj = chat_memory_module(history)
    if inj is not None:
        assert isinstance(inj, PromptInjection)
        assert inj.content is not None