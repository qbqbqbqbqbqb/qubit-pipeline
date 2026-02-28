import asyncio
import os
import signal
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

from scripts2.utils.log_utils import get_logger
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

async def main():
    terminate_event = asyncio.Event()
    twitch_enabled = asyncio.Event()
    twitch_enabled.set()

    llm_client = AsyncHuggingFaceLLM(ModelManager.get_instance(), max_tokens=150)
    dispatcher = PromptDispatcher(llm_client)

    llm_handler = LLMPromptHandler(dispatcher)

    input_handler = InputHandler(max_age_seconds=30, prompt_handler=llm_handler)

    event_bus.subscribe("twitch_chat_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_subscription_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_raid_processed", input_handler.handle_event)
    event_bus.subscribe("twitch_follow_processed", input_handler.handle_event)

    moderation_handler = ModerationHandler()
    event_bus.subscribe("twitch_chat", moderation_handler.handle_event)
    event_bus.subscribe("twitch_subscription", moderation_handler.handle_event)
    event_bus.subscribe("twitch_raid", moderation_handler.handle_event)
    event_bus.subscribe("twitch_follow", moderation_handler.handle_event)

    monologue_scheduler = MonologueScheduler(dispatcher, inactivity_timeout=120, terminate_event=terminate_event)
    for event_type in llm_handler.builders.keys():
        event_bus.subscribe(event_type, monologue_scheduler.notify_activity)
    event_bus.subscribe("monologue_prompt", llm_handler.handle_event)

    tts_handler = TTSHandler()
    obs_Handler = OBSHandler(settings=settings)
    output_handler = OutputHandler(
        tts_handler=tts_handler,
        obs_handler=obs_Handler
    )

    twitch_listener = TwitchListener(settings, terminate_event)
    asyncio.create_task(twitch_listener.listen(event_bus, twitch_enabled))
    
    logger.info("System initialized, waiting for events...")
    await terminate_event.wait()

asyncio.run(main())