from src.qubit.prompting.modules.personality import personality_module


def test_personality_module_default_values():
    result = personality_module()
    assert "energetic" in result.content
    assert "casual and humorous" in result.content
    assert result.priority == 90


def test_personality_module_custom_values():
    result = personality_module(mood="calm", tone="serious", interaction_level="low")
    assert "calm" in result.content
    assert "serious" in result.content
    assert "low" in result.content or "Focus mostly" in result.content
    assert result.priority == 90


def test_personality_module_medium_interaction():
    result = personality_module(interaction_level="medium")
    assert "Engage with the audience occasionally" in result.content
    assert result.priority == 90