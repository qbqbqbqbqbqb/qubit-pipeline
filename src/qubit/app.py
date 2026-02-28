import asyncio
import logging

from .config import get_settings
from .core.bus import EventBus
from .core.lifecycle import on_startup, on_shutdown
from .modules import twitch_chat, response_ai, tts_pipert, obs_websocket, monologue


async def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    bus = EventBus()

    modules = [
        twitch_chat.TwitchChatModule(settings, bus),
        response_ai.AIResponseModule(settings, bus),
        tts_pipert.TTSModule(settings, bus),
        obs_websocket.OBSModule(settings, bus),
        monologue.MonologueModule(settings, bus),
    ]

    await on_startup(modules)

    dispatcher = asyncio.create_task(bus.run())

    try:
        await asyncio.gather(*(m.run() for m in modules), return_exceptions=True)
    finally:
        await on_shutdown(modules)
        dispatcher.cancel()


if __name__ == "__main__":
    asyncio.run(main())