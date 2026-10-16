"""
<summary>
Event dataclasses for the application's internal pub/sub system.
One dataclass per event type. This file is the single source of truth for the bus topology.
</summary>
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.qubit.prompting.injections import PromptInjection
from src.qubit.prompting.prompt_assembler import PromptAssembler


@dataclass
class Event:
    """
    <summary>Base event carrying a type, timestamp, and arbitrary data payload.</summary>
    """
    type: str
    timestamp: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Platform input events
# ---------------------------------------------------------------------------

@dataclass
class TwitchEvent(Event):
    """<summary>Base class for Twitch-originated events.</summary>"""


@dataclass
class KickEvent(Event):
    """<summary>Base class for Kick-originated events.</summary>"""


@dataclass
class TwitchChatEvent(TwitchEvent):
    """<summary>Chat message received from Twitch.</summary>"""
    user: str
    text: str


@dataclass
class KickChatEvent(KickEvent):
    """<summary>Chat message received from Kick.</summary>"""
    user: str
    text: str


@dataclass
class TwitchRaidEvent(TwitchEvent):
    """<summary>Raid incoming from Twitch.</summary>"""
    user: str
    viewers: int


@dataclass
class KickRaidEvent(KickEvent):
    """<summary>Raid incoming from Kick.</summary>"""
    user: str
    viewers: int


@dataclass
class TwitchSubscriptionEvent(TwitchEvent):
    """<summary>Subscription event from Twitch.</summary>"""
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None


@dataclass
class KickSubscriptionEvent(KickEvent):
    """<summary>Subscription event from Kick.</summary>"""
    user: str
    tier: str
    sub_type: str
    sub_message: Optional[str] = None


@dataclass
class TwitchFollowEvent(TwitchEvent):
    """<summary>Follow event from Twitch.</summary>"""
    user: str
    followed_at: str


@dataclass
class KickFollowEvent(KickEvent):
    """<summary>Follow event from Kick.</summary>"""
    user: str
    followed_at: str


# ---------------------------------------------------------------------------
# Streamer input events
# ---------------------------------------------------------------------------

@dataclass
class SpeechEvent(Event):
    """<summary>Speech-to-text input from the streamer.</summary>"""
    text: str


# ---------------------------------------------------------------------------
# Cognitive / generation events
# ---------------------------------------------------------------------------

@dataclass
class MonologueEvent(Event):
    """<summary>Autonomous monologue prompt trigger from the cognitive layer.</summary>"""
    user: str
    prompt: str


@dataclass
class ResponsePromptEvent(Event):
    """<summary>Prompt assembled and ready for LLM generation.</summary>"""
    user: str
    source: str
    prompt: str


@dataclass
class ResponseGeneratedEvent(Event):
    """<summary>LLM response ready for output handling.</summary>"""
    prompt: str
    source: str
    response: str


@dataclass
class PromptAssemblyEvent(Event):
    """<summary>Prompt assembly in progress. Carries the assembler and any contributed injections.</summary>"""
    assembler: PromptAssembler
    user: str
    prompt_text: str
    contributions: List[PromptInjection] = field(default_factory=list)
