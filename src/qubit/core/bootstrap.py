"""Wire up and return the fully constructed application instance."""

from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus

from src.qubit.core.server import WebSocketServerService

from src.qubit.input.twitch.listener import TwitchListener
from src.qubit.input.kick.listener import KickListener
from src.qubit.input.stt_listener import SpeechToTextListener
from src.qubit.input.frontend_command_processor import FrontendCommandProcessor

from src.qubit.output.coordinator import OutputCoordinator
from src.qubit.output.handlers.tts import TTSHandler
from src.qubit.output.handlers.obs import OBSHandler
from src.qubit.output.handlers.audio_player import AudioFilePlayer
from src.qubit.output.handlers.vtube import VtubeStudioHandler

from src.qubit.processing.moderation import ModerationProcessor
from src.qubit.processing.conversation import ConversationProcessor
from src.qubit.processing.autonomous import AutonomousPromptProcessor

from src.qubit.generation.coordinator import GenerationCoordinator

from src.qubit.memory.service import MemoryService
from src.qubit.memory.writer import MemoryWriter

from src.qubit.cognitive.orchestrator import CognitiveOrchestrator

from src.qubit.models.llm_service import LLMService
from src.qubit.models.model_registry import LLM_PROFILES

from config.env_config import settings


async def create_app():
    """Construct the application with all services, processors, and handlers wired together."""
    app = App()
    app.state = RuntimeState()
    app.state.features["vtube_studio"] = getattr(settings, "enable_vtube_studio", True)
    app.event_bus = event_bus

    llm_service = LLMService()
    for prof in LLM_PROFILES.values():
        llm_service.register_profile(prof)

    await llm_service.ensure_loaded("main")
    await llm_service.ensure_loaded("reflection")

    app.state.llm_service = llm_service

    generation_coordinator = GenerationCoordinator(llm_service=llm_service, main_profile="main")

    memory_service = MemoryService(llm_service=llm_service)
    memory_writer = MemoryWriter(
        memory_service,
        stt_speaker_name=getattr(settings, "stt_speaker_name", "Speaker")
    )

    moderation_processor = ModerationProcessor()
    conversation_processor = ConversationProcessor(
        max_age_seconds=30,
        memory_writer=memory_writer
    )
    autonomous_prompt_processor = AutonomousPromptProcessor(
        max_age_seconds=30,
        memory_writer=memory_writer,
        event_bus=event_bus
    )

    cognitive = CognitiveOrchestrator()
    frontend_command_processor = FrontendCommandProcessor()


    twitch = TwitchListener(settings=settings)
    kick = KickListener(settings=settings)
    stt = SpeechToTextListener(
        input_device_index=getattr(settings, "stt_input_device_index", None)
    )

    vtube_handler = None
    if getattr(settings, "enable_vtube_studio", True):
        vtube_handler = VtubeStudioHandler(
            port=getattr(settings, "vtube_studio_port", 8001)
        )

    output_coordinator = OutputCoordinator(
        tts_handler=TTSHandler(),
        obs_handler=OBSHandler(settings=settings),
        vtube_studio_handler=vtube_handler,
        memory_writer=memory_writer,
    )

    audio_player = AudioFilePlayer(audio_directory=getattr(settings, 'audio_directory', 'audio'))
    app.audio_player = audio_player

    ws_service = WebSocketServerService(host="0.0.0.0", port=8765)

    app.add_service(ws_service)
    app.add_service(memory_service)
    app.add_service(generation_coordinator)

    moderation_processor.register_subscriptions(app.event_bus)
    conversation_processor.register_subscriptions(app.event_bus)
    autonomous_prompt_processor.register_subscriptions(app.event_bus)
    frontend_command_processor.register_subscriptions(app.event_bus)

    app.add_service(cognitive)
    app.add_service(twitch)
    app.add_service(kick)
    app.add_service(stt)
    app.add_service(audio_player)
    app.add_service(output_coordinator)

    return app
