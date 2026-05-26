"""
Application bootstrap / wiring.

This file is intentionally the ONLY place that knows how all the pieces fit together.
It should remain thin: construction + registration only.

See ARCHITECTURE.md for the target layered model and naming conventions.
The comments below already reflect the desired SoC boundaries (even while some
implementation cleanup is still in progress).
"""

from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus

# --- Core infrastructure ---
from src.qubit.core.server import WebSocketServerService

# --- Input sources (produce raw events) ---
from src.qubit.input.twitch.listener import TwitchListener
from src.qubit.input.kick.listener import KickListener
from src.qubit.input.stt_listener import SpeechToTextListener
from src.qubit.input.frontend_command_processor import FrontendCommandProcessor

# --- Output (coordinator + leaves) ---
from src.qubit.output.coordinator import OutputCoordinator
from src.qubit.output.handlers.tts import TTSHandler
from src.qubit.output.handlers.obs import OBSHandler
from src.qubit.output.handlers.audio_player import AudioFilePlayer
from src.qubit.output.handlers.vtube import VtubeStudioHandler

# --- Processing (pure EventProcessors: transform / filter / normalise) ---
from src.qubit.processing.moderation import ModerationProcessor
from src.qubit.processing.conversation import ConversationProcessor
from src.qubit.processing.autonomous import AutonomousPromptProcessor

# --- Generation (the single owner of intent → full prompt → LLM → response_generated) ---
from src.qubit.generation.coordinator import GenerationCoordinator

# --- Memory (storage + RAG provider + background reflections) ---
from src.qubit.memory.service import MemoryService
from src.qubit.memory.writer import MemoryWriter

# --- Cognitive / Decision layer (the only place that decides "what to do") ---
from src.qubit.cognitive.orchestrator import CognitiveOrchestrator

# --- Models (single source of truth for LLM usage) ---
from src.qubit.models.llm_service import LLMService
from src.qubit.models.model_registry import LLM_PROFILES

from config.env_config import settings


async def create_app():
    """
    The single place that assembles the entire application graph according to
    the target architecture.

    This function:
    - Creates all layer components in the correct dependency order
    - Wires them together (passing shared dependencies like MemoryWriter, LLMService, event_bus)
    - Registers Services for lifecycle management and pure EventProcessors for direct bus subscriptions
    - Returns a fully configured App instance ready to be run by runtime.run_app()

    IMPORTANT: This is intentionally the ONLY file that knows the full wiring.
    Changing the architecture (new layers, renames, new dependencies) should
    primarily happen here and be reflected in the layer READMEs.
    """
    app = App()
    app.state = RuntimeState()
    app.state.features["vtube_studio"] = getattr(settings, "enable_vtube_studio", True)
    app.event_bus = event_bus

    # =====================================================================
    # LAYER: Models (LLM profiles + loading)
    # Single source of truth for all text generation. Everything else calls
    # through LLMService with a named profile.
    # =====================================================================
    llm_service = LLMService()
    for prof in LLM_PROFILES.values():
        llm_service.register_profile(prof)

    # Pre-load the profiles we use at runtime
    await llm_service.ensure_loaded("main")
    await llm_service.ensure_loaded("reflection")

    app.state.llm_service = llm_service

    # =====================================================================
    # LAYER: Generation (the single owner of "high-level intent → full prompt → LLM response")
    # =====================================================================
    generation_coordinator = GenerationCoordinator(llm_service=llm_service, main_profile="main")

    # =====================================================================
    # LAYER: Memory (storage owner + RAG provider + background reflections)
    # Writes go through the pure MemoryWriter (EventProcessor).
    # =====================================================================
    memory_service = MemoryService(llm_service=llm_service)
    memory_writer = MemoryWriter(
        memory_service,
        stt_speaker_name=getattr(settings, "stt_speaker_name", "Speaker")
    )

    # =====================================================================
    # LAYER: Input Processing (pure EventProcessors)
    # Moderation, dedup, staleness, memory writes. No loops here.
    # =====================================================================
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

    # =====================================================================
    # LAYER: Cognitive / Decision (the brain)
    # Owns activity tracking + decision engine + behaviours.
    # The only place allowed to decide "respond now", "monologue now", or "stay silent".
    # =====================================================================
    cognitive = CognitiveOrchestrator()
    frontend_command_processor = FrontendCommandProcessor()
  
    # =====================================================================
    # LAYER: Input Sources (raw event producers)
    # Long-running connections / listeners. They only publish raw events.
    # =====================================================================
    twitch = TwitchListener(settings=settings)
    kick = KickListener(settings=settings)
    stt = SpeechToTextListener(
        input_device_index=getattr(settings, "stt_input_device_index", None)
    )

    # =====================================================================
    # LAYER: Output (coordinator + implementation leaves)
    # Sanitises responses, owns the speaking queue, drives TTS / OBS / VTube,
    # and owns ai_speaking state.
    # =====================================================================
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

    # =====================================================================
    # LAYER: Core infrastructure services (WebSocket control plane)
    # =====================================================================
    ws_service = WebSocketServerService(host="0.0.0.0", port=8765)

    # =====================================================================
    # REGISTRATION
    # Services get the full lifecycle. Pure processors are registered directly.
    # =====================================================================
    app.add_service(ws_service)
    app.add_service(memory_service)
    app.add_service(generation_coordinator)

    moderation_processor.register_subscriptions(app.event_bus)
    conversation_processor.register_subscriptions(app.event_bus)
    autonomous_prompt_processor.register_subscriptions(app.event_bus)
    frontend_command_processor.register_subscriptions(app.event_bus)

    app.add_service(cognitive)  # still assigned to variable 'cognitive' for now (internal name)
    app.add_service(twitch)
    app.add_service(kick)
    app.add_service(stt)
    app.add_service(audio_player)
    app.add_service(output_coordinator)

    return app
