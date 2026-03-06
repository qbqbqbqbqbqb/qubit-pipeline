import asyncio
import os
import signal
import sys

from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

from src.qubit.input.monologue_input_handler import MonologueInputHandler
from src.qubit.core.signals import Signals
from src.qubit.core.server import WebSocketServer
from src.qubit.utils.log_utils import get_logger
from src.qubit.core.event_bus import event_bus
from src.qubit.input.input_handler import InputHandler
from src.qubit.input.input_moderation_handler import ModerationHandler
from src.qubit.input.monologue_gen import MonologueScheduler
from src.qubit.input.twitch.listener import TwitchListener
from src.qubit.models.async_hf_model_manager import AsyncHuggingFaceLLM
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.qubit.models.model_manager import ModelManager
from src.qubit.output.obs_handler import OBSHandler
from src.qubit.output.output_handler import OutputHandler
from src.qubit.output.tts_handler import TTSHandler
from src.qubit.processing.prompt_builder import LLMPromptHandler
from src.qubit.processing.prompt_dispatcher import PromptDispatcher 
from config.env_config import settings
from src.qubit.models.model_registry import MODEL_REGISTRY


logger = get_logger(__name__)

def setup_signal_handlers(signals):
    """
    Sets up signal handlers for graceful shutdown on SIGINT and SIGTERM.

    Args:
        signals (Signals): The signals object used for termination flags.
    """
    loop = asyncio.get_running_loop()

    def handle(sig, frame):
        sig_name = signal.Signals(sig).name
        logger.info(f"Received signal {sig_name}, shutting down...")
        signals.terminate.set()

    try:
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, lambda: handle(signal.SIGINT, None))
        loop.add_signal_handler(signal.SIGTERM, lambda: handle(signal.SIGTERM, None))
    except NotImplementedError:
        signal.signal(signal.SIGINT, handle)
        signal.signal(signal.SIGTERM, handle)


async def main():

    signals = Signals()

    ws_server = WebSocketServer(signals=signals, host='localhost', port=8765)
    server = await ws_server.start()

    setup_signal_handlers(signals)

    signals.twitch_enabled.set()
    signals.youtube_enabled.set()
    signals.kick_enabled.set()
    signals.monologue_enabled.set()

    # for input
    signals.chat_enabled.set()
    signals.raid_enabled.set()
    signals.follow_enabled.set()
    signals.subs_enabled.set()

    llm_client = AsyncHuggingFaceLLM(ModelManager.get_instance(), max_tokens=150)
    dispatcher = PromptDispatcher(llm_client)

    llm_handler = LLMPromptHandler(dispatcher=dispatcher)

    input_handler = InputHandler(max_age_seconds=30, prompt_handler=llm_handler)
    monologue_input_handler = MonologueInputHandler(max_age_seconds=30, prompt_handler=llm_handler)

    event_bus.subscribe("twitch_chat_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_subscription_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_raid_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_follow_processed", input_handler.handle_event)

    moderation_handler = ModerationHandler()
    event_bus.subscribe("twitch_chat", moderation_handler.handle_event)
    event_bus.subscribe("twitch_subscription", moderation_handler.handle_event)
    event_bus.subscribe("twitch_raid", moderation_handler.handle_event)
    event_bus.subscribe("twitch_follow", moderation_handler.handle_event)

    monologue_scheduler = MonologueScheduler(dispatcher=dispatcher, inactivity_timeout=120, monologue_enabled=signals.monologue_enabled)
    for event_type in llm_handler.builders.keys():
        event_bus.subscribe(event_type, monologue_scheduler.notify_activity)
    event_bus.subscribe("monologue_prompt", monologue_input_handler.handle_event)

    tts_handler = TTSHandler()
    obs_Handler = OBSHandler(settings=settings)
    output_handler = OutputHandler(
        tts_handler=tts_handler,
        obs_handler=obs_Handler
    )

    twitch_listener = TwitchListener(settings=settings, twitch_enabled=signals.twitch_enabled, chat_enabled=signals.chat_enabled,
                                     raid_enabled=signals.raid_enabled, follow_enabled=signals.follow_enabled, subs_enabled=signals.subs_enabled)
    asyncio.create_task(twitch_listener.listen(event_bus))
    
    logger.info("System initialized, waiting for events...")
    await signals.terminate.wait() # do i want this idk lol
    server.close()
    await server.wait_closed()
    sys.exit()

asyncio.run(main())