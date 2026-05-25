# Output Layer

Owns final delivery of generated responses.

## Responsibilities

- Sanitise dialogue (banned words, bot name removal, etc.)
- Own the output queue + staleness logic
- Drive `ai_speaking` / `ai_thinking` state on `RuntimeState`
- Coordinate leaf handlers: TTS, OBS subtitles, optional VTube mouth animation

## Key Components

- `OutputCoordinator` — the `Service` that owns the queue and speaking state
- `DialogueSanitiser` (in `handlers/`)
- Leaf handlers in `output/handlers/`:
  - `tts.py`
  - `obs.py`
  - `vtube.py`
  - `sanitiser.py`

## Design Rules

- This layer is the **only** place that should set/clear `ai_speaking`.
- The coordinator coordinates — it does **not** contain synthesis or websocket logic.
- All actual work is delegated to the small pure handlers in `handlers/`.

## Flow

`ResponseGeneratedEvent` → sanitise + memory forward → queue → drain loop → call handlers → speaking state management
