from src.qubit.prompting.modules.input import input_module


def test_input_module_returns_injection():
    result = input_module("hello world")
    assert result.content == "hello world"
    assert result.priority == 10


def test_input_module_with_empty_string():
    result = input_module("")
    assert result.content == ""
    assert result.priority == 10