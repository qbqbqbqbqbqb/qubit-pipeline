
"""
Main entry point for qubit

This module initializes and runs the AI Vtuber pipeline, coordinating various modules
for monologue generation, Twitch chat interaction, memory management, response generation,
and text-to-speech synthesis.
"""

import asyncio
import signal
import threading
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from scripts2.config.config import INSTRUCTIONS_FILE, ROOT
from scripts2.core.signals import Signals
from scripts2.managers.prompt_manager import PromptManager
from scripts2.modules.memory_module import MemoryModule
from scripts2.modules.monologue_module import MonologueModule
from scripts2.modules.twitch_module import TwitchModule
from scripts2.utils.log_utils import get_logger
from scripts2.config.env_config import settings
from scripts2.core.central_event_broker import CentralEventBroker
from scripts2.core.broker_event_handler import BrokerEventHandler
from scripts2.modules.response_generator_module import ResponseGeneratorModule
from scripts2.models.model_manager import ModelManager
from scripts2.modules.tts_speech_module import TtsSpeechModule
from scripts2.managers.tts_manager import TTSManager
from scripts2.modules.vtube_studio_module import VTubeStudioModule

logger = get_logger("Main")

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def control_page():
    return """
    <html>
        <head><title>Stream Controller</title></head>
        <body>
            <h1>Start Stream Modules</h1>
            <form action="/start" method="post">
                <button type="submit">Start Twitch & Monologue</button>
            </form>
        </body>
    </html>
    """

@app.post("/start")
async def start_modules():
    if not state.startup_trigger.is_set():
        state.startup_trigger.set()
        return {"status": "started"}
    return {"status": "already started"}


class SharedState:
    startup_trigger: asyncio.Event = None

state = SharedState()


def setup_signal_handlers(signals):
    """
    Sets up signal handlers for graceful shutdown on SIGINT and SIGTERM.

    Args:
        signals (Signals): The signals object used for termination flags.
    """
    def signal_handler(sig, frame):
        sig_name = signal.Signals(sig).name
        logger.info(f"Received signal {sig_name}, shutting down...")
        signals.terminate.set()
 
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def start_module_in_thread(module):
    """
    Starts a given module in a separate daemon thread using asyncio.

    Args:
        module: The module instance to start.

    Returns:
        threading.Thread: The thread running the module.
    """
    def run_loop():
        logger.info(f"Thread for module {module.name} started")
        try:
            asyncio.run(module.start())
        except Exception as e:
            logger.error(f"Exception in thread for {module.name}: {e}")
        logger.info(f"Thread for module {module.name} exiting")
 
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    return thread

async def main():
    """
    Main asynchronous function that initializes all components, starts modules,
    and handles the application lifecycle.
    """
    signals = Signals()
    setup_signal_handlers(signals)
    state.startup_trigger = asyncio.Event()

    event_broker = CentralEventBroker()
    tts_manager = TTSManager()
    model_manager = ModelManager()

    vtube_module = VTubeStudioModule(
        signals=signals,
        model_enabled=True,
    )

    await vtube_module.init()

    tts_speech_module = TtsSpeechModule(
        signals=signals,
        settings = settings,
        tts_manager=tts_manager,
        tts_enabled=True,
        vtube_module=vtube_module
    )

    memory_module = MemoryModule(
        base_path=ROOT,
        memory_enabled=True,
        response_generator=None
    )

    prompt_manager = PromptManager(system_instructions=INSTRUCTIONS_FILE, chat_history_manager=memory_module.chat_history_manager)
    
    response_generator_module = ResponseGeneratorModule(
        signals=signals,
        event_broker=event_broker,
        model_manager=model_manager,
        prompt_manager=prompt_manager,
        response_generation_enabled=True,
    )

    response_thread = start_module_in_thread(response_generator_module)

    prompt_manager.memory_module = memory_module
    
    try:
        await asyncio.wait_for(signals.response_generator_ready.wait(), timeout=10)
        logger.info("ResponseGeneratorModule is ready")
    except asyncio.TimeoutError:
        logger.warning("ResponseGeneratorModule did not start in time")

    memory_module = MemoryModule(
        base_path=ROOT,
        memory_enabled=True,
        response_generator=response_generator_module)
    
            
    prompt_manager.memory_module = memory_module
    tts_thread = start_module_in_thread(tts_speech_module)

    try:
        await asyncio.wait_for(signals.tts_module_ready.wait(), timeout=10)
        logger.info("tts_speech_module is ready")
    except asyncio.TimeoutError:
        logger.warning("tts_speech_module did not start in time")

    broker_handler = BrokerEventHandler(
        event_broker,
        tts_speech_module=tts_speech_module,
        response_generator_module=response_generator_module,
        memory_manager=memory_module
    )
    broker_handler.start()


    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())

    logger.info("Web controller started at http://127.0.0.1:8000")


    logger.info("Waiting for browser button press to start Twitch and Monologue...")
    await state.startup_trigger.wait()

    try:
        logger.info("Startup trigger received. Starting Twitch and Monologue modules...")

        event_broker.publish_event({
            "type": "startup",
            "text": "Write a short greeting to say hello and welcome viewers to the stream."
        })

        modules = {
            'twitch': TwitchModule(
                signals=signals,
                settings=settings,
                event_broker=event_broker,
                memory_manager=memory_module,
                twitch_enabled=True,
                chat_enabled=True,
            ),
            'monologue': MonologueModule(
                signals=signals,
                event_broker=event_broker,
                monologue_enabled=True,
            ),
            'memory_manager': memory_module,
        }


        module_threads = {
            'response': response_thread,
            'tts': tts_thread,
        }

        for name, module in modules.items():
            thread = start_module_in_thread(module)
            module_threads[name] = thread
            logger.info(f"Started module '{name}' in thread.")

    except Exception as e:
        logger.exception("Failed to start Twitch/Monologue modules: %s", e)

    try:
        while not signals.terminate.is_set():
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass

    logger.info("Shutdown initiated. Waiting for modules to stop...")

    await asyncio.gather(*(module.stop() for module in [response_generator_module, tts_speech_module] + list(modules.values())))

    for name, thread in module_threads.items():
        logger.info(f"Joining thread for module '{name}'")
        thread.join(timeout=5)

    event_broker.stop()

    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
