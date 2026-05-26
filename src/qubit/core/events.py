"""
Domain event definitions for the entire Qubit pipeline.

All significant occurrences in the system (user input, decisions, generations,
memory operations, etc.) are represented as immutable dataclass events and
communicated exclusively through the EventBus.

Base Event provides the minimal common structure.
Specialized events add the fields required by their consumers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.qubit.prompting.injections import PromptInjection
from src.qubit.prompting.prompt_assembler import PromptAssembler


@dataclass
class Event:
    """
    Base event for all domain events in the system.

    Attributes:
        type: String identifier used for routing on the EventBus
              (e.g. "twitch_chat_processed", "kick_chat_processed", "response_prompt", "response_generated").
        timestamp: ISO 8601 timestamp when the event was created.
        data: Arbitrary payload. Specific event types usually expose
              typed fields in addition to (or instead of) using this dict.
    """
    type: str
    timestamp: str
    data: Dict[str, Any]

@dataclass
class TwitchEvent(Event):
    pass


class KickEvent(Event):
    pass


@dataclass
class TwitchChatEvent(TwitchEvent):
    user: str
    text: str

@dataclass
class TwitchSubscriptionEvent(TwitchEvent):
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None

@dataclass
class TwitchRaidEvent(TwitchEvent):
    user: str
    viewers: int

@dataclass
class TwitchFollowEvent(TwitchEvent):
    user: str
    followed_at: str

@dataclass
class YoutubeEvent(Event):
    video_id: str
    title: str
    channel: str

@dataclass
class KickChatEvent(KickEvent):
    user: str
    text: str

@dataclass
class KickSubscriptionEvent(KickEvent):
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None

@dataclass
class KickRaidEvent(KickEvent):
    user: str
    viewers: int

@dataclass
class KickFollowEvent(KickEvent):
    user: str
    followed_at: str

@dataclass
class ModeratedEvent(Event):
    user: str
    text: str
    reason: str

@dataclass
class SpeechEvent(Event):
    text: str

@dataclass
class MonologueEvent(Event):
    user: str
    prompt: str

@dataclass
class InputEvent(Event):
    source: str
    text: str

@dataclass
class ResponsePromptEvent(Event):
    user: str
    source: str
    prompt: str

@dataclass
class ResponseGeneratedEvent(Event):
    prompt: str
    source: str
    response: str

@dataclass
class PromptAssemblyEvent(Event):
    assembler: PromptAssembler
    user: str
    prompt_text: str
    contributions: List[PromptInjection] = field(default_factory=list)

@dataclass
class MiscInputEvent(Event):
    user: str
    prompt: Optional[str] = None
