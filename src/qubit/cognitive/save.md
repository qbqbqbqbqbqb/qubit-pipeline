# Cognitive Layer

The cognitive layer is the only place in the pipeline allowed to decide
Qubit's next high-level action: respond to chat/STT, react to a community
event, speak an autonomous monologue, or stay silent. Every other layer is
strictly downstream — generation only executes intents it receives,
output only speaks what it's told, input processing only filters and
forwards raw events. All the "should I / what should I do" logic lives here.

## Files

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
  README.md
```

Split this way deliberately: `activity_tracker.py` and `decision_engine.py`
had each accumulated 2-3 genuinely different responsibilities as the
feature set grew (event interpretation, busyness math, event queuing;
scoring, quota tracking, event publishing). Both are now thin coordinators
— the actual logic lives in single-purpose collaborators that can be read
and tested in isolation. `behaviours/`, `priority_queue.py`, and
`cognitive_orchestrator.py` were already right-sized and weren't touched by
this split.

## The decision cycle

`CognitiveOrchestrator._run()` calls `DecisionEngine.run_decision_cycle()`
roughly every 5 seconds (`DECISION_INTERVAL_SECONDS`), skipped when the app
hasn't started or output is currently busy speaking (see
[Known gaps](#known-gaps-and-assumptions) — that speaking check is a
placeholder). Each cycle:

1. **Time-based activity decay** runs first (`ActivityTracker.apply_time_decay()`
   → `ActivityScore.apply_time_decay()`).
2. **Context is built** — activity score, the chat queue, pending community
   events, staged frontend command (peeked, not consumed yet), feature
   flags, and whether idle monologue is currently under its quota
   (`IdleQuotaTracker.is_under_quota()`).
3. **Every enabled behavior proposes**, or returns `None`.
4. **`ProposalArbiter.select_winner()` picks the highest-scoring proposal**
   (see [Scoring](#scoring-weights-and-priority-tiers)).
5. **`DecisionExecutor.execute()` runs the winner** — publishes an event,
   updates its own speech timers, and only *then* clears whatever state
   that decision consumed (frontend command consumed, matched community
   events removed, chat message removed from the queue). `DecisionEngine`
   then updates the winning behavior's `last_triggered` and records the
   outcome with `IdleQuotaTracker`.

Step 5's "clear on execution, not on read" pattern matters: if a proposal
peeked at in step 2 doesn't end up winning (e.g. a raid arrives the same
moment a frontend command was staged), that state must still be there to
compete again next cycle instead of being silently lost.

## Scoring: weights and priority tiers

*(Lives in `decision/proposal_arbiter.py`.)*

Each behavior returns a proposal score normalized to roughly 0–1 — "how
much do I want this, on my own internal scale." Two things then decide who
actually wins, layered on top of that:

**`ProposalArbiter.BEHAVIOR_WEIGHTS`** — the single table that says how much
a maxed-out proposal from one behavior matters relative to another:

```python
BEHAVIOR_WEIGHTS = {
    "chat_response": 1.0,
    "frontend_start": 0.75,
    "frontend_random_fact": 0.75,
    "idle_monologue": 0.4,
    "community_event": 1.0,
}
```

**Priority tiers** — a flat `PRIORITY_TIER_BONUS` (10.0) added per tier
point, which dwarfs any weighted score. Tiers decide outright priority
classes; weights only break ties *within* a tier.

| Tier | Who | Why |
|---|---|---|
| 2 | `community_event` (raid/gift/follow) | Rarest, always wins — even over live STT. |
| 1 | `chat_response` when the winning message is live STT | Streamer's own voice should never lose to text chat. |
| 0 | everything else | Normal competition, decided by weight × normalized score. |

To retune *how much idle monologue competes with chat* in the normal case,
change `BEHAVIOR_WEIGHTS["idle_monologue"]` in `proposal_arbiter.py`. To
change *whether raids beat STT*, that's a tier question, not a weight
question — don't try to solve it with weights, it won't work (weights
can't cross a tier boundary; that's the point).

`ProposalArbiter.select_winner()` also accepts `extra_bonus_by_reason`, a
one-off additive bonus keyed by a proposal's "reason" for that cycle —
this is how `DecisionEngine` injects `IdleQuotaTracker`'s catch-up bonus
without the arbiter needing to know anything idle-specific.

## "Chat busyness" — `activity_score`

*(Lives in `activity/busyness.py`, exposed via `ActivityTracker.activity_score`.)*

`ActivityScore.value` drives `ChatResponseBehavior`'s selectivity curve and
`IdleMonologueBehavior`'s eagerness curve. It is driven **only** by written
chat messages (`user_input_chat_message`). STT and community events
(raids/gifts/follows) do not touch it — they win through the tier system
above, completely independent of how busy chat looks. Earlier in
development STT fed into this score too, which made heavy STT talking
suppress chat responsiveness even when chat itself was quiet — that
coupling has been removed.

`activity_score` decays two ways, and both run:
- **Per chat message** (`ActivityScore.register_chat_message`) — the
  existing `value = value * 0.85 + weight` compounding.
- **Per decision cycle, based on wall-clock time**
  (`ActivityScore.apply_time_decay`) — so genuine silence relaxes the score
  back down instead of freezing it at its last value. This only runs while
  decision cycles are actually executing; if cycles are paused (app not
  started, or output busy), decay pauses too — time spent speaking doesn't
  count as "silence."

## Idle monologue quota (target: ~30% of chat+monologue decisions)

*(Lives in `decision/idle_quota_tracker.py`.)*

Left alone, idle monologue's own eagerness curve gets crushed at high chat
activity — its random "spark gate" only lets it propose on ~17% of ticks,
and even then its score ceiling sits well below chat's floor. To hold a
genuine ~30% share regardless of how busy chat is, `IdleQuotaTracker`
tracks the last 20 chat-vs-monologue outcomes (ignoring frontend commands
and community events — they're not part of this ratio) and reports
**catch-up mode** whenever the trailing share is below `TARGET_SHARE`
(0.30):

- `IdleMonologueBehavior` bypasses its own cooldown/spark gates entirely
  (`idle_quota_catchup` in context, set by `DecisionEngine` from
  `IdleQuotaTracker.is_under_quota()`).
- `ProposalArbiter` adds a decisive `CATCHUP_BONUS` (5.0) to idle's score
  via `extra_bonus_by_reason` — large enough to beat any normal tier-0
  proposal, small enough to still lose to STT (tier 1) or community events
  (tier 2).

Once the trailing window is back at/above target, catch-up switches off and
idle goes back to behaving exactly as its own curves define — rare and
organic, not a metronome.

A softer, purely multiplicative correction was tried first and verified (by
simulation) to *not* reach target — it settles into a permanent steady-state
deficit, because a bounded multiplier can't close a large score-magnitude
gap. Only a guaranteed win during catch-up actually converges.

## Feature toggles

*(Resolved in `activity/event_adapter.py`, applied in `activity/activity_tracker.py`.)*

| Toggle | Gates | Where |
|---|---|---|
| `stt` | Live voice input | `EventAdapter.FEATURE_FLAG_BY_SOURCE` |
| `chat` | Written chat messages | same |
| `raids` | Raids, follows, and non-gift subscriptions | same (default bucket — see caveats) |
| `gifts` | Subscriptions where `sub_type` indicates a gift | `EventAdapter.feature_flag_for` (inspects `sub_type`, no separate gift event exists) |
| `monologue` | Autonomous idle chatter (`IdleMonologueBehavior` only) | `IdleMonologueBehavior.tick` + dampens `activity_score` growth generally |

A toggle being off means the input is **dropped entirely** at
`ActivityTracker.handle_input()` — not scored, not queued, not just
excluded from the activity number. (Earlier, `stt` off only zeroed its
score contribution but still let the message through to be answered — that
was a bug, now fixed.)

## Community events (raids / gifts / follows)

*(Queued in `activity/community_event_queue.py`, proposed by `behaviours/community_event.py`.)*

`user_event_raid`, `user_event_subscription`, and `user_event_follow` are
routed to `ActivityTracker.events` (a `CommunityEventQueue`) instead of the
text-based priority queue — they don't have meaningful chat "text" and
shouldn't be scored by chat quality heuristics. `CommunityEventBehavior`
reads whatever is currently pending and collates it into one reaction:

- One event pending → one description.
- Multiple pending → `"several community events at once: ..."` joining all
  of them. There's no explicit spam/burst detection — it just reacts to
  whatever accumulated since the last cycle, so a burst landing within one
  ~5s decision cycle is naturally batched, and a lone event is a
  "collation" of one.

Field extraction (`EventAdapter.extract_event_detail`) matches the real
dataclasses in `core/events.py`: `TwitchRaidEvent`/`KickRaidEvent` →
`user`, `viewers`; `TwitchSubscriptionEvent`/`KickSubscriptionEvent` →
`user`, `tier`, `sub_type` (no numeric gift count exists in the schema — a
gift is represented by `sub_type`, not a count);
`TwitchFollowEvent`/`KickFollowEvent` → `user`.

## Known gaps and assumptions

- **`CognitiveOrchestrator._is_output_busy()` is a placeholder.** It
  best-effort checks `app.state.runtime.ai_speaking` via `getattr` and
  falls back to "not busy" if that path doesn't exist — meaning the gate is
  currently a no-op until wired to whatever `RuntimeState`/
  `OutputCoordinator` actually exposes.
- **`CommunityEventBehavior`/`DecisionExecutor` reuse `MonologueEvent`**
  rather than a dedicated event type, since no `CommunityEventPromptEvent`
  exists in `core/events.py`. Downstream can distinguish it via
  `event.data["kind"] == "community_event"`, but not by event type.
- **Follows and non-gift subscriptions are bundled under the `raids`
  toggle**, since only `stt`/`chat`/`raids`/`monologue`/`gifts` were
  specified. Split further if the frontend grows dedicated switches.
- **`EventAdapter.GIFT_SUB_TYPES = {"gift"}`** is a guess at what Input
  Processing actually puts in `sub_type` for a gifted sub. Confirm against
  the real value and adjust if it differs (e.g. `"gift_sub"`).
- **`IdleQuotaTracker.CATCHUP_BONUS` (5.0) and the whole quota mechanism**
  were validated by a standalone simulation of the scoring math, not by
  running the actual event loop end-to-end. Worth watching the logs on a
  real stream to confirm the ~30% actually holds under real traffic
  patterns.
- **This file split changed import paths.** If anything else in the repo
  imports `src.qubit.cognitive.activity_tracker` or
  `src.qubit.cognitive.decision_engine` directly, update those to
  `src.qubit.cognitive.activity.activity_tracker` and
  `src.qubit.cognitive.decision.decision_engine` — `cognitive_orchestrator.py`
  is already updated, but nothing else in this codebase has been searched
  for other references.