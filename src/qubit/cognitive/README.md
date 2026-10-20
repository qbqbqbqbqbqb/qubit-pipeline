# cognitive/

The decision layer. The only part of the application that decides what Qubit does next.

## Responsibility

Receives filtered input (via `ActivityTracker`), runs a scored proposal cycle across registered behaviours, and publishes the winning action as a `ResponsePromptEvent` or `MonologueEvent`. Nothing else in the codebase is permitted to make that decision.

## Files

| File | Responsibility |
|---|---|
| `orchestrator.py` | `CognitiveOrchestrator` — `Service` that owns the decision loop tick; wires `ActivityTracker` and `DecisionEngine` |
| `priority_queue.py` | `InputPriorityQueue` — scored queue for pending chat and STT messages |

## Sub-packages

### `activity/`
Pure state holders for the cognitive context. No decision logic.

| File | Responsibility |
|---|---|
| `activity_tracker.py` | Coordinates busyness score, input queue, and community event queue; used only by `CognitiveOrchestrator` and `DecisionEngine` |
| `busyness.py` | `ActivityScore` — scalar representing how busy chat currently is |
| `community_event_queue.py` | Queue for pending raid / gift / follow reactions |
| `event_adapter.py` | Translates raw `Event` objects into the typed fields `ActivityTracker` needs; isolates field-shape knowledge from the tracker |

### `behaviours/`
Pluggable decision strategies. Each returns a scored proposal or `None`.

| File | Responsibility |
|---|---|
| `base.py` | `Behavior` — abstract base; defines the proposal contract |
| `chat_response.py` | Proposes a response to the highest-priority chat or STT message |
| `community.py` | Proposes a reaction to a pending community event (raid, gift, follow) |
| `frontend_monologue.py` | Proposes a monologue triggered by a manual frontend button press |
| `idle_monologue.py` | Proposes a spontaneous monologue when chat is quiet |
| `topic_selector.py` | Utility for selecting a topic when `idle_monologue` runs |

### `decision/`
Wires proposals into a final action.

| File | Responsibility |
|---|---|
| `decision_engine.py` | Builds context, collects proposals, delegates scoring and execution |
| `decision_executor.py` | Turns a winning proposal into published events |
| `idle_quota_tracker.py` | Rate-limits idle monologues across the session |
| `proposal_arbiter.py` | Scores and ranks proposals using `BEHAVIOR_WEIGHTS`; picks a winner |

## Adding a behaviour

1. Create `behaviours/my_behaviour.py` subclassing `Behavior`.
2. Implement `tick(context) -> dict | None`.
3. Register an instance in `DecisionEngine.__init__`.
4. Set its weight in `ProposalArbiter.BEHAVIOR_WEIGHTS`.
