import asyncio

from scripts2.core.central_event_broker import CentralEventBroker


class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, queue_manager, tts_speech_module):
        self.broker = broker
        self.queue_manager = queue_manager
        self.tts_speech_module = tts_speech_module
        self._task = None

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            event_type = event.get("type")
            try:
                if event_type == "monologue":
                    await self.queue_manager.process_new_prompt_from_monologue_generation(event["text"])
                elif event_type == "twitch_chat":
                    await self.queue_manager.process_new_prompt_from_twitch_chat(event["user"], event["message"])
                elif event_type == "response_generated":
                    self.tts_speech_module.submit_response(event)
                else:
                    pass
            except Exception as e:
                print(f"Error processing event {event}: {e}")

    def stop(self):
        if self._task:
            self._task.cancel()
