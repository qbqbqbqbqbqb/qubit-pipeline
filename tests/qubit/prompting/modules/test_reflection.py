from src.qubit.prompting.modules.reflection import reflection_memory_module


def test_reflection_memory_module_with_reflections():
    reflections = [{"content": "reflection 1"}, {"content": "reflection 2"}]
    result = reflection_memory_module(reflections)
    assert result is not None
    assert "reflection 1" in result.content
    assert "reflection 2" in result.content
    assert result.priority == 60


def test_reflection_memory_module_empty_list():
    result = reflection_memory_module([])
    assert result is None


def test_reflection_memory_module_none_list():
    result = reflection_memory_module(None)
    assert result is None