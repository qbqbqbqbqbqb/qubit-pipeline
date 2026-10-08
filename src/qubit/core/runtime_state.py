"""Runtime state flags and async events for the application lifecycle."""

import asyncio
from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """
    Boolean feature toggles for the application.

    Using a typed dataclass instead of a plain dict means a typo in a flag
    name is an AttributeError immediately rather than a silent True/False
    default that bypasses the gate. Add new flags here when new features
    are gated — never use ad-hoc string keys on RuntimeState.features.
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


class RuntimeState:
    """Shared mutable state for the running application."""

    def __init__(self):
        self.shutdown = asyncio.Event()
        self.start = asyncio.Event()
        self.ai_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
        self.features = FeatureFlags()
