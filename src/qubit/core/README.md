# Core / Runtime Layer

This package contains the fundamental runtime and wiring components.

## Responsibilities

- Application lifecycle (`App`, `Service`)
- Event distribution (`EventBus`)
- Shared mutable runtime state (`RuntimeState`)
- Central bootstrap / dependency wiring (`bootstrap.py`)
- Long-running service orchestration

## Key Types

| Type                | Role                                      | Notes |
|---------------------|-------------------------------------------|-------|
| `Service`           | Base for anything that owns a `_run` loop or connection | Has `start`/`stop` + lifecycle |
| `EventProcessor`    | Pure reactor that reacts to events        | No loop, just `handle_event` |
| `EventBus`          | Central pub/sub                           | Global singleton in most runs |
| `RuntimeState`      | Single source of truth for flags + `ai_*` state | `features`, `ai_speaking`, `ai_thinking`, etc. |
| `App`               | Lightweight container of services         | Mostly for wiring and shutdown coordination |

## Design Rules

- Only `Runtime` + `WebSocketServerService` should own long-running loops in core.
- `RuntimeState` must be the **only** place that holds cross-cutting boolean/timing state.
- `bootstrap.py` is intentionally the only place that knows how all the pieces are wired together.

## See Also

- `bootstrap.py` for the current wiring
- Individual layer READMEs for how their components are registered
