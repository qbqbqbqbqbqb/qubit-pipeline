import asyncio
import time
import signal
import threading

from scripts2.core.signals import Signals
from scripts2.modules.monologue_module import MonologueModule
from scripts2.modules.twitch_module import TwitchModule
from scripts2.managers.queue_manager import QueueManager
from scripts2.utils.log_utils import get_logger
from scripts2.config.env_config import settings
from scripts2.core.central_event_broker import CentralEventBroker 
from scripts2.core.broker_event_handler import BrokerEventHandler
from scripts2.modules.response_generator_module import ResponseGeneratorModule
from scripts2.managers.model_manager import ModelManager
from scripts2.modules.tts_speech_module import TtsSpeechModule
from scripts2.managers.tts_manager import TTSManager

logger = get_logger("Main")

def setup_signal_handlers(signals):
    def signal_handler(sig, frame):
        sig_name = signal.Signals(sig).name
        logger.info(f"Received signal {sig_name}, shutting down...")
        signals.terminate = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def start_module_in_thread(module):
    """
    Each module is async; this runs its start method in a dedicated thread with its own event loop.
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
    signals = Signals()
    setup_signal_handlers(signals)

    event_broker = CentralEventBroker()

    queue_manager = QueueManager()
    await queue_manager.start_merging_queues()
    
    tts_manager = TTSManager()
    
    tts_speech_module = TtsSpeechModule(
    signals=signals,
    tts_manager=tts_manager,
    tts_enabled=True
    )

    broker_handler = BrokerEventHandler(event_broker, queue_manager, tts_speech_module=tts_speech_module)
    broker_handler.start()

    model_manager = ModelManager()


    modules = {
        'twitch': TwitchModule(
            signals=signals,
            settings=settings,
            event_broker=event_broker,
            twitch_enabled=True,
            chat_enabled=True,
        ),
        'monologue': MonologueModule(
            signals=signals,
            event_broker=event_broker,
            monologue_enabled=True,
        ),
        'response':ResponseGeneratorModule(
            signals=signals,
            event_broker=event_broker,
            queue_manager=queue_manager,
            model_manager=model_manager,
            response_generation_enabled=True,
        ),
        'tts':tts_speech_module
    }

    module_threads = {}
    for name, module in modules.items():
        module_threads[name] = start_module_in_thread(module)
        logger.info(f"Started module '{name}' in thread.")

    try:
        while not signals.terminate:
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass

    logger.info("Shutdown initiated. Waiting for modules to stop...")

    await asyncio.gather(*(module.stop() for module in modules.values()))

    for name, thread in module_threads.items():
        logger.info(f"Joining thread for module '{name}'")
        thread.join(timeout=5)

    event_broker.stop()

    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
