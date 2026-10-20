# utils/

Shared utilities with no dependencies on application layers. Any module here must be safe to import from anywhere.

## Files

| File | Provides |
|---|---|
| `log_utils.py` | `get_logger(name)` — returns a configured `logging.Logger`; the single logging entry point for the whole application |
| `filter_utils.py` | Word-list filtering helpers; used by `ModerationProcessor` and `OutputCoordinator` |
| `message_tracker.py` | `MessageTracker` — sliding-window deduplication for chat messages; used by `ConversationProcessor` |
| `file_utils.py` | File system helpers (directory scanning, safe path construction) |
| `tts_utils.py` | TTS text pre-processing utilities (abbreviation expansion, number normalisation) |

## Rules

- No file in `utils/` may import from `cognitive/`, `processing/`, `generation/`, `memory/`, `models/`, `output/`, or `input/`.
- No application state (`RuntimeState`, `FeatureFlags`, `EventBus`) is stored here.
- Pure functions and stateless classes only.
