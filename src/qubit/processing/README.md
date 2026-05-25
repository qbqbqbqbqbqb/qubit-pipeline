# Input Processing Layer

This layer contains **pure** `EventProcessor`s that transform, filter, and normalise raw input events.

## Responsibilities

- Deduplication
- Staleness filtering
- Moderation
- Memory side-effects (forwarding to `MemoryWriter`)
- Converting certain events into high-level intents for the Cognitive or Generation layers

## Current Processors

| Processor                    | Trigger Events                          | Does |
|------------------------------|-----------------------------------------|------|
| `ConversationProcessor`      | `twitch_chat_processed`, subs, raids, follows | Dedup + staleness + memory forward |
| `AutonomousPromptProcessor`  | `monologue_prompt`, `start_message`     | Staleness + memory + emits `ResponsePromptEvent` |
| `ModerationProcessor`        | Raw chat events                         | Basic sanitisation / filtering |
| `FrontendCommandProcessor`   | Frontend commands                       | Normalises and emits events |

## Design Rules

- These are **pure reactors** — no loops, no queues.
- They should only publish events or forward to `MemoryWriter`.
- Prompt construction for monologues now lives here (emits `ResponsePromptEvent` directly).

## Naming

Use `*Processor` for anything in this layer.
