from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

class EventType(Enum):
    CHAT_MESSAGE        = auto()
    AI_RESPONSE_READY   = auto()
    TTS_FINISHED        = auto()
    MONOLOGUE_TRIGGER   = auto()
    SHUTDOWN            = auto()


@dataclass
class Event:
    type: EventType
    payload: Any = None
    source: str = "unknown"