"""
<summary>
Runtime state flags and async events for the application lifecycle.
</summary>
"""

import asyncio
from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """
    <summary>
    Boolean feature toggles for the application.
    Using a typed dataclass ensures a typo in a flag name raises an AttributeError
    immediately rather than silently defaulting to True or False.
    Add new flags here when gating new features — never use ad-hoc string keys.
    </summary>
    """
    twitch: bool = True
    kick: bool = True
    stt: bool = True
    chat: bool = True
    raids: bool = True
    follow: bool = True
    subs: bool = True
    gifts: bool = True
    monologue: bool = True
    vtube_studio: bool = True
    png_output: bool = False
    memory_read: bool = True
    memory_write: bool = True


class RuntimeState:
    """
    <summary>
    Shared mutable state for the running application. Holds lifecycle events
    and the feature flag set.
    </summary>
    """

    def __init__(self):
        self.shutdown = asyncio.Event()
        self.start = asyncio.Event()
        self.ai_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
        self.features = FeatureFlags()
