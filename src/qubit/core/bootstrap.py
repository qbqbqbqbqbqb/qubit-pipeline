from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus

from src.qubit.core.server import WebSocketServerService
from src.qubit.input.twitch.listener import TwitchListener
from src.qubit.output.output_handler import OutputHandler
from src.qubit.output.tts_handler import TTSHandler
from src.qubit.output.obs_handler import OBSHandler

from src.qubit.processing.prompt_dispatcher import PromptDispatcher
from src.qubit.processing.prompt_builder import LLMPromptHandler
from src.qubit.processing.input_moderation_handler import ModerationHandler
from src.qubit.processing.input_handler import InputHandler
from src.qubit.processing.monologue_input_handler import AutonomousInputHandler

from src.qubit.memory.memory_service import MemoryService
from src.qubit.memory.memory_handler import MemoryHandler

from src.qubit.cognitive.cognitive_service import CognitiveService
from src.qubit.input.frontend_command_handler import FrontendCommandHandler

from src.qubit.models.model_manager import ModelManager
from src.qubit.models.async_hf_model_manager import AsyncHuggingFaceLLM
from config.env_config import settings


async def create_app():
    app = App()
    app.state = RuntimeState()
    app.event_bus = event_bus

    # ====================== CORE COMPONENTS ======================
    llm_client = AsyncHuggingFaceLLM(ModelManager.get_instance(), max_tokens=150)
    dispatcher = PromptDispatcher(llm_client)
    
    memory_service = MemoryService(dispatcher=dispatcher)
    memory_handler = MemoryHandler(memory_service)

    llm_handler = LLMPromptHandler(dispatcher=dispatcher)

    # ====================== PROCESSORS (EventProcessor) ======================
    moderation_handler = ModerationHandler()
    input_handler = InputHandler(
        max_age_seconds=30,
        prompt_handler=llm_handler,
        memory_handler=memory_handler
    )
    monologue_handler = AutonomousInputHandler(        
        max_age_seconds=30,
        prompt_handler=llm_handler,
        memory_handler=memory_handler
    )

    # ====================== COGNITIVE LAYER ======================
    cognitive = CognitiveService(inactivity_timeout=120)
    frontend_handler = FrontendCommandHandler()
 
    # ====================== INPUT / OUTPUT ======================
    twitch = TwitchListener(settings=settings)
    output_handler = OutputHandler(tts_handler=TTSHandler(), 
                                   obs_handler=OBSHandler(settings=settings),  
                                   memory_handler=memory_handler)

    ws_service = WebSocketServerService(host="0.0.0.0", port=8765)

    # ====================== REGISTER SERVICES ======================
    app.add_service(ws_service)
    app.add_service(memory_service)
    app.add_service(dispatcher)

    moderation_handler.register_subscriptions(app.event_bus)
    input_handler.register_subscriptions(app.event_bus)
    monologue_handler.register_subscriptions(app.event_bus)
    frontend_handler.register_subscriptions(app.event_bus)


    app.add_service(cognitive)
    app.add_service(twitch)
    app.add_service(output_handler)

    return app