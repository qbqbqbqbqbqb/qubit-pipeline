# cognitive/

Decides what Qubit does next. Nothing else in the codebase makes that call.

Takes filtered input via `ActivityTracker`, runs a scored proposal cycle across all behaviours every 5 seconds, and publishes the winner as a `ResponsePromptEvent`. The loop runs continuously regardless of TTS state — output queuing and staleness are handled downstream by `OutputCoordinator`.

| File | What it does |
|---|---|
| `orchestrator.py` | Owns the 5s decision loop. Wires `ActivityTracker` and `DecisionEngine`. Gates `_handle_input` on `processing_active` — no new messages enter after end_stream |
| `priority_queue.py` | Scored queue for pending chat and STT messages |

## activity/

State only — no decision logic lives here.

| File | What it does |
|---|---|
| `activity_tracker.py` | Coordinates busyness score, input queue, and community event queue |
| `busyness.py` | Chat busyness as a scalar value |
| `community_event_queue.py` | Pending raid / gift / follow reactions |
| `event_adapter.py` | Translates raw events into the fields `ActivityTracker` needs |

## behaviours/

Each behaviour returns a scored proposal or `None`.

| File | What it does |
|---|---|
| `base.py` | Abstract base. Defines the proposal contract |
| `chat_response.py` | Proposes a response to the top pending chat or STT message |
| `community.py` | Proposes a reaction to a pending raid, gift, or follow |
| `frontend_monologue.py` | Proposes a monologue from a frontend trigger (`start`, `random_fact`, `end_stream`) |
| `idle_monologue.py` | Proposes a spontaneous monologue when chat is quiet |
| `topic_selector.py` | Picks a topic for idle monologues |

## decision/

| File | What it does |
|---|---|
| `decision_engine.py` | Builds context, collects proposals, delegates to arbiter and executor |
| `decision_executor.py` | Turns the winning proposal into published events |
| `idle_quota_tracker.py` | Keeps idle monologue share near 30% (`TARGET_SHARE`) over a 20-entry sliding window. `CATCHUP_BONUS = 5.0` guarantees a win when under quota |
| `proposal_arbiter.py` | Scores and ranks proposals via `BEHAVIOR_WEIGHTS`. Picks the winner |

## Adding a behaviour

1. Create `behaviours/my_behaviour.py` subclassing `Behavior`
2. Implement `tick(context) -> dict | None`
3. Register an instance in `DecisionEngine.__init__`
4. Set its weight in `ProposalArbiter.BEHAVIOR_WEIGHTS`