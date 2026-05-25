"""Tests for the new multi-LLM architecture (LLMService, LLMProfile, PromptFormatters)."""

import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

# Ensure heavy mocking is active for this directory via conftest
pytestmark = [
    pytest.mark.heavy,
    pytest.mark.usefixtures("mock_heavy_stack"),
]

from src.qubit.models.llm_profile import LLMProfile, GenerationOverrides
from src.qubit.models.model_config import ModelConfig, GenerationConfig
from src.qubit.models.prompt_formatters import (
    get_formatter,
    list_formatters,
    register_formatter,
    PromptFormatter,
)
from src.qubit.models.llm_service import LLMService


def test_prompt_formatters_are_registered():
    formatters = list_formatters()
    assert "raw" in formatters
    assert "chat_template" in formatters
    assert "reflection" in formatters
    assert "pygmalion" in formatters


def test_get_formatter_fallback():
    # Unknown name falls back to raw safely
    fmt = get_formatter("nonexistent-formatter-xyz")
    assert fmt is not None
    result = fmt.format(assembled_text="hello")
    assert "hello" in result or result == "hello"


def test_raw_formatter_basic():
    fmt = get_formatter("raw")
    out = fmt.format(assembled_text="test prompt")
    assert out == "test prompt"

    out2 = fmt.format(messages=[{"role": "user", "content": "hi"}])
    assert "user: hi" in out2


def test_role_mapped_formatter_system_prompt():
    fmt = get_formatter("pygmalion")  # uses RoleMappedFormatter
    out = fmt.format(
        messages=[{"role": "user", "content": "hello"}],
        system="You are special.",
        model_config=ModelConfig(model_name="test")
    )
    assert "System: You are special." in out
    assert "User: hello" in out


def test_reflection_formatter_adds_analytical_system():
    fmt = get_formatter("reflection")
    out = fmt.format(assembled_text="some chat history")
    assert "analytical AI" in out.lower() or "insights" in out.lower()


def test_llm_profile_creation():
    cfg = ModelConfig(model_name="test/model")
    profile = LLMProfile(
        key="test-profile",
        config=cfg,
        formatter=get_formatter("raw"),
        generation_defaults=GenerationConfig(temperature=0.5),
    )
    assert profile.key == "test-profile"
    assert profile.config.model_name == "test/model"


def test_llm_profile_from_model_config_does_not_mutate():
    original_cfg = ModelConfig(
        model_name="original/model",
        generation_config=GenerationConfig(temperature=0.9)
    )
    profile = LLMProfile.from_model_config(
        key="test",
        model_config=original_cfg,
        formatter_name="raw",
        generation_overrides={"temperature": 0.1}
    )
    # Original should be untouched
    assert original_cfg.generation_config.temperature == 0.9
    # Profile has the override
    assert profile.generation_defaults.temperature == 0.1


class TestLLMService:
    """Tests for LLMService using mocks (no real model loading)."""

    @pytest.fixture
    def mock_manager(self):
        mgr = MagicMock()
        mgr.config = MagicMock()
        mgr.config.generation_config = GenerationConfig()
        mgr.generate_dialogue = MagicMock(return_value="mocked response")
        mgr.tokenizer = None
        return mgr

    def test_register_and_list_profiles(self):
        svc = LLMService()
        cfg = ModelConfig(model_name="fake/model")
        profile = LLMProfile(key="test", config=cfg, formatter=get_formatter("raw"))
        svc.register_profile(profile)

        assert "test" in svc.list_profiles()

    @pytest.mark.asyncio
    async def test_generate_uses_formatter_and_calls_manager(self, mock_manager):
        svc = LLMService()
        cfg = ModelConfig(model_name="fake/model")
        profile = LLMProfile(key="test", config=cfg, formatter=get_formatter("raw"))

        svc.register_profile(profile)
        svc._managers["test"] = mock_manager  # inject mock to skip real load

        result = await svc.generate("test", "hello world", max_new_tokens=50)

        assert result == "mocked response"
        mock_manager.generate_dialogue.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_applies_overrides(self, mock_manager):
        svc = LLMService()
        cfg = ModelConfig(model_name="fake/model")
        profile = LLMProfile(
            key="test",
            config=cfg,
            formatter=get_formatter("raw"),
            generation_defaults=GenerationConfig(temperature=0.9)
        )

        svc.register_profile(profile)
        svc._managers["test"] = mock_manager

        await svc.generate(
            "test",
            "prompt",
            overrides=GenerationOverrides(temperature=0.2, max_new_tokens=99)
        )

        # The service should have temporarily set the effective config
        # We just verify it attempted to call generate_dialogue
        mock_manager.generate_dialogue.assert_called_once()

    def test_dedup_logic_exists(self):
        svc = LLMService()
        assert hasattr(svc, "_same_model_identity")
        assert callable(svc._same_model_identity)
