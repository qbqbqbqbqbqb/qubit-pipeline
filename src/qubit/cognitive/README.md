# Cognitive Layer

The **CognitiveService** is the central brain of Qubit.  
It decides:
- When to trigger monologues (low activity **or** random chance)
- When to respond to chat/STT messages
- When to stay silent

## Architecture

```mermaid
flowchart TD
    subgraph Inputs ["Input Events"]
        A[twitch_chat_processed]
        B[stt_processed]
        C[user_event_follow<br/>subscription<br/>raid]
    end

    subgraph Cognitive ["Cognitive Layer"]
        Service["**CognitiveService**<br/>(thin orchestrator)"]
        Tracker["**ActivityTracker**<br/>(score + input routing)"]
        Queue["**InputPriorityQueue**<br/>(STT 10× • quality • recency)"]
        Engine["**DecisionEngine**<br/>(runs every 5s)"]
        Behaviors["**behaviors/**<br/>IdleMonologueBehavior<br/>ChatResponseBehavior"]
    end

    subgraph Output ["Output"]
        Bus[EventBus]
        Pipeline[Pipeline<br/>→ PromptDispatcher → LLM → TTS/OBS]
    end

    A & B & C --> Service
    Service --> Tracker
    Tracker --> Queue
    Tracker --> Engine
    Engine --> Behaviors
    Behaviors --> Engine
    Engine --> Bus
    Bus --> Pipeline

    style Service fill:#4ade80,stroke:#166534
    style Engine fill:#60a5fa,stroke:#1e40af