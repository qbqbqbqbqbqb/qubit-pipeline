from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Event:
    type: str
    timestamp: str
    data: Dict[str, Any]

@dataclass
class TwitchEvent(Event):
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
class KickEvent(Event):
    user: str
    reason: str

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
