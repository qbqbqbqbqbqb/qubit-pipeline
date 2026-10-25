# utils/

Shared helpers. No dependencies on any application layer — safe to import from anywhere.

| File | What it does |
|---|---|
| `log_utils.py` | `get_logger(name)` — single logging entry point for the whole application |
| `filter_utils.py` | Word-list filtering against `BLACKLISTED_WORDS_LIST` and `WHITELISTED_WORDS_LIST` from `config/config.py` |
| `message_tracker.py` | Sliding-window deduplication for chat messages. Used by `ConversationProcessor` |
| `tts_utils.py` | Text pre-processing before TTS — abbreviation expansion, number normalisation, character sanitisation |

Nothing here imports from `cognitive/`, `processing/`, `generation/`, `memory/`, `models/`, `output/`, or `input/`. No application state stored here.