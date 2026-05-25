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
from src.qubit.input.frontend_command_processor import FrontendCommandProcessor

# --- Output (coordinator + leaves) ---
from src.qubit.output.output_coordinator import OutputCoordinator
from src.qubit.output.tts_handler import TTSHandler
from src.qubit.output.obs_handler import OBSHandler

# --- Processing (pure EventProcessors: transform / filter / normalise) ---
from src.qubit.processing.moderation_processor import ModerationProcessor
from src.qubit.processing.conversation_processor import ConversationProcessor
from src.qubit.processing.autonomous_prompt_processor import AutonomousPromptProcessor

# --- Generation (the single owner of intent → full prompt → LLM → response_generated) ---
from src.qubit.generation.prompt_request_builder import PromptRequestBuilder
from src.qubit.generation.generation_coordinator import GenerationCoordinator

# --- Memory (storage + RAG provider + background reflections) ---
from src.qubit.memory.memory_service import MemoryService
from src.qubit.memory.memory_writer import MemoryWriter

# --- Cognitive / Decision layer (the only place that decides "what to do") ---
from src.qubit.cognitive.cognitive_orchestrator import CognitiveOrchestrator

# --- Models (single source of truth for LLM usage) ---
from src.qubit.models.llm_service import LLMService
from src.qubit.models.model_registry import LLM_PROFILES

from config.env_config import settings


async def create_app():
    app = App()
    app.state = RuntimeState()
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

    # Temporary glue (will be folded into GenerationCoordinator later)
    prompt_request_builder = PromptRequestBuilder(dispatcher=generation_coordinator)

    # =====================================================================
    # LAYER: Memory (storage owner + RAG provider + background reflections)
    # Writes go through the pure MemoryWriter (EventProcessor).
    # =====================================================================
    memory_service = MemoryService(llm_service=llm_service)
    memory_writer = MemoryWriter(memory_service)

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
        prompt_handler=prompt_request_builder,
        memory_writer=memory_writer
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

    # =====================================================================
    # LAYER: Output (coordinator + implementation leaves)
    # Sanitises responses, owns the speaking queue, drives TTS / OBS / VTube,
    # and owns ai_speaking state.
    # =====================================================================
    output_coordinator = OutputCoordinator(tts_handler=TTSHandler(), 
                                           obs_handler=OBSHandler(settings=settings),  
                                           memory_writer=memory_writer)

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
    app.add_service(output_coordinator)

    return app
