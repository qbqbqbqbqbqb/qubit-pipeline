# Testing Strategy & Mocking Guidelines

## Core Principle

**Never use `pytest.importorskip` or module-level `pytest.skip` for heavy dependencies** (torch, transformers, chromadb, twitchAPI, numpy, audio libs, etc.).

Instead, **prioritise mocking** so that every test file can be collected and every test can run even in a minimal Python environment.

## The `mock_heavy_stack` Fixture

Located in `tests/conftest.py`.

Use it when a test touches:
- Model loading / LLM inference
- ChromaDB / long-term memory
- Twitch or other external realtime APIs
- Audio synthesis (TTS, pyaudio, piper)
- OBS / VTube / side-effecty output handlers

### Usage

**Recommended (per-test):**
```python
def test_something(mock_heavy_stack):
    ...
```

**Directory / module level (preferred for models/ and memory/):**
```python
import pytest

pytestmark = [
    pytest.mark.heavy,
    pytest.mark.usefixtures("mock_heavy_stack"),
]
```

## Directory Conventions

- `tests/qubit/models/` → All tests should be marked `heavy` + use `mock_heavy_stack`
- `tests/qubit/memory/` → All tests should be marked `heavy` + use `mock_heavy_stack`
- `tests/qubit/core/` (especially bootstrap) → Use when touching `create_app()` or services that pull heavy deps
- Pure logic tests (most cognitive, event bus, priority queue, etc.) usually do **not** need it

## Pattern for Heavy Modules

When a module under test does heavy work at import time:

1. Move the `from src.qubit.xxx.heavy import HeavyThing` **inside** the test function (lazy import).
2. Patch the specific constructors/classes inside the test (or rely on `mock_heavy_stack`).
3. Never let real model loading, DB connections, or network calls happen during test execution.

## Adding New Heavy Dependencies

If a new heavy library appears, update:
1. `tests/conftest.py` → `mock_heavy_stack` fixture (both the `targets` list and the `sys.modules` pre-population block)
2. This `AGENTS.md` file

## Why This Approach?

- Tests remain fast and deterministic
- CI can run the full suite without a full GPU/ML environment
- New contributors never hit confusing "skipped because torch not installed" messages
- Real behaviour is still tested via unit tests of the individual components (with their own mocks)

## Current Heavy Directories

- `tests/qubit/models/`
- `tests/qubit/memory/`
- Parts of `tests/qubit/output/` (TTS, OBS)
- `tests/qubit/input/` (Twitch listener)
- `tests/qubit/core/test_bootstrap.py`

## Anti-Patterns to Avoid

- `pytest.importorskip("torch")` at the top of a test file
- Real `chromadb.PersistentClient()` or `AutoModelForCausalLM.from_pretrained()` in tests
- Module-level imports of heavy classes in test files that are not inside `if TYPE_CHECKING:` or lazy imports

Follow the mocking strategy and the entire suite stays green and fast.
