import pytest
from src.qubit.prompting.modules.core import core_system_module
from src.qubit.prompting.injections import PromptInjection


def test_core_system_module_returns_injection():
    inj = core_system_module()
    assert isinstance(inj, PromptInjection)
    assert inj.content is not None
    assert len(inj.content) > 0
    assert inj.priority == 100