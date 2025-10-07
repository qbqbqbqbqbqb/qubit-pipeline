import asyncio
import signal
import platform

from scripts.config import settings
from scripts.managers.queue_manager import QueueManager
from scripts.utils.log_utils import get_logger
from scripts.utils.refresh_token import refresh_twitch_token
from scripts.managers.task_manager import TaskManager

from scripts.modules.twitch_client import TwitchClient
from scripts.modules.model_module import ModelModule
from scripts.managers.model_manager import ModelManager
from scripts.managers.module_manager import ModuleManager
from scripts.modules.response_module import ResponseModule
from scripts.modules.monologue_module import MonologueModule

from scripts.core.signals import Signals

logger = get_logger("Main")
task_manager = TaskManager()
stop_event = asyncio.Event()

signals = Signals()
signals.monologue_enabled = True


async def handle_signal(sig, frame):
    sig_name = signal.Signals(sig).name
    logger.info(f"Received signal {sig_name}, shutting down...")
    stop_event.set()
    signals.terminate = True


def setup_signal_handlers(loop):
    if platform.system() == "Windows":
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(handle_signal(s, f)))
        signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(handle_signal(s, f)))
    else:
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(handle_signal(signal.SIGINT, None)))
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(handle_signal(signal.SIGTERM, None)))


async def token_refresher_loop():
    while not stop_event.is_set():
        try:
            logger.info("Refreshing Twitch tokens...")
            await refresh_twitch_token()
            logger.info("Token refresh complete.")
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
        await asyncio.sleep(3600)


async def keep_alive_loop():
    while not stop_event.is_set():
        await asyncio.sleep(1)


async def initialise_managers_and_modules(signals):
    module_manager = ModuleManager()
    model_manager = ModelManager.get_instance()
    queue_manager = QueueManager()

    twitch_module = TwitchClient(
        settings,
        signals,
        monologue_module=None, 
        queue_manager=queue_manager,
    )
    model_module = ModelModule(model_manager, signals)
    response_module = ResponseModule(queue_manager, chat_sender=None, signals=signals)

    module_manager.register(model_module)
    module_manager.register(twitch_module)
    module_manager.register(response_module)

    return module_manager, model_manager, queue_manager, twitch_module, model_module, response_module


async def start_core_modules(twitch_module, model_module, response_module):
    await twitch_module.start()
    await model_module.start()

    while twitch_module.chat is None:
        logger.info("[Main] Waiting for Twitch chat to initialise...")
        await asyncio.sleep(1)

    async def send_to_chat(message: str):
        await twitch_module.chat.send_message(settings.twitch_channel, message)

    response_module.set_chat_sender(send_to_chat)
    await response_module.start()


async def wait_for_twitch_chat_ready(twitch_module):
    while twitch_module.chat is None:
        logger.info("[Main] Waiting for Twitch chat to initialise...")
        await asyncio.sleep(1)


async def start_background_tasks(task_manager, monologue_module):
    task_manager.add_task(monologue_module.run())
    task_manager.add_task(token_refresher_loop())
    task_manager.add_task(keep_alive_loop())


async def shutdown_sequence(task_manager, module_manager):
    await task_manager.cancel_all()
    await module_manager.stop_all()
    logger.info("Shutdown complete.")
    asyncio.get_event_loop().stop()


async def main():
    loop = asyncio.get_running_loop()
    setup_signal_handlers(loop)

    module_manager, model_manager, queue_manager, twitch_module, model_module, response_module = await initialise_managers_and_modules(signals)

    await start_core_modules(twitch_module, model_module, response_module)

    monologue_module = MonologueModule(
        signals=signals,
        queue_manager=queue_manager,
        response_generator=response_module,
        memory_manager=getattr(model_manager, "memory_manager", None),
        max_monologues_between_chats=3,
        starters=None,
    )
    module_manager.register(monologue_module)
    twitch_module.monologue_module = monologue_module

    await start_background_tasks(task_manager, monologue_module)

    await stop_event.wait()

    await shutdown_sequence(task_manager, module_manager)


if __name__ == "__main__":
    asyncio.run(main())
