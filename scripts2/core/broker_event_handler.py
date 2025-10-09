import asyncio

from scripts2.core.central_event_broker import CentralEventBroker

class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module):
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module=response_generator_module
        self._task = None

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            event_type = event.get("type")
            try:
                if event_type in ("monologue", "startup", "twitch_chat"):
                    user = event.get("user")
                    
                    if event_type in ("monologue", "startup") and not user:
                        user = "system"

                    self.broker.publish_event({
                        "type": "response_prompt",
                        "source": event_type,
                        "user": user,
                        "text": event.get("text"),
                        "original_type": event_type
                    })
                elif event["type"] == "response_generated":
                    if event["original_type"] == "startup":
                        priority = 1
                    else:
                        priority = 10
                    await self.tts_speech_module.consume_response(event)
                elif event["type"] == "response_prompt":
                    if event["original_type"] == "startup":
                        priority = 1
                    else:
                        priority = 10
                    self.response_generator_module.submit_prompt(event, priority)
                else:
                    pass
            except Exception as e:
                print(f"Error processing event {event}: {e}")


    def stop(self):
        if self._task:
            self._task.cancel()
