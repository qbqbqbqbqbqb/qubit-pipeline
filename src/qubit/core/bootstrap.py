"""Wire up and return the fully constructed application instance."""

from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import EventBus
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


async def create_app() -> App:
    """Construct the application with all services, processors, and handlers wired together."""
    app = App()
    app.state = RuntimeState()
    app.state.features.vtube_studio = settings.enable_vtube_studio
    app.event_bus = EventBus()

    # LLM service — profiles registered and executors loaded before anything else.
    llm_service = LLMService()
    for profile in LLM_PROFILES.values():
        llm_service.register_profile(profile)
    await llm_service.ensure_loaded("main")
    await llm_service.ensure_loaded("reflection")
    app.state.llm_service = llm_service

    # Memory
    memory_service = MemoryService(llm_service=llm_service)
    memory_writer = MemoryWriter(
        memory_service,
        stt_speaker_name=settings.stt_speaker_name,
    )

    # Processing — register subscriptions here, not in service.start(),
    # because processors are not long-lived services; they are stateless
    # event handlers that run synchronously on the bus.
    moderation_processor = ModerationProcessor()
    conversation_processor = ConversationProcessor(
        max_age_seconds=30,
        memory_writer=memory_writer,
    )
    autonomous_prompt_processor = AutonomousPromptProcessor(
        max_age_seconds=30,
        memory_writer=memory_writer,
        event_bus=app.event_bus,
    )
    frontend_command_processor = FrontendCommandProcessor()

    for processor in (
        moderation_processor,
        conversation_processor,
        autonomous_prompt_processor,
        frontend_command_processor,
    ):
        processor.register_subscriptions(app.event_bus)

    # Output
    vtube_handler = (
        VtubeStudioHandler(port=settings.vtube_studio_port)
        if settings.enable_vtube_studio
        else None
    )
    output_coordinator = OutputCoordinator(
        tts_handler=TTSHandler(),
        obs_handler=OBSHandler(settings=settings),
        vtube_studio_handler=vtube_handler,
        memory_writer=memory_writer,
    )

    audio_player = AudioFilePlayer(audio_directory=settings.audio_directory)
    app.audio_player = audio_player

    # Services — started in order; WebSocket first so it can receive the
    # frontend start command before anything else is running.
    app.add_service(WebSocketServerService(host="0.0.0.0", port=8765))
    app.add_service(memory_service)
    app.add_service(GenerationCoordinator(llm_service=llm_service, main_profile="main"))
    app.add_service(CognitiveOrchestrator())
    app.add_service(TwitchListener(settings=settings))
    app.add_service(KickListener(settings=settings))
    app.add_service(SpeechToTextListener(input_device_index=settings.stt_input_device_index))
    app.add_service(audio_player)
    app.add_service(output_coordinator)

    return app
