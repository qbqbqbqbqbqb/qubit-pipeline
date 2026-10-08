"""Event dataclasses for the application's internal pub/sub system.

One dataclass per event type. Keep this file as the single source of truth
for the bus topology — if an event type isn't defined here it shouldn't exist
on the bus. Dead or unimplemented event classes do not belong here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.qubit.prompting.injections import PromptInjection
from src.qubit.prompting.prompt_assembler import PromptAssembler


@dataclass
class Event:
    """Base event carrying a type, timestamp, and arbitrary data payload."""
    type: str
    timestamp: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Platform input events
# ---------------------------------------------------------------------------

@dataclass
class TwitchEvent(Event):
    """Base class for Twitch-originated events."""


@dataclass
class KickEvent(Event):
    """Base class for Kick-originated events."""


@dataclass
class TwitchChatEvent(TwitchEvent):
    """Chat message received from Twitch."""
    user: str
    text: str


@dataclass
class KickChatEvent(KickEvent):
    """Chat message received from Kick."""
    user: str
    text: str


@dataclass
class TwitchRaidEvent(TwitchEvent):
    """Raid incoming from Twitch."""
    user: str
    viewers: int


@dataclass
class KickRaidEvent(KickEvent):
    """Raid incoming from Kick."""
    user: str
    viewers: int


@dataclass
class TwitchSubscriptionEvent(TwitchEvent):
    """Subscription event from Twitch."""
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None


@dataclass
class KickSubscriptionEvent(KickEvent):
    """Subscription event from Kick."""
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None


@dataclass
class TwitchFollowEvent(TwitchEvent):
    """Follow event from Twitch."""
    user: str
    followed_at: str


@dataclass
class KickFollowEvent(KickEvent):
    """Follow event from Kick."""
    user: str
    followed_at: str


# ---------------------------------------------------------------------------
# Streamer input events
# ---------------------------------------------------------------------------

@dataclass
class SpeechEvent(Event):
    """Speech-to-text input from the streamer."""
    text: str


# ---------------------------------------------------------------------------
# Cognitive / generation events
# ---------------------------------------------------------------------------

@dataclass
class MonologueEvent(Event):
    """Autonomous monologue prompt trigger from the cognitive layer."""
    user: str
    prompt: str


@dataclass
class ResponsePromptEvent(Event):
    """Prompt assembled and ready for LLM generation."""
    user: str
    source: str
    prompt: str


@dataclass
class ResponseGeneratedEvent(Event):
    """LLM response ready for output handling."""
    prompt: str
    source: str
    response: str


@dataclass
class PromptAssemblyEvent(Event):
    """Prompt assembly complete, carrying the assembler and contributions."""
    assembler: PromptAssembler
    user: str
    prompt_text: str
    contributions: List[PromptInjection] = field(default_factory=list)
