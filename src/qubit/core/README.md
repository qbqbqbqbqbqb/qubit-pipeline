# core/

Application lifecycle and shared infrastructure. Everything else depends on this package; this package depends on nothing inside `qubit/`.

## Files

| File | Responsibility |
|---|---|
| `app.py` | `App` — top-level container; holds `state`, `event_bus`, and the service registry |
| `bootstrap.py` | Wires every service and processor together; the only place construction order is defined |
| `event_bus.py` | `EventBus` — async pub/sub; typed string event names, async handler dispatch |
| `event_processor.py` | `EventProcessor` — abstract base for stateless event consumers; subclasses declare `SUBSCRIPTIONS` |
| `events.py` | All typed `Event` dataclasses used across the application |
| `runtime.py` | `Runtime` — drives `asyncio` lifecycle; starts and stops services in registration order |
| `runtime_state.py` | `RuntimeState` + `FeatureFlags` — shared mutable state (lifecycle events, feature toggles) |
| `server.py` | `WebSocketServerService` — WebSocket server on `ws://0.0.0.0:8765`; bridges the frontend control panel to the event bus |
| `service.py` | `Service` — abstract base for long-lived async services; subclasses implement `start()` / `stop()` |

## Key invariants

- `FeatureFlags` is the single source of truth for every runtime toggle. Add new flags here, nowhere else.
- Events are the only permitted cross-layer communication. No service holds a direct reference to another service.
- `bootstrap.py` is the only file allowed to import from every layer. Keep it flat; construction logic does not belong elsewhere.
