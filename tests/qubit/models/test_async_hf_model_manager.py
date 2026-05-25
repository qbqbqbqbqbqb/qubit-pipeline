import pytest
from unittest.mock import patch, MagicMock, AsyncMock

pytest.importorskip("torch", reason="AsyncHuggingFaceLLM requires torch + transformers")



@pytest.fixture
def mock_model_manager():
    mgr = MagicMock()
    mgr.model = MagicMock()
    mgr.tokenizer = MagicMock()
    return mgr


def test_async_hf_llm_instantiation(mock_model_manager):
    llm = AsyncHuggingFaceLLM(mock_model_manager, max_tokens=128)
    assert llm.max_tokens == 128
    assert llm.model_manager is mock_model_manager


@pytest.mark.asyncio
async def test_generate_with_retries_returns_string(mock_model_manager):
    llm = AsyncHuggingFaceLLM(mock_model_manager)
    llm.model_manager.generate_dialogue = MagicMock(return_value="Hello there")

    result = await llm.generate_with_retries("test prompt")
    assert isinstance(result, str)
    assert "Hello" in result
