"""
VisionListener — periodic window capture and description service.

When the vision FeatureFlag is on, captures the configured window every
VISION_INTERVAL_SECONDS, runs the description through the vision model,
stores the result on RuntimeState.latest_vision_description, and publishes
a VisionContextEvent on the bus so prompt assembly can inject it.

The vision model is loaded lazily on the first capture cycle rather than
at startup, so it doesn't block the rest of the boot sequence.
"""

import asyncio

from config.settings import VISION_MODEL, VISION_INTERVAL_SECONDS
from src.qubit.core.events import VisionContextEvent
from src.qubit.core.service import Service
from src.qubit.input.vision import capture, models
from src.qubit.utils.log_utils import get_logger


class VisionListener(Service):

    def __init__(self) -> None:
        super().__init__("vision listener")
        self._model_loaded = False

    async def start(self) -> None:
        self.logger = get_logger("VisionListener")
        self.logger.info("[start] Vision listener starting — model: %s, interval: %ss",
                         VISION_MODEL, VISION_INTERVAL_SECONDS)
        await self._run()

    async def stop(self) -> None:
        self.logger.info("[stop] Vision listener stopping")

    async def _run(self) -> None:
        while not self.app.state.shutdown.is_set():
            await asyncio.sleep(VISION_INTERVAL_SECONDS)

            if not self.app.state.features.vision:
                continue

            if not self.app.state.start.is_set():
                continue

            await self._capture_and_publish()

    async def _capture_and_publish(self) -> None:
        loop = asyncio.get_running_loop()

        try:
            description = await loop.run_in_executor(None, self._capture_sync)
        except Exception as exc:
            self.logger.error("[_capture_and_publish] Capture failed: %s", exc)
            return

        if not description:
            return

        self.logger.debug("[_capture_and_publish] Vision description: %s", description[:80])
        self.app.state.latest_vision_description = description

        await self.app.event_bus.publish(VisionContextEvent(
            type="vision_context",
            timestamp=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            data={"description": description},
        ))

    def _capture_sync(self) -> str:
        """Blocking — runs in executor thread."""
        if not self._model_loaded:
            models.load(VISION_MODEL)
            self._model_loaded = True

        window_title = getattr(self.app.state, "vision_window", None)
        image = capture.capture_window(window_title)
        if image is None:
            return ""
        return models.describe(image)