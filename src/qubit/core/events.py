from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.qubit.prompting.injections import PromptInjection
from src.qubit.prompting.prompt_assembler import PromptAssembler


@dataclass
class Event:
    type: str
    timestamp: str
    data: Dict[str, Any]


# Base Twitch/Kick events
@dataclass
class TwitchEvent(Event):
    pass

@dataclass
class KickEvent(Event):
    pass

# Chat Events
@dataclass
class TwitchChatEvent(TwitchEvent):
    user: str
    text: str

@dataclass
class KickChatEvent(KickEvent):
    user: str
    text: str

# Raid Events
@dataclass
class TwitchRaidEvent(TwitchEvent):
    user: str
    viewers: int

@dataclass
class KickRaidEvent(KickEvent):
    user: str
    viewers: int

# Subscription Events
@dataclass
class TwitchSubscriptionEvent(TwitchEvent):
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None

@dataclass
class KickSubscriptionEvent(KickEvent):
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None

# Follow Events
@dataclass
class TwitchFollowEvent(TwitchEvent):
    user: str
    followed_at: str

@dataclass
class KickFollowEvent(KickEvent):
    user: str
    followed_at: str

# From streamer events
@dataclass
class SpeechEvent(Event):
    text: str

# Random Events
@dataclass
class MonologueEvent(Event):
    user: str
    prompt: str

@dataclass
class MiscInputEvent(Event):
    user: str
    prompt: Optional[str] = None # TODO: to be implemented


# Qubit internal events
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

# Dead
@dataclass
class YoutubeEvent(Event):
    video_id: str
    title: str
    channel: str

@dataclass
class ModeratedEvent(Event):
    user: str
    text: str
    reason: str

@dataclass
class InputEvent(Event):
    source: str
    text: str
    