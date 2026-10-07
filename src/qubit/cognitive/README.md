# Qubit Pipeline — Architecture

Qubit is an AI VTuber / streaming co-host. This document covers the overall
pipeline shape and does a full deep-dive on the two layers actually built
out in detail so far: **Cognitive** (decision-making) and **Output**
(speech/visuals). Input Processing, Generation, and Memory are described
only at the level inferable from event contracts and docstrings elsewhere
in the code — I don't have those layers' actual implementations in front of
me, so treat those sections as "what the boundary looks like from outside,"
not verified internals.

## Pipeline overview

```
 Twitch/Kick chat, STT, raids, subs, follows, frontend commands
        │
        ▼
 ┌─────────────────┐
 │ Input Processing │  filters/normalizes raw platform events
 └────────┬─────────┘
          │ stt_processed / twitch_chat_processed / kick_chat_processed /
          │ user_event_raid / user_event_subscription / user_event_follow /
          │ frontend_command
          ▼
 ┌─────────────────┐
 │    Cognitive     │  the ONLY layer allowed to decide what happens next
 └────────┬─────────┘
          │ response_prompt / monologue_prompt
          ▼
 ┌─────────────────┐
 │    Generation    │  turns a prompt into actual dialogue text (LLM)
 └────────┬─────────┘
          │ response_generated
          ▼
 ┌─────────────────┐
 │      Output      │  sanitises, queues, speaks (TTS/OBS/VTube/PNG)
 └──────────────────┘
```

**Memory** sits off to the side as a cross-cutting sink — `OutputCoordinator`
forwards every sanitised response to `memory_writer.handle_event()` rather
than memory sitting inline in the main flow.

Each layer's docstrings state a hard boundary, worth restating since it's
the whole point of the split:
- Input Processing only filters and forwards raw events.
- Cognitive is the only place allowed to decide *whether* and *what* to say
  — it must not contain generation or output logic.
- Generation only executes intents it receives — it doesn't decide to speak.
- Output only speaks what it's told and coordinates leaf handlers (TTS,
  OBS, VTube Studio, PNG) — it must not contain synthesis/websocket/
  sanitiser implementation details itself, those live in handler classes.

---

## Cognitive layer

The only place that decides: respond to chat/STT, react to a community
event, speak an autonomous monologue, or stay silent.

### Files

```
cognitive/
  activity/
    activity_tracker.py        # thin coordinator over the three below
    busyness.py                 # ActivityScore: chat-only activity_score scalar + decay
    community_event_queue.py    # pending raid/gift/follow reactions: add/peek/remove
    event_adapter.py            # raw Event -> canonical source/flag/text/detail
  decision/
    decision_engine.py          # thin coordinator: run the cycle, build context, delegate
    proposal_arbiter.py         # BEHAVIOR_WEIGHTS, PRIORITY_TIER_BONUS, pick winner
    idle_quota_tracker.py       # decision history, is_under_quota, catch-up bonus
    decision_executor.py        # publish event, clear consumed state, own speech timers
  behaviours/
    base.py                     # Behavior ABC — the contract every behavior implements
    chat_response.py            # proposes answering the best pending chat/STT message
    idle_monologue.py           # proposes autonomous, topic-less chatter
    frontend_monologue.py       # proposes a monologue when the operator triggers one
    community_event.py          # proposes reacting to raids/gifts/follows, collated
  priority_queue.py             # chat/STT queue — separate STT/chat buckets, hard TTL
  cognitive_orchestrator.py     # Service: owns the ticker, forwards input, stays dumb
```

`activity_tracker.py` and `decision_engine.py` are thin coordinators —
each had accumulated multiple responsibilities as the feature set grew and
was split into single-purpose collaborators that can be read and reasoned
about in isolation.

### The decision cycle

`CognitiveOrchestrator._run()` calls `DecisionEngine.run_decision_cycle()`
roughly every 5 seconds, skipped when the app hasn't started or output is
busy (see [Known gaps](#known-gaps-and-assumptions) — that speaking check
is currently a no-op placeholder). Each cycle:

1. **Time-based activity decay** runs first.
2. **Context is built** — activity score, the chat queue, pending community
   events, staged frontend command (peeked, not consumed), feature flags,
   and whether idle monologue is under its quota.
3. **Every enabled behavior proposes**, or returns `None`.
4. **`ProposalArbiter` picks the highest-scoring proposal.**
5. **`DecisionExecutor` runs the winner** — publishes an event, updates its
   own speech timers, and only *then* clears whatever state that decision
   consumed. `DecisionEngine` then updates the winning behavior's
   `last_triggered` and records the outcome for the quota ratio.

Step 5's "clear on execution, not on read" matters: a proposal peeked at in
step 2 that doesn't end up winning (e.g. a raid arrives the same moment a
frontend command was staged) must still be there to compete again next
cycle instead of being silently lost.

### Scoring: weights and priority tiers

Each behavior returns a proposal score normalized to roughly 0–1 — how much
*it* wants this, on its own scale. Two things decide who wins:

**`ProposalArbiter.BEHAVIOR_WEIGHTS`** — how much a maxed-out proposal from
one behavior matters relative to another, for normal (tier-0) competition:

```python
BEHAVIOR_WEIGHTS = {
    "chat_response": 1.0,
    "frontend_start": 0.75,
    "frontend_random_fact": 0.75,
    "idle_monologue": 0.4,
    "community_event": 1.0,
}
```

**Priority tiers** — a flat `PRIORITY_TIER_BONUS` (10.0) per tier point,
which dwarfs any weighted score. Tiers decide outright priority classes;
weights only break ties *within* a tier.

| Tier | Who | Why |
|---|---|---|
| 2 | `community_event` (raid/gift/follow) | Rarest, always wins — even over live STT. |
| 1 | `chat_response` when the winning message is live STT | Streamer's own voice should never lose to text chat. |
| 0 | everything else | Normal competition: weight × normalized score. |

To retune how much idle competes with chat in the normal case, change
`BEHAVIOR_WEIGHTS["idle_monologue"]`. To change whether raids beat STT,
that's a tier question — weights can't cross a tier boundary by design.

### "Chat busyness" — `activity_score`

Drives `ChatResponseBehavior`'s selectivity curve and
`IdleMonologueBehavior`'s eagerness curve. Driven **only** by written chat
messages. STT and community events do not touch it — they win purely
through the tier system, independent of how busy chat looks. (Earlier, STT
fed into this score too, which made heavy STT talking suppress chat
responsiveness even when chat itself was quiet — removed.)

Decays two ways: per chat message (the usual compounding decay), and per
decision cycle based on wall-clock time — so genuine silence relaxes the
score back down instead of freezing it at its last value. Time-based decay
only runs while cycles execute; paused cycles (output busy) pause decay too.

### Idle monologue quota (target: ~30%)

Left alone, idle's own eagerness curve gets crushed at high chat activity —
its spark gate only fires ~17% of ticks, and even then its ceiling sits
below chat's floor. `IdleQuotaTracker` tracks the last 20 chat-vs-monologue
outcomes and enters **catch-up mode** whenever the trailing share drops
below 30%: `IdleMonologueBehavior` bypasses its own random gates, and
`ProposalArbiter` adds a decisive bonus (5.0 — enough to beat any tier-0
proposal, not enough to beat STT or community events). Once back at/above
target, catch-up switches off and idle behaves exactly as its curves define.

A softer multiplicative correction was tried first and verified (by
simulation) to *not* reach target — a bounded multiplier can't close a
large score-magnitude gap. Only a guaranteed win during catch-up converges.

### Feature toggles

| Toggle | Gates | Where |
|---|---|---|
| `stt` | Live voice input | `EventAdapter.FEATURE_FLAG_BY_SOURCE` |
| `chat` | Written chat messages | same |
| `raids` | Raids, follows, non-gift subscriptions | same (default bucket) |
| `gifts` | Subscriptions where `sub_type` indicates a gift | `EventAdapter.feature_flag_for` |
| `monologue` | Autonomous idle chatter | `IdleMonologueBehavior.tick` + dampens `activity_score` growth |

A toggle being off drops the input entirely at `ActivityTracker.handle_input()`
— not scored, not queued.

### Community events (raids / gifts / follows)

Routed to `ActivityTracker.events` (a `CommunityEventQueue`), not the
text-based priority queue — no meaningful chat "text" to score by quality.
`CommunityEventBehavior` collates whatever's pending into one reaction: a
single event gets one description, multiple pending get joined into one
message. No explicit spam detection — a burst landing within one ~5s cycle
is naturally batched.

Field extraction matches the real `core/events.py` dataclasses:
`TwitchRaidEvent`/`KickRaidEvent` → `user`, `viewers`;
`TwitchSubscriptionEvent`/`KickSubscriptionEvent` → `user`, `tier`,
`sub_type` (no numeric gift count exists — a gift is represented by
`sub_type`, not a count); `TwitchFollowEvent`/`KickFollowEvent` → `user`.

---

## Output layer

`OutputCoordinator` is the only place that drives `ai_speaking` state and
actually calls TTS/OBS/VTube Studio/PNG handlers. It receives
`ResponseGeneratedEvent`, sanitises the text (`DialogueSanitiser`), and
queues it for speaking.

### Two queues, priority-aware

`self.queue` (normal) and `self.priority_queue` (community-event reactions)
— the priority queue always drains first, and gets a much longer staleness
allowance (120s vs. 30s default) since raids/gifts/follows are rare and
shouldn't get dropped just for waiting behind a couple of chat responses.
Both are capped (`maxlen`) so a sustained output stall can't grow either
queue without bound.

Priority detection reads `event.data["kind"] == "community_event"` — the
marker Cognitive's `DecisionExecutor` sets. **This only works if Generation
forwards `data` through unchanged** when it builds `ResponseGeneratedEvent`
from the originating prompt event. Not confirmed against the actual
Generation code — if it builds `data` fresh instead of passing it through,
community events silently fall back to normal-priority handling.

### Staleness

Every item carries a timestamp from when it was queued; items older than
the applicable max age are dropped rather than spoken late. This is a
*different* staleness concern than anything in Cognitive — Cognitive's
tiers decide who gets proposed next; Output's staleness decides whether
enough real time has passed that saying something now would look wrong
(e.g. TTS fell behind).

---

## Known gaps and assumptions

- **`CognitiveOrchestrator._is_output_busy()` is a placeholder.** Best-effort
  checks `app.state.runtime.ai_speaking` and falls back to "not busy" if
  that path doesn't exist — the gate is currently a no-op until wired to
  whatever `RuntimeState`/`OutputCoordinator` actually exposes. This is also
  the deeper fix for output-queue growth under a stall — a queue cap is a
  backstop, not a substitute for throttling intake at the source.
- **Community-event priority in Output depends on Generation forwarding
  `event.data`** unchanged from the prompt event through to
  `ResponseGeneratedEvent`. Not verified — check the Generation layer.
- **`CommunityEventBehavior`/`DecisionExecutor` reuse `MonologueEvent`**
  rather than a dedicated event type, since no `CommunityEventPromptEvent`
  exists in `core/events.py`. Downstream can distinguish it via
  `event.data["kind"]`, not by event type.
- **Follows and non-gift subscriptions are bundled under the `raids`
  toggle** — only `stt`/`chat`/`raids`/`monologue`/`gifts` were specified.
- **`EventAdapter.GIFT_SUB_TYPES = {"gift"}`** is a guess at what Input
  Processing puts in `sub_type` for a gifted sub. Confirm the real value.
- **`IdleQuotaTracker.CATCHUP_BONUS` and the quota mechanism** were
  validated by standalone simulation of the scoring math, not the actual
  event loop end-to-end. Worth watching logs on a real stream.
- **`OutputCoordinator`'s existing chat/monologue detection**
  (`event.source in ("twitch_chat_processed", "kick_chat_processed")`)
  likely doesn't match what Cognitive actually sets (`"user_input_stt"` /
  `"user_input_chat_message"`) unless Generation rewrites `source` in
  between — unconfirmed, flagged separately from this refactor.
- **Import paths changed** when the cognitive layer was split:
  `src.qubit.cognitive.activity_tracker` → `src.qubit.cognitive.activity.activity_tracker`,
  `src.qubit.cognitive.decision_engine` → `src.qubit.cognitive.decision.decision_engine`.
  `cognitive_orchestrator.py` is updated; anything else in the repo
  importing the old paths needs the same update.