"""Shared pytest fixtures for the qubit-pipeline test suite."""

import sys
import os
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project root is on sys.path and is the working directory so
# config.config can resolve data file paths via get_root().
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)


def _stub_module(name: str, **attrs) -> ModuleType:
    """Create a minimal stub module so heavy imports don't crash in CI."""
    mod = ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# Stub torch and transformers so model_config.py can be imported without a GPU.
if "torch" not in sys.modules:
    torch_stub = _stub_module("torch")
    torch_stub.cuda = _stub_module("torch.cuda", is_available=lambda: False)
    # Sentinel dtype values used as dataclass field defaults in model_config.py
    torch_stub.dtype = type("dtype", (), {})
    torch_stub.float16 = object()
    torch_stub.bfloat16 = object()
    torch_stub.float32 = object()
    sys.modules["torch"] = torch_stub
    sys.modules["torch.cuda"] = torch_stub.cuda

for _name in (
    "transformers",
    "transformers.AutoModelForCausalLM",
    "transformers.AutoTokenizer",
    "transformers.BitsAndBytesConfig",
    "peft",
    "peft.PeftModel",
    "bitsandbytes",
):
    if _name not in sys.modules:
        sys.modules[_name] = _stub_module(_name)


def make_event(type_="twitch_chat_processed", text="hello", user="viewer1", **kwargs):
    event = MagicMock()
    event.type = type_
    event.text = text
    event.user = user
    event.timestamp = datetime.now(timezone.utc).isoformat()
    event.data = {"text": text, "user": user}
    for k, v in kwargs.items():
        setattr(event, k, v)
    return event


def make_feature_flags(**overrides):
    from src.qubit.core.runtime_state import FeatureFlags
    flags = FeatureFlags()
    for k, v in overrides.items():
        setattr(flags, k, v)
    return flags


def make_app(features=None):
    from src.qubit.core.runtime_state import RuntimeState
    from src.qubit.core.event_bus import EventBus
    app = MagicMock()
    app.state = RuntimeState()
    app.event_bus = EventBus()
    if features:
        for k, v in features.items():
            setattr(app.state.features, k, v)
    return app


@pytest.fixture
def app():
    return make_app()


@pytest.fixture
def event_bus():
    from src.qubit.core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def feature_flags():
    return make_feature_flags()
