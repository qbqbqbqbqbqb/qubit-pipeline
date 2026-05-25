from src.qubit.prompting.modules.stream_type import stream_type_module


def test_stream_type_module_returns_injection():
    result = stream_type_module()
    assert "Just Chatting" in result.content
    assert result.priority == 80


def test_stream_type_module_content_format():
    result = stream_type_module()
    assert result.content.startswith("You are doing a")